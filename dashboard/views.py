from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import staff_required
from inventory.models import TestDrive, Vehicle
from service.models import Appointment, CustomerCar
from service.predict import predict_services
from shop.models import Order, Part


@login_required
def home(request):
    if request.user.is_dealer_staff:
        return redirect("dashboard:manager")
    today = timezone.localdate()
    cars = []
    for car in request.user.cars.select_related("car_model__make"):
        usage, predictions = predict_services(car, with_slots=False)
        cars.append({"car": car, "usage": usage, "next": predictions[0] if predictions else None})
    context = {
        "cars": cars,
        "appointments": request.user.appointments.filter(date__gte=today, status=Appointment.Status.BOOKED)
        .select_related("service_type", "car__car_model"),
        "test_drives": request.user.test_drives.filter(date__gte=today).select_related("vehicle__car_model__make"),
        "orders": request.user.orders.all()[:5],
        "notifications": request.user.notifications.all()[:5],
    }
    return render(request, "dashboard/customer.html", context)


def _aging_buckets(vehicles):
    buckets = {"0-44 days": 0, "45-89 days": 0, "90-119 days": 0, "120+ days": 0}
    for v in vehicles:
        d = v.days_on_lot
        key = "0-44 days" if d < 45 else "45-89 days" if d < 90 else "90-119 days" if d < 120 else "120+ days"
        buckets[key] += 1
    return buckets


@staff_required
def manager(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    stock = list(Vehicle.objects.filter(status=Vehicle.Status.IN_STOCK).select_related("car_model__make"))

    sold_this_month = Vehicle.objects.filter(status=Vehicle.Status.SOLD, sold_on__gte=month_start)
    parts_revenue = (
        Order.objects.filter(created_at__date__gte=month_start)
        .exclude(status=Order.Status.CANCELLED)
        .aggregate(t=Sum("total"))["t"]
        or 0
    )

    # Customers whose cars need service soon (predictive engine across the whole garage base).
    due = []
    for car in CustomerCar.objects.select_related("owner", "car_model__make"):
        _, preds = predict_services(car, with_slots=False)
        for p in preds:
            if p.status != "ok":
                due.append({"car": car, "pred": p})
    due.sort(key=lambda x: x["pred"].due_date)

    buckets = _aging_buckets(stock)
    appts_today = Appointment.objects.filter(date=today).exclude(status="cancelled").count()
    bay_capacity = settings.SERVICE_BAYS * len(settings.SERVICE_SLOTS)
    context = {
        "gauges": {
            "avg_days": round(sum(v.days_on_lot for v in stock) / len(stock)) if stock else 0,
            "bay_util": round(appts_today * 100 / bay_capacity) if bay_capacity else 0,
            "fresh_pct": round(sum(1 for v in stock if v.days_on_lot < 45) * 100 / len(stock)) if stock else 0,
        },
        "kpi": {
            "in_stock": len(stock),
            "stock_value": sum(v.list_price for v in stock),
            "avg_days": round(sum(v.days_on_lot for v in stock) / len(stock)) if stock else 0,
            "aging": sum(1 for v in stock if v.days_on_lot >= 45),
            "sold_month": sold_this_month.count(),
            "sales_month": sold_this_month.aggregate(t=Sum("sold_price"))["t"] or 0,
            "parts_revenue": parts_revenue,
            "appts_today": appts_today,
        },
        "bucket_labels": list(buckets.keys()),
        "bucket_values": list(buckets.values()),
        "holding_cost": sum(v.advice.holding_cost for v in stock),
        "low_stock": Part.objects.filter(stock__lte=F("reorder_level")).order_by("stock")[:8],
        "test_drives": TestDrive.objects.filter(date__gte=today, date__lte=today + timedelta(days=7))
        .exclude(status="cancelled")
        .select_related("vehicle__car_model__make", "customer"),
        "due_services": due[:10],
        "due_count": len(due),
        "service_mix": Appointment.objects.filter(date__gte=month_start)
        .values("service_type__name")
        .annotate(n=Count("id"))
        .order_by("-n"),
    }
    return render(request, "dashboard/manager.html", context)


@staff_required
def aging(request):
    stock = sorted(
        Vehicle.objects.filter(status=Vehicle.Status.IN_STOCK).select_related("car_model__make"),
        key=lambda v: -v.days_on_lot,
    )
    rows = [{"v": v, "a": v.advice} for v in stock]
    return render(
        request,
        "dashboard/aging.html",
        {
            "rows": rows,
            "actionable": sum(1 for r in rows if r["a"].needs_action),
            "total_holding": sum(r["a"].holding_cost for r in rows),
        },
    )


@staff_required
@require_POST
def apply_all_markdowns(request):
    changed = sum(
        1 for v in Vehicle.objects.filter(status=Vehicle.Status.IN_STOCK) if v.apply_suggested_price(by_user=request.user)
    )
    messages.success(request, f"Applied suggested markdowns to {changed} vehicle(s).")
    return redirect("dashboard:aging")
