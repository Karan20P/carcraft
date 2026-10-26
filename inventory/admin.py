from django.contrib import admin

from .models import CarModel, Make, PriceChange, TestDrive, Vehicle


class CarModelInline(admin.TabularInline):
    model = CarModel
    extra = 1


@admin.register(Make)
class MakeAdmin(admin.ModelAdmin):
    inlines = [CarModelInline]


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ("name", "make", "body_type")
    list_filter = ("make", "body_type")


class PriceChangeInline(admin.TabularInline):
    model = PriceChange
    extra = 0
    readonly_fields = ("old_price", "new_price", "reason", "changed_by", "changed_at")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("__str__", "vin", "status", "list_price", "acquired_on", "days_on_lot")
    list_filter = ("status", "fuel", "is_new", "car_model__make")
    search_fields = ("vin", "car_model__name", "car_model__make__name")
    inlines = [PriceChangeInline]


@admin.register(TestDrive)
class TestDriveAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "customer", "date", "time", "status")
    list_filter = ("status", "date")
    list_editable = ("status",)
