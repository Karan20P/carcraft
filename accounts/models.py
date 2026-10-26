from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        STAFF = "staff", "Sales / Service Staff"
        MANAGER = "manager", "Manager"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=15, blank=True)

    @property
    def is_dealer_staff(self):
        return self.role in (self.Role.STAFF, self.Role.MANAGER) or self.is_superuser

    def __str__(self):
        return self.get_full_name() or self.username
