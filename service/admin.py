from django.contrib import admin

from .models import Appointment, CustomerCar, Notification, OdometerReading, ServiceType


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "labour_price", "duration_minutes", "interval_km", "interval_months")
    filter_horizontal = ("bundle_parts",)


class OdometerInline(admin.TabularInline):
    model = OdometerReading
    extra = 0


@admin.register(CustomerCar)
class CustomerCarAdmin(admin.ModelAdmin):
    list_display = ("registration_no", "car_model", "year", "owner")
    search_fields = ("registration_no", "owner__username")
    inlines = [OdometerInline]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("car", "service_type", "date", "slot", "status", "odometer_km")
    list_filter = ("status", "service_type", "date")
    list_editable = ("status",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "is_read", "created_at")
