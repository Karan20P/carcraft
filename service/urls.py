from django.urls import path

from . import views

app_name = "service"

urlpatterns = [
    path("my-cars/", views.my_cars, name="my_cars"),
    path("my-cars/add/", views.add_car, name="add_car"),
    path("my-cars/<int:pk>/", views.car_detail, name="car_detail"),
    path("book/", views.book, name="book"),
    path("appointments/", views.appointments, name="appointments"),
    path("appointments/<int:pk>/cancel/", views.cancel, name="cancel"),
    path("notifications/", views.notifications, name="notifications"),
    path("board/", views.board, name="board"),
    path("board/<int:pk>/complete/", views.complete_job, name="complete"),
    path("reminders/run/", views.run_reminders, name="run_reminders"),
]
