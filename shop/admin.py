from django.contrib import admin

from .models import Category, Order, OrderItem, Part


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon")


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "price", "stock", "low_stock")
    list_filter = ("category", "is_accessory")
    search_fields = ("name", "sku", "brand")
    list_editable = ("price", "stock")

    @admin.display(boolean=True)
    def low_stock(self, obj):
        return obj.low_stock


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("__str__", "customer", "created_at", "status", "total")
    list_filter = ("status",)
    list_editable = ("status",)
    inlines = [OrderItemInline]
