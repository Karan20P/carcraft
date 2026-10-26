from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from inventory.models import Vehicle
from service.models import CustomerCar


class SmokeTests(TestCase):
    """Every page renders with the demo data, for each kind of user."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_public_pages(self):
        v = Vehicle.objects.filter(status="in_stock").first()
        for url in ["/", reverse("inventory:list"), reverse("inventory:detail", args=[v.pk]),
                    reverse("shop:list"), reverse("shop:cart"), reverse("login"), reverse("signup")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_customer_pages(self):
        self.client.login(username="customer", password="demo1234")
        car = CustomerCar.objects.filter(owner__username="customer").first()
        for url in [reverse("dashboard:home"), reverse("service:my_cars"), reverse("service:add_car"),
                    reverse("service:car_detail", args=[car.pk]), reverse("service:book"),
                    reverse("service:appointments"), reverse("service:notifications"), reverse("shop:orders")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        # customers can't see staff pages
        self.assertEqual(self.client.get(reverse("dashboard:aging")).status_code, 403)

    def test_manager_pages(self):
        self.client.login(username="manager", password="demo1234")
        for url in [reverse("dashboard:manager"), reverse("dashboard:aging"), reverse("service:board")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        r = self.client.post(reverse("dashboard:apply_all"), follow=True)
        self.assertContains(r, "Applied suggested markdowns")
        r = self.client.post(reverse("service:run_reminders"), follow=True)
        self.assertContains(r, "service reminder")

    def test_checkout_flow(self):
        from shop.models import Part
        self.client.login(username="customer", password="demo1234")
        part = Part.objects.filter(stock__gt=2).first()
        stock_before = part.stock
        self.client.post(reverse("shop:cart_add", args=[part.pk]), {"quantity": 2})
        r = self.client.post(reverse("shop:checkout"), {"shipping_address": "x", "phone": "1"}, follow=True)
        self.assertContains(r, "placed")
        part.refresh_from_db()
        self.assertEqual(part.stock, stock_before - 2)
