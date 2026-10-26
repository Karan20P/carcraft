from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms import SignUpForm


def signup(request):
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to CarCraft! Add your car to get service predictions.")
        return redirect("dashboard:home")
    return render(request, "accounts/signup.html", {"form": form})
