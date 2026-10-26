"""
Load realistic demo data so the novelty features have something to show:
aging stock spread over 0-150 days, and customer cars with odometer history.

    python manage.py seed_demo          # only if the DB is empty
    python manage.py seed_demo --reset  # wipe CarCraft data and reseed
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from inventory.images import attach_all
from inventory.models import CarModel, Make, PriceChange, TestDrive, Vehicle
from service.models import Appointment, CustomerCar, Notification, OdometerReading, ServiceType
from shop.models import Category, Order, OrderItem, Part

CATALOGUE = {
    "Maruti Suzuki": [("Swift", "hatchback", 650000), ("Baleno", "hatchback", 720000), ("Brezza", "suv", 980000)],
    "Hyundai": [("i20", "hatchback", 780000), ("Creta", "suv", 1350000), ("Verna", "sedan", 1250000)],
    "Tata": [("Punch", "suv", 680000), ("Nexon", "suv", 1050000), ("Harrier", "suv", 1900000)],
    "Mahindra": [("XUV700", "suv", 2100000), ("Scorpio-N", "suv", 1750000)],
    "Honda": [("City", "sedan", 1300000), ("Amaze", "sedan", 820000)],
    "Toyota": [("Innova Crysta", "muv", 2300000), ("Fortuner", "suv", 3800000)],
}
VARIANTS = ["LXi", "VXi", "ZXi", "SX", "EX", "Asta", "Creative", "AX5", "Top"]
COLOURS = ["Pearl White", "Midnight Black", "Fire Red", "Silky Silver", "Ocean Blue", "Granite Grey"]

PARTS = [
    # (category, icon, sku, name, brand, price, stock, accessory)
    ("Engine & Oil", "bi-droplet", "OIL-5W30-4L", "Engine Oil 5W-30 (4 L)", "Castrol", 2450, 40, False),
    ("Engine & Oil", "bi-droplet", "FLT-OIL-01", "Oil Filter", "Bosch", 380, 60, False),
    ("Engine & Oil", "bi-droplet", "FLT-AIR-01", "Air Filter", "Bosch", 650, 35, False),
    ("Engine & Oil", "bi-droplet", "SPK-IRID-4", "Iridium Spark Plugs (set of 4)", "NGK", 1960, 18, False),
    ("Engine & Oil", "bi-droplet", "CLT-LL-1L", "Long-life Coolant (1 L)", "Motul", 420, 4, False),
    ("Brakes", "bi-disc", "BRK-PAD-FR", "Front Brake Pads", "Brembo", 2200, 20, False),
    ("Brakes", "bi-disc", "BRK-FLD-500", "Brake Fluid DOT4 (500 ml)", "Bosch", 350, 3, False),
    ("Electrical", "bi-battery-charging", "BAT-35AH", "Battery 35Ah", "Amaron", 4800, 12, False),
    ("Electrical", "bi-battery-charging", "BLB-LED-H4", "LED Headlight Bulbs H4", "Philips", 2600, 15, False),
    ("Cabin & Comfort", "bi-wind", "FLT-CAB-01", "Cabin AC Filter", "Mahle", 520, 30, False),
    ("Cabin & Comfort", "bi-wind", "WPR-BLD-PR", "Wiper Blades (pair)", "Bosch", 750, 25, False),
    ("Accessories", "bi-stars", "ACC-DASHCAM", "Full-HD Dash Camera", "70mai", 5490, 10, True),
    ("Accessories", "bi-stars", "ACC-MAT-3D", "3D Floor Mats", "Autofurnish", 2999, 14, True),
    ("Accessories", "bi-stars", "ACC-SEATCVR", "Premium Seat Covers", "Elegant", 6499, 0, True),
    ("Accessories", "bi-stars", "ACC-TYREINF", "Portable Tyre Inflator", "Michelin", 3290, 9, True),
]

SERVICES = [
    # (name, labour, minutes, interval_km, interval_months, bundle SKUs, description)
    ("General Service", 1800, 180, 10000, 12, ["OIL-5W30-4L", "FLT-OIL-01", "FLT-AIR-01", "FLT-CAB-01"],
     "Engine oil & filter change, air/cabin filter, 50-point inspection."),
    ("Wheel Alignment & Balancing", 900, 60, 10000, 12, [], "Computerised alignment and wheel balancing."),
    ("Brake Service", 1200, 90, 20000, 24, ["BRK-PAD-FR", "BRK-FLD-500"], "Brake pad replacement and fluid top-up."),
    ("Spark Plug Replacement", 600, 45, 30000, 36, ["SPK-IRID-4"], "Replace all spark plugs."),
    ("Coolant Flush", 800, 60, 40000, 24, ["CLT-LL-1L"], "Drain and refill engine coolant."),
    ("Battery Health Check", 300, 30, None, 24, [], "Load-test battery and terminals."),
    ("Accident / Body Repair", 2500, 240, None, None, [], "Dent, paint and body work (quoted on inspection)."),
    ("Car Wash & Detailing", 1200, 120, None, None, [], "Exterior foam wash, interior vacuum and polish."),
]


def _vin(rng):
    chars = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "MA" + "".join(rng.choice(chars) for _ in range(15))


class Command(BaseCommand):
    help = "Seed CarCraft with demo data."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing CarCraft data first")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        if reset:
            for model in (Notification, Appointment, OdometerReading, CustomerCar, ServiceType, OrderItem, Order,
                          Part, Category, TestDrive, PriceChange, Vehicle, CarModel, Make):
                model.objects.all().delete()
            User.objects.filter(username__in=["manager", "staff", "customer", "priya"]).delete()
        elif Make.objects.exists():
            self.stdout.write(self.style.WARNING("Data already present. Use --reset to reseed."))
            return

        rng = random.Random(42)
        today = timezone.localdate()

        # --- Users -----------------------------------------------------------
        manager = User.objects.create_superuser("manager", "manager@carcraft.test", "demo1234",
                                                first_name="Arjun", last_name="Mehta", role=User.Role.MANAGER)
        User.objects.create_user("staff", "staff@carcraft.test", "demo1234", first_name="Ravi",
                                 role=User.Role.STAFF, is_staff=True)
        customer = User.objects.create_user("customer", "customer@carcraft.test", "demo1234", first_name="Rahul",
                                            last_name="Sharma", phone="9876543210")
        priya = User.objects.create_user("priya", "priya@carcraft.test", "demo1234", first_name="Priya",
                                         last_name="Nair", phone="9123456780")

        # --- Makes, models, vehicles ----------------------------------------
        models_by_name = {}
        for make_name, items in CATALOGUE.items():
            make = Make.objects.create(name=make_name)
            for name, body, base in items:
                models_by_name[name] = (CarModel.objects.create(make=make, name=name, body_type=body), base)

        # Days-on-lot spread so every aging stage shows up in the demo.
        ages = [3, 8, 15, 22, 30, 38, 47, 52, 61, 75, 88, 95, 104, 118, 131, 149]
        names = list(models_by_name)
        for i, age in enumerate(ages):
            cm, base = models_by_name[names[i % len(names)]]
            is_new = i % 3 != 0
            list_price = Decimal(base if is_new else int(base * rng.uniform(0.55, 0.8)) // 1000 * 1000)
            Vehicle.objects.create(
                vin=_vin(rng), car_model=cm, variant=rng.choice(VARIANTS),
                year=today.year if is_new else rng.randint(today.year - 6, today.year - 2),
                fuel=rng.choice(["petrol", "petrol", "diesel", "cng"]), transmission=rng.choice(["manual", "automatic"]),
                color=rng.choice(COLOURS), odometer_km=0 if is_new else rng.randint(18000, 70000), is_new=is_new,
                cost_price=(list_price * Decimal("0.90")).quantize(Decimal("1")), list_price=list_price,
                acquired_on=today - timedelta(days=age),
                description=f"{'Brand new' if is_new else 'Certified pre-owned'} {cm}. Inspected by the CarCraft workshop.",
            )
        # A few sold this month for the dashboard.
        for name in ("City", "Brezza", "Nexon"):
            cm, base = models_by_name[name]
            Vehicle.objects.create(
                vin=_vin(rng), car_model=cm, variant="Top", year=today.year, color=rng.choice(COLOURS),
                cost_price=Decimal(base) * Decimal("0.9"), list_price=base, acquired_on=today - timedelta(days=40),
                status=Vehicle.Status.SOLD, sold_on=today - timedelta(days=rng.randint(0, min(10, today.day - 1))),
                sold_price=base, buyer=customer,
            )

        # --- Parts & services ------------------------------------------------
        cats, parts = {}, {}
        for cat, icon, sku, name, brand, price, stock, acc in PARTS:
            if cat not in cats:
                cats[cat] = Category.objects.create(name=cat, icon=icon)
            parts[sku] = Part.objects.create(sku=sku, name=name, brand=brand, category=cats[cat], price=price,
                                             stock=stock, is_accessory=acc, description=f"Genuine {brand} {name.lower()}.")
        services = {}
        for name, labour, mins, km, months, skus, desc in SERVICES:
            st = ServiceType.objects.create(name=name, labour_price=labour, duration_minutes=mins,
                                            interval_km=km, interval_months=months, description=desc)
            st.bundle_parts.set([parts[s] for s in skus])
            services[name] = st

        # --- Customer garages with history (feeds the predictor) -------------
        def make_car(owner, model_name, reg, year, start_km, km_per_day, history_days, serviced_days_ago):
            car = CustomerCar.objects.create(owner=owner, car_model=models_by_name[model_name][0], year=year,
                                             registration_no=reg, added_on=today - timedelta(days=history_days))
            # Readings roughly every 60 days with some noise - real driving isn't perfectly linear.
            for d in range(history_days, -1, -60):
                km = start_km + int(km_per_day * (history_days - d) * rng.uniform(0.92, 1.08))
                OdometerReading.objects.create(car=car, date=today - timedelta(days=d), km=km,
                                               source=OdometerReading.Source.CUSTOMER)
            for i, days_ago in enumerate(serviced_days_ago):
                km = start_km + int(km_per_day * (history_days - days_ago))
                appt_date = today - timedelta(days=days_ago)
                # Every visit: general service + alignment. Latest visit was a full "major" service.
                jobs = ["General Service", "Wheel Alignment & Balancing"]
                if i == len(serviced_days_ago) - 1:
                    jobs += ["Brake Service", "Spark Plug Replacement", "Coolant Flush", "Battery Health Check"]
                for job in jobs:
                    Appointment.objects.create(customer=owner, car=car, service_type=services[job],
                                               date=appt_date, slot="10:30", status=Appointment.Status.COMPLETED,
                                               odometer_km=km, completed_at=timezone.now() - timedelta(days=days_ago))
                OdometerReading.objects.create(car=car, date=appt_date, km=km, source=OdometerReading.Source.SERVICE)
            return car

        # Rahul: city commuter, ~25 km/day, last service ~11 months ago -> due soon by TIME.
        make_car(customer, "Swift", "MH12AB1234", today.year - 4, 22000, 25, 720, [690, 340])
        # Rahul: highway driver, ~95 km/day, serviced 85 days ago -> due soon by DISTANCE.
        make_car(customer, "Creta", "MH14CD5678", today.year - 2, 15000, 95, 420, [400, 85])
        # Priya: heavy user, ~120 km/day, last service 110 days ago -> OVERDUE.
        make_car(priya, "Nexon", "KA05EF9012", today.year - 3, 30000, 120, 500, [470, 110])
        # Priya: barely driven, ~8 km/day -> on track.
        make_car(priya, "Amaze", "KA03GH3456", today.year - 1, 2000, 8, 300, [60])

        # --- A little activity -----------------------------------------------
        swift = CustomerCar.objects.get(registration_no="MH12AB1234")
        next_day = today + timedelta(days=2 if today.weekday() != 4 else 3)
        Appointment.objects.create(customer=customer, car=swift, service_type=services["Car Wash & Detailing"],
                                   date=next_day, slot="12:00", include_bundle=False)
        TestDrive.objects.create(vehicle=Vehicle.objects.filter(status="in_stock").first(), customer=customer,
                                 date=today + timedelta(days=1), time="11:00", status=TestDrive.Status.CONFIRMED)
        order = Order.objects.create(customer=customer, shipping_address="12 MG Road, Pune", phone="9876543210",
                                     total=parts["ACC-DASHCAM"].price + parts["WPR-BLD-PR"].price)
        OrderItem.objects.create(order=order, part=parts["ACC-DASHCAM"], quantity=1, unit_price=parts["ACC-DASHCAM"].price)
        OrderItem.objects.create(order=order, part=parts["WPR-BLD-PR"], quantity=1, unit_price=parts["WPR-BLD-PR"].price)

        photos = attach_all()
        if not photos:
            self.stdout.write("No model photos on disk yet: run `python manage.py fetch_car_images` for real car photos.")

        self.stdout.write(self.style.SUCCESS(
            "Demo data loaded.\n"
            "  manager / demo1234  (manager dashboard, aging advisor, admin)\n"
            "  staff   / demo1234  (service board)\n"
            "  customer / demo1234, priya / demo1234  (garage + predictions)"
        ))
