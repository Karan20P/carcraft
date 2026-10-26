from django.conf import settings
from django.db import models
from django.utils import timezone

from inventory.models import CarModel, Vehicle
from shop.models import Part

SLOT_CHOICES = [(s, s) for s in settings.SERVICE_SLOTS]


class ServiceType(models.Model):
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    labour_price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=60)
    # Maintenance schedule. Leave both blank for one-off jobs (e.g. "Accident repair").
    interval_km = models.PositiveIntegerField(null=True, blank=True, help_text="Due every N km")
    interval_months = models.PositiveIntegerField(null=True, blank=True, help_text="...or every N months")
    bundle_parts = models.ManyToManyField(
        Part, blank=True, related_name="service_bundles", help_text="Parts usually needed for this job"
    )

    class Meta:
        ordering = ["interval_km", "name"]

    def __str__(self):
        return self.name

    @property
    def is_periodic(self):
        return bool(self.interval_km or self.interval_months)

    @property
    def bundle_total(self):
        return sum((p.price for p in self.bundle_parts.all()), 0)


class CustomerCar(models.Model):
    """A car in a customer's garage - bought here or brought in for service."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cars")
    car_model = models.ForeignKey(CarModel, on_delete=models.PROTECT)
    year = models.PositiveIntegerField()
    registration_no = models.CharField(max_length=15, unique=True)
    fuel = models.CharField(max_length=10, choices=Vehicle.Fuel.choices, default=Vehicle.Fuel.PETROL)
    vehicle = models.OneToOneField(
        Vehicle, null=True, blank=True, on_delete=models.SET_NULL, help_text="Set if bought from this dealership"
    )
    added_on = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["-added_on"]

    def __str__(self):
        return f"{self.car_model} ({self.registration_no})"


class OdometerReading(models.Model):
    """Every known (date, km) point for a car. These feed the usage predictor."""

    class Source(models.TextChoices):
        REGISTRATION = "registration", "Added to garage"
        SERVICE = "service", "Recorded at service"
        CUSTOMER = "customer", "Logged by owner"

    car = models.ForeignKey(CustomerCar, on_delete=models.CASCADE, related_name="readings")
    date = models.DateField(default=timezone.localdate)
    km = models.PositiveIntegerField()
    source = models.CharField(max_length=15, choices=Source.choices, default=Source.CUSTOMER)

    class Meta:
        ordering = ["date", "km"]

    def __str__(self):
        return f"{self.car}: {self.km} km on {self.date}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appointments")
    car = models.ForeignKey(CustomerCar, on_delete=models.CASCADE, related_name="appointments")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT)
    date = models.DateField()
    slot = models.CharField(max_length=5, choices=SLOT_CHOICES)
    include_bundle = models.BooleanField(default=True, help_text="Add the recommended parts bundle")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.BOOKED)
    notes = models.CharField(max_length=250, blank=True)
    odometer_km = models.PositiveIntegerField(null=True, blank=True, help_text="Recorded when the job is completed")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["date", "slot"]

    def __str__(self):
        return f"{self.service_type} - {self.car} on {self.date} {self.slot}"

    @property
    def estimated_cost(self):
        cost = self.service_type.labour_price
        if self.include_bundle:
            cost += self.service_type.bundle_total
        return cost

    @classmethod
    def slot_is_free(cls, date, slot, exclude_pk=None):
        qs = cls.objects.filter(date=date, slot=slot).exclude(status=cls.Status.CANCELLED)
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.count() < settings.SERVICE_BAYS


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    car = models.ForeignKey(CustomerCar, null=True, blank=True, on_delete=models.CASCADE)
    service_type = models.ForeignKey(ServiceType, null=True, blank=True, on_delete=models.SET_NULL)
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
