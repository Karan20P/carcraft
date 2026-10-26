from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.vehicle_list, name="list"),
    path("<int:pk>/", views.vehicle_detail, name="detail"),
    path("<int:pk>/test-drive/", views.book_test_drive, name="test_drive"),
    path("<int:pk>/apply-markdown/", views.apply_markdown, name="apply_markdown"),
]
