from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("manager/", views.manager, name="manager"),
    path("aging/", views.aging, name="aging"),
    path("aging/apply-all/", views.apply_all_markdowns, name="apply_all"),
]
