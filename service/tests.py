from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from inventory.models import CarModel, Make

from .models import Appointment, CustomerCar, Notification, OdometerReading, ServiceType
from .predict import estimate_usage, fit_rate, predict_services, send_reminders


class FitRateTests(TestCase):
    def test_linear_rate(self):
        start = date(2026, 1, 1)
        points = [(start + timedelta(days=d), 10_000 + 50 * d) for d in (0, 30, 60, 90)]
        rate, n = fit_rate(points)
        self.assertAlmostEqual(rate, 50, places=3)
        self.assertEqual(n, 4)

    def test_too_little_history(self):
        self.assertEqual(fit_rate([(date(2026, 1, 1), 100)])[0], None)
        self.assertEqual(fit_rate([(date(2026, 1, 1), 100), (date(2026, 1, 5), 300)])[0], None)


class PredictionTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user("u", password="x")
        cm = CarModel.objects.create(make=Make.objects.create(name="M"), name="X")
        self.car = CustomerCar.objects.create(owner=self.user, car_model=cm, year=2022, registration_no="AB1")
        self.service = ServiceType.objects.create(name="General", labour_price=1000, interval_km=10_000, interval_months=12)

    def _readings(self, km_per_day, days):
        for d in range(days, -1, -30):
            OdometerReading.objects.create(car=self.car, date=self.today - timedelta(days=d), km=20_000 + km_per_day * (days - d))

    def test_heavy_driver_due_by_distance(self):
        self._readings(100, 120)  # 100 km/day
        Appointment.objects.create(customer=self.user, car=self.car, service_type=self.service,
                                   date=self.today - timedelta(days=80), slot="09:00",
                                   status="completed", odometer_km=24_000)
        usage, preds = predict_services(self.car, self.today, with_slots=False)
        self.assertAlmostEqual(usage.km_per_day, 100, delta=1)
        p = preds[0]
        self.assertEqual(p.trigger, "distance")
        # due at 34,000; now at 32,000 -> ~20 days
        self.assertAlmostEqual(p.days_left, 20, delta=2)
        self.assertEqual(p.status, "due_soon")

    def test_light_driver_due_by_time(self):
        self._readings(5, 300)
        Appointment.objects.create(customer=self.user, car=self.car, service_type=self.service,
                                   date=self.today - timedelta(days=350), slot="09:00",
                                   status="completed", odometer_km=20_000)
        _, preds = predict_services(self.car, self.today, with_slots=False)
        self.assertEqual(preds[0].trigger, "time")

    def test_default_rate_with_no_history(self):
        OdometerReading.objects.create(car=self.car, date=self.today, km=5000)
        usage = estimate_usage(self.car, self.today)
        self.assertTrue(usage.is_default)
        self.assertEqual(usage.confidence, "low")

    def test_reminders_not_duplicated(self):
        self._readings(100, 120)
        Appointment.objects.create(customer=self.user, car=self.car, service_type=self.service,
                                   date=self.today - timedelta(days=110), slot="09:00",
                                   status="completed", odometer_km=21_000)
        self.assertEqual(send_reminders(self.today), 1)
        self.assertEqual(send_reminders(self.today), 0)
        self.assertEqual(Notification.objects.count(), 1)

    def test_suggested_slot_respects_bay_capacity(self):
        self._readings(100, 120)
        Appointment.objects.create(customer=self.user, car=self.car, service_type=self.service,
                                   date=self.today - timedelta(days=110), slot="09:00",
                                   status="completed", odometer_km=21_000)
        _, preds = predict_services(self.car, self.today)
        p = preds[0]
        self.assertIsNotNone(p.suggested_date)
        self.assertGreater(p.suggested_date, self.today)
        self.assertNotEqual(p.suggested_date.weekday(), 6)
