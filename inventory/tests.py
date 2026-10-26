from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import CarModel, Make, Vehicle
from .pricing import advise


class PricingAdvisorTests(TestCase):
    def test_fresh_car_unchanged(self):
        a = advise(10, 1_000_000, 900_000)
        self.assertEqual(a.stage, "fresh")
        self.assertFalse(a.needs_action)

    def test_aging_stages(self):
        self.assertEqual(advise(45, 1_000_000, 900_000).suggested_price, Decimal("980000"))
        self.assertEqual(advise(90, 1_000_000, 900_000).suggested_price, Decimal("950000"))
        self.assertEqual(advise(130, 1_000_000, 900_000).suggested_price, Decimal("920000"))

    def test_never_below_cost_floor(self):
        a = advise(130, 1_000_000, 960_000)  # 8% off would be 920k, floor is 979,200
        self.assertTrue(a.hit_floor)
        self.assertEqual(a.suggested_price, Decimal("979200"))

    def test_markdown_applies_once_per_stage(self):
        make = Make.objects.create(name="Test")
        cm = CarModel.objects.create(make=make, name="Car")
        v = Vehicle.objects.create(
            vin="V1", car_model=cm, year=2024, color="Red", cost_price=900_000, list_price=1_000_000,
            acquired_on=timezone.localdate() - timedelta(days=50),
        )
        self.assertTrue(v.apply_suggested_price())
        self.assertEqual(v.list_price, Decimal("980000"))
        self.assertFalse(v.apply_suggested_price())  # second click does nothing
        # Later stage still measured against the ORIGINAL price.
        v.acquired_on = timezone.localdate() - timedelta(days=95)
        v.save()
        self.assertTrue(v.apply_suggested_price())
        self.assertEqual(v.list_price, Decimal("950000"))
