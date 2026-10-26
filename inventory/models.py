from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from . import pricing


class Make(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CarModel(models.Model):
    class Body(models.TextChoices):
        HATCHBACK = "hatchback", "Hatchback"
        SEDAN = "sedan", "Sedan"
        SUV = "suv", "SUV"
        MUV = "muv", "MUV"
        PICKUP = "pickup", "Pickup"

    make = models.ForeignKey(Make, on_delete=models.CASCADE, related_name="models")
    name = models.CharField(max_length=50)
    body_type = models.CharField(max_length=20, choices=Body.choices, default=Body.SEDAN)
    image = models.ImageField(upload_to="car_models/", blank=True, help_text="Stock photo shared by all vehicles of this model")
    image_credit = models.CharField(max_length=300, blank=True)
    image_source = models.URLField(blank=True, help_text="Where the photo came from (for attribution)")

    class Meta:
        ordering = ["make__name", "name"]
        unique_together = ("make", "name")

    def __str__(self):
        return f"{self.make} {self.name}"


class Vehicle(models.Model):
    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "In stock"
        RESERVED = "reserved", "Reserved"
        SOLD = "sold", "Sold"

    class Fuel(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"
        CNG = "cng", "CNG"
        EV = "ev", "Electric"
        HYBRID = "hybrid", "Hybrid"

    class Transmission(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATIC = "automatic", "Automatic"

    vin = models.CharField("VIN", max_length=17, unique=True)
    car_model = models.ForeignKey(CarModel, on_delete=models.PROTECT, related_name="vehicles")
    variant = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField()
    fuel = models.CharField(max_length=10, choices=Fuel.choices, default=Fuel.PETROL)
    transmission = models.CharField(max_length=10, choices=Transmission.choices, default=Transmission.MANUAL)
    color = models.CharField(max_length=30)
    odometer_km = models.PositiveIntegerField(default=0)
    is_new = models.BooleanField(default=True)

    cost_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="What the dealership paid")
    list_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Current asking price")
    acquired_on = models.DateField(default=timezone.localdate)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.IN_STOCK)
    sold_on = models.DateField(null=True, blank=True)
    sold_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases"
    )

    image = models.ImageField(upload_to="vehicles/", blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-acquired_on"]

    def __str__(self):
        return f"{self.year} {self.car_model} {self.variant}".strip()

    @property
    def display_image(self):
        """The vehicle's own photo, else its model's stock photo (may be empty)."""
        return self.image or self.car_model.image

    # --- Inventory aging & price advisor ------------------------------------
    @property
    def days_on_lot(self):
        end = self.sold_on if self.status == self.Status.SOLD and self.sold_on else timezone.localdate()
        return (end - self.acquired_on).days

    @property
    def original_price(self):
        first_change = self.price_changes.order_by("changed_at").first()
        return first_change.old_price if first_change else self.list_price

    @property
    def advice(self):
        return pricing.advise(self.days_on_lot, self.list_price, self.cost_price, self.original_price)

    @property
    def margin(self):
        return self.list_price - self.cost_price

    def apply_suggested_price(self, by_user=None):
        """Apply the advisor's markdown and log it in price history."""
        advice = self.advice
        if advice.suggested_price >= self.list_price:
            return False
        PriceChange.objects.create(
            vehicle=self,
            old_price=self.list_price,
            new_price=advice.suggested_price,
            reason=f"Aging advisor: {advice.stage_label} ({self.days_on_lot} days on lot)",
            changed_by=by_user,
        )
        self.list_price = advice.suggested_price
        self.save(update_fields=["list_price"])
        return True


class PriceChange(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="price_changes")
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=200)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    @property
    def drop_percent(self):
        if not self.old_price:
            return Decimal("0")
        return ((self.old_price - self.new_price) / self.old_price * 100).quantize(Decimal("0.1"))


class TestDrive(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="test_drives")
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="test_drives")
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "time"]

    def __str__(self):
        return f"Test drive: {self.vehicle} by {self.customer} on {self.date}"
