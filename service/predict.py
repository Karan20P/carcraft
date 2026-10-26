"""
Predictive Service Engine (novelty feature).

Instead of reminding every customer "every 6 months", CarCraft learns how much
*each* car is actually driven:

1. Collect every known odometer point (date, km) for the car - when it was
   added, every completed service, and readings the owner logs.
2. Fit a least-squares line through those points. The slope is the car's
   usage rate in km/day. (Few points -> fall back to a city-average rate.)
3. For every periodic service (oil change every 10,000 km / 12 months, etc.)
   work out when the car will hit the km limit at its own rate, and when the
   time limit expires. Whichever comes first is the due date.
4. Suggest the first free service-bay slot near that date, plus the parts
   bundle that job needs.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

MIN_SPAN_DAYS = 14  # need at least two weeks of history to trust a trend
MAX_KM_PER_DAY = 400  # sanity cap against typos in odometer readings


@dataclass
class UsageEstimate:
    km_per_day: float
    confidence: str  # "low" | "medium" | "high"
    points: int
    current_km: int
    is_default: bool

    @property
    def km_per_month(self):
        return round(self.km_per_day * 30)


@dataclass
class ServicePrediction:
    service_type: object
    last_date: date
    last_km: int
    due_km: int | None
    due_date_by_km: date | None
    due_date_by_time: date | None
    due_date: date
    trigger: str  # "distance" or "time"
    days_left: int
    km_left: int | None
    status: str  # "overdue" | "due_soon" | "ok"
    bundle: list = field(default_factory=list)
    bundle_total: Decimal = Decimal("0")
    suggested_date: date | None = None
    suggested_slot: str | None = None
    life_used: int = 0  # % of the service interval already used up (can exceed 100)

    @property
    def status_label(self):
        return {"overdue": "Overdue", "due_soon": "Due soon", "ok": "On track"}[self.status]

    @property
    def color(self):
        return {"overdue": "danger", "due_soon": "warning", "ok": "success"}[self.status]

    @property
    def days_overdue(self):
        return abs(self.days_left)

    @property
    def km_over(self):
        return abs(self.km_left) if self.km_left is not None else None

    @property
    def total_estimate(self):
        return self.service_type.labour_price + self.bundle_total


def _add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    # clamp day (e.g. 31 Jan + 1 month -> 28/29 Feb)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue


def fit_rate(points):
    """
    Least-squares slope of km against days. Returns (km_per_day or None, n).
    `points` is a list of (date, km).
    """
    points = sorted(points)
    n = len(points)
    if n < 2:
        return None, n
    origin = points[0][0]
    xs = [(d - origin).days for d, _ in points]
    ys = [km for _, km in points]
    if xs[-1] - xs[0] < MIN_SPAN_DAYS:
        return None, n
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return None, n
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return max(0.0, min(slope, MAX_KM_PER_DAY)), n


def estimate_usage(car, today=None):
    today = today or timezone.localdate()
    points = list(car.readings.values_list("date", "km"))
    rate, n = fit_rate(points)
    is_default = rate is None
    if is_default:
        rate = float(settings.DEFAULT_KM_PER_DAY)
    confidence = "low" if is_default or n < 3 else ("medium" if n < 5 else "high")

    if points:
        last_date, last_km = max(points)
        current_km = int(last_km + rate * max(0, (today - last_date).days))
    else:
        current_km = 0
    return UsageEstimate(round(rate, 1), confidence, n, current_km, is_default)


def _last_service(car, service_type):
    """Last completed job of this type, else the date the car joined the garage."""
    appt = (
        car.appointments.filter(service_type=service_type, status="completed", odometer_km__isnull=False)
        .order_by("-date")
        .first()
    )
    if appt:
        return appt.date, appt.odometer_km
    first = car.readings.order_by("date").first()
    if first:
        return first.date, first.km
    return car.added_on, 0


def suggest_slot(target_date, today=None):
    """First date on/after target (never in the past, never Sunday) with a free bay."""
    from .models import Appointment

    today = today or timezone.localdate()
    day = max(target_date, today + timedelta(days=1))
    for _ in range(60):
        if day.weekday() != 6:  # workshop closed on Sundays
            for slot in settings.SERVICE_SLOTS:
                if Appointment.slot_is_free(day, slot):
                    return day, slot
        day += timedelta(days=1)
    return None, None


def predict_services(car, today=None, with_slots=True):
    from .models import Appointment, ServiceType

    today = today or timezone.localdate()
    usage = estimate_usage(car, today)
    rate = usage.km_per_day
    predictions = []

    # Services already booked for this car don't need a reminder.
    booked = set(
        car.appointments.filter(status__in=["booked", "in_progress"], date__gte=today).values_list(
            "service_type_id", flat=True
        )
    )

    for st in ServiceType.objects.prefetch_related("bundle_parts"):
        if not st.is_periodic or st.pk in booked:
            continue
        last_date, last_km = _last_service(car, st)

        due_km = due_by_km = None
        km_left = None
        if st.interval_km:
            due_km = last_km + st.interval_km
            km_left = due_km - usage.current_km
            due_by_km = today + timedelta(days=round(km_left / rate)) if rate > 0 else None

        due_by_time = _add_months(last_date, st.interval_months) if st.interval_months else None

        candidates = [(d, t) for d, t in ((due_by_km, "distance"), (due_by_time, "time")) if d]
        if not candidates:
            continue
        due_date, trigger = min(candidates)
        days_left = (due_date - today).days

        if days_left < 0:
            status = "overdue"
        elif days_left <= settings.SERVICE_DUE_SOON_DAYS:
            status = "due_soon"
        else:
            status = "ok"

        fractions = []
        if st.interval_km:
            fractions.append((usage.current_km - last_km) / st.interval_km)
        if st.interval_months:
            fractions.append((today - last_date).days / (st.interval_months * 30.44))

        bundle = list(st.bundle_parts.all())
        pred = ServicePrediction(
            life_used=max(0, round(max(fractions) * 100)),
            service_type=st,
            last_date=last_date,
            last_km=last_km,
            due_km=due_km,
            due_date_by_km=due_by_km,
            due_date_by_time=due_by_time,
            due_date=due_date,
            trigger=trigger,
            days_left=days_left,
            km_left=km_left,
            status=status,
            bundle=bundle,
            bundle_total=sum((p.price for p in bundle), Decimal("0")),
        )
        if with_slots and status != "ok":
            # Aim for a few days before it's due so the customer isn't late.
            pred.suggested_date, pred.suggested_slot = suggest_slot(due_date - timedelta(days=3), today)
        predictions.append(pred)

    predictions.sort(key=lambda p: p.due_date)
    return usage, predictions


def send_reminders(today=None):
    """
    Create in-app notifications (and console e-mails) for every service that is
    overdue or due soon. Won't nag about the same car+service more than weekly.
    Returns the number of reminders sent.
    """
    from .models import CustomerCar, Notification

    today = today or timezone.localdate()
    week_ago = timezone.now() - timedelta(days=7)
    sent = 0
    for car in CustomerCar.objects.select_related("owner", "car_model__make"):
        _, predictions = predict_services(car, today)
        for p in predictions:
            if p.status == "ok":
                continue
            if Notification.objects.filter(car=car, service_type=p.service_type, created_at__gte=week_ago).exists():
                continue
            when = f"was due {abs(p.days_left)} days ago" if p.status == "overdue" else f"is due in {p.days_left} days"
            msg = f"{p.service_type} for {car.car_model} ({car.registration_no}) {when}."
            if p.suggested_date:
                msg += f" Free slot: {p.suggested_date:%d %b} at {p.suggested_slot}."
            link = reverse("service:book") + f"?car={car.pk}&service_type={p.service_type.pk}"
            if p.suggested_date:
                link += f"&date={p.suggested_date.isoformat()}&slot={p.suggested_slot}"
            Notification.objects.create(
                user=car.owner, car=car, service_type=p.service_type, message=msg, link=link
            )
            if car.owner.email:
                car.owner.email_user("CarCraft service reminder", msg)
            sent += 1
    return sent
