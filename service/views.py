from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from shop.models import Part

from .forms import AppointmentForm, CompleteJobForm, CustomerCarForm, OdometerForm
from .models import Appointment, CustomerCar, Notification, OdometerReading
from .predict import predict_services, send_reminders


@login_required
def my_cars(request):
    cars = []
    for car in request.user.cars.select_related("car_model__make"):
        usage, predictions = predict_services(car, with_slots=False)
        cars.append({"car": car, "usage": usage, "next": predictions[0] if predictions else None})
    return render(request, "service/my_cars.html", {"cars": cars})


@login_required
def add_car(request):
    form = CustomerCarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            car = form.save(commit=False)
            car.owner = request.user
            car.save()
            today = timezone.localdate()
            d, km = form.cleaned_data["last_service_date"], form.cleaned_data["last_service_km"]
            if d is not None:
                OdometerReading.objects.create(car=car, date=d, km=km, source=OdometerReading.Source.SERVICE)
            OdometerReading.objects.create(
                car=car, date=today, km=form.cleaned_data["current_km"], source=OdometerReading.Source.REGISTRATION
            )
        messages.success(request, f"{car} added to your garage.")
        return redirect("service:car_detail", pk=car.pk)
    return render(request, "service/car_form.html", {"form": form})


@login_required
def car_detail(request, pk):
    car = get_object_or_404(CustomerCar.objects.select_related("car_model__make"), pk=pk, owner=request.user)
    odo_form = OdometerForm(request.POST or None, car=car)
    if request.method == "POST" and odo_form.is_valid():
        OdometerReading.objects.update_or_create(
            car=car, date=timezone.localdate(), source=OdometerReading.Source.CUSTOMER,
            defaults={"km": odo_form.cleaned_data["km"]},
        )
        messages.success(request, "Reading saved - predictions updated.")
        return redirect("service:car_detail", pk=car.pk)

    usage, predictions = predict_services(car)
    readings = list(car.readings.all())
    history = car.appointments.select_related("service_type").order_by("-date")
    return render(
        request,
        "service/car_detail.html",
        {
            "car": car,
            "usage": usage,
            "predictions": predictions,
            "history": history,
            "odo_form": odo_form,
            "chart_labels": [r.date.isoformat() for r in readings],
            "chart_values": [r.km for r in readings],
        },
    )


@login_required
def book(request):
    if not request.user.cars.exists():
        messages.info(request, "Add your car first so we can book it in.")
        return redirect("service:add_car")
    initial = {k: request.GET[k] for k in ("car", "service_type", "date", "slot") if request.GET.get(k)}
    form = AppointmentForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        appt = form.save(commit=False)
        appt.customer = request.user
        appt.save()
        messages.success(
            request, f"Booked: {appt.service_type} on {appt.date:%d %b} at {appt.slot}. Estimate ₹{appt.estimated_cost:,.0f}."
        )
        return redirect("service:appointments")
    return render(request, "service/book.html", {"form": form})


@login_required
def appointments(request):
    appts = request.user.appointments.select_related("car__car_model__make", "service_type").order_by("-date")
    return render(request, "service/appointments.html", {"appointments": appts, "today": timezone.localdate()})


@login_required
@require_POST
def cancel(request, pk):
    appt = get_object_or_404(Appointment, pk=pk, customer=request.user, status=Appointment.Status.BOOKED)
    appt.status = Appointment.Status.CANCELLED
    appt.save(update_fields=["status"])
    messages.info(request, "Appointment cancelled.")
    return redirect("service:appointments")


@login_required
def notifications(request):
    items = list(request.user.notifications.all()[:50])
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "service/notifications.html", {"items": items})


# --- Staff ------------------------------------------------------------------
@staff_required
def board(request):
    today = timezone.localdate()
    appts = (
        Appointment.objects.filter(date__gte=today)
        .exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.COMPLETED])
        .select_related("customer", "car__car_model__make", "service_type")
    )
    return render(request, "service/board.html", {"appointments": appts, "today": today})


@staff_required
def complete_job(request, pk):
    appt = get_object_or_404(Appointment.objects.select_related("car", "service_type"), pk=pk)
    form = CompleteJobForm(request.POST or None, instance=appt)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            appt = form.save(commit=False)
            appt.status = Appointment.Status.COMPLETED
            appt.completed_at = timezone.now()
            appt.save()
            # The new reading teaches the predictor how much this car is driven.
            OdometerReading.objects.create(
                car=appt.car, date=appt.date, km=appt.odometer_km, source=OdometerReading.Source.SERVICE
            )
            if appt.include_bundle:
                for part in appt.service_type.bundle_parts.all():
                    Part.objects.filter(pk=part.pk, stock__gt=0).update(stock=F("stock") - 1)
        messages.success(request, f"Job completed for {appt.car}. Parts stock updated.")
        return redirect("service:board")
    return render(request, "service/complete_job.html", {"form": form, "appt": appt})


@staff_required
@require_POST
def run_reminders(request):
    count = send_reminders()
    messages.success(request, f"Sent {count} service reminder(s).")
    return redirect("dashboard:manager")
