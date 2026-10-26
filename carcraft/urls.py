from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from inventory.views import home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("cars/", include("inventory.urls")),
    path("shop/", include("shop.urls")),
    path("service/", include("service.urls")),
    path("dashboard/", include("dashboard.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "CarCraft Administration"
admin.site.site_title = "CarCraft Admin"
