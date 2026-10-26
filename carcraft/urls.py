from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from inventory.views import home

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("cars/", include("inventory.urls")),
    path("shop/", include("shop.urls")),
    path("service/", include("service.urls")),
    path("dashboard/", include("dashboard.urls")),
    # Media (car photos, uploads) is served by Django in every environment.
    # Fine for this demo-sized app; a large site would use a CDN / object storage.
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]

admin.site.site_header = "CarCraft Administration"
admin.site.site_title = "CarCraft Admin"
