from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import staff_required
from service.models import Appointment
from shop.models import Part

from .forms import TestDriveForm
from .models import Make, Vehicle


def home(request):
    vehicles = Vehicle.objects.filter(status=Vehicle.Status.IN_STOCK).select_related("car_model__make")[:6]
    parts = Part.objects.filter(stock__gt=0).select_related("category")[:4]
    stats = {
        "in_stock": Vehicle.objects.filter(status=Vehicle.Status.IN_STOCK).count(),
        "makes": Make.objects.count(),
        "parts": Part.objects.count(),
        "serviced": Appointment.objects.filter(status=Appointment.Status.COMPLETED).count(),
    }
    return render(request, "home.html", {"vehicles": vehicles, "parts": parts, "stats": stats})


def vehicle_list(request):
    qs = Vehicle.objects.exclude(status=Vehicle.Status.SOLD).select_related("car_model__make")
    q = request.GET.get("q", "").strip()
    make = request.GET.get("make", "")
    fuel = request.GET.get("fuel", "")
    condition = request.GET.get("condition", "")
    max_price = request.GET.get("max_price", "")
    sort = request.GET.get("sort", "newest")

    if q:
        qs = qs.filter(
            Q(car_model__name__icontains=q) | Q(car_model__make__name__icontains=q) | Q(variant__icontains=q)
        )
    if make:
        qs = qs.filter(car_model__make_id=make)
    if fuel:
        qs = qs.filter(fuel=fuel)
    if condition in ("new", "used"):
        qs = qs.filter(is_new=(condition == "new"))
    if max_price.isdigit():
        qs = qs.filter(list_price__lte=int(max_price))

    qs = qs.order_by(
        {"price_low": "list_price", "price_high": "-list_price", "year": "-year"}.get(sort, "-acquired_on")
    )
    page = Paginator(qs, 9).get_page(request.GET.get("page"))
    return render(
        request,
        "inventory/vehicle_list.html",
        {
            "page": page,
            "makes": Make.objects.all(),
            "fuels": Vehicle.Fuel.choices,
            "filters": request.GET,
        },
    )


def vehicle_detail(request, pk):
    vehicle = get_object_or_404(Vehicle.objects.select_related("car_model__make"), pk=pk)
    form = TestDriveForm()
    return render(request, "inventory/vehicle_detail.html", {"vehicle": vehicle, "form": form})


@login_required
def book_test_drive(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk, status=Vehicle.Status.IN_STOCK)
    form = TestDriveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        td = form.save(commit=False)
        td.vehicle = vehicle
        td.customer = request.user
        td.save()
        messages.success(request, f"Test drive requested for {td.date:%d %b} at {td.time:%H:%M}. We'll confirm shortly.")
        return redirect("dashboard:home")
    return render(request, "inventory/vehicle_detail.html", {"vehicle": vehicle, "form": form})


@staff_required
def apply_markdown(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == "POST":
        old = vehicle.list_price
        if vehicle.apply_suggested_price(by_user=request.user):
            messages.success(request, f"{vehicle}: price dropped from ₹{old:,.0f} to ₹{vehicle.list_price:,.0f}.")
        else:
            messages.info(request, f"{vehicle}: no markdown needed right now.")
    return redirect("dashboard:aging")
