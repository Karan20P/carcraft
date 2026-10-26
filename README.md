# CarCraft: Automotive Inventory & Dealership Suite

Vehicle inventory and dealership management, plus an e-commerce store for parts/accessories and
service appointment scheduling. Built with **Python, Django, Bootstrap 5 and MySQL**.

## Novelty features

### 1. Predictive Service Engine (`service/predict.py`)
Most service reminders run on a fixed calendar ("every 6 months"). CarCraft learns how much **each car
is actually driven**:

1. Every known odometer point (date, km) is stored: when the car is added, at every completed service
   (entered by the technician) and whenever the owner logs a reading.
2. A **least-squares regression line** is fitted through those points. Its slope is the car's
   usage rate in km/day. With too little history it falls back to a city average (33 km/day) and
   reports *low confidence*.
3. Each periodic service has a km interval and a time interval (e.g. General Service: 10,000 km or 12 months).
   The engine projects when the car will reach the km limit at **its own rate**, and the due date is
   whichever limit comes first (distance or time).
4. For services that are due soon or overdue, it finds the **first free service-bay slot** (capacity-aware,
   closed on Sundays) and attaches the **recommended parts bundle** with a cost estimate.
5. `python manage.py send_service_reminders` (schedule it daily) creates in-app notifications and e-mails,
   with a one-click "book this slot" link. It won't remind about the same car and service more than once a week.

So a highway driver doing 100 km/day is reminded after about 3 months (distance), while a weekend driver
is reminded at 12 months (time).

### 2. Inventory Aging & Price Advisor (`inventory/pricing.py`)
Every day an unsold car costs the dealer money (finance interest, insurance, lot space; modelled as 0.05% of
cost per day). The advisor:

| Days on lot | Stage    | Suggested markdown (from original price) |
|-------------|----------|-------------------------------------------|
| 0-44        | Fresh    | none                                      |
| 45-89       | Aging    | -2%                                       |
| 90-119      | Stale    | -5%                                       |
| 120+        | Critical | -8%, consider wholesale/auction           |

* Prices are rounded down to the nearest ₹500 and **never drop below cost + 2%**.
* Markdowns are measured against the *original* listing price, so a stage applies once only.
* Every change is logged in `PriceChange` (audit trail), and customers see "Price reduced from ₹X".
* The manager dashboard shows an aging histogram and the total holding cost of current stock.

## Modules
| App         | What it does |
|-------------|--------------|
| `accounts`  | Custom user with roles (customer / staff / manager), sign-up and login |
| `inventory` | Makes, models, vehicles, search and filters, test-drive booking, aging advisor |
| `shop`      | Parts and accessories catalogue, session cart, checkout with stock locking, orders |
| `service`   | Customer garage, odometer log, appointments with bay capacity, service board, predictive engine |
| `dashboard` | Customer dashboard, manager KPIs, aging advisor page |

## Run it (SQLite, quickest)
```bash
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on Mac/Linux)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo       # demo data
python manage.py fetch_car_images  # real model photos (needs internet, run once)
python manage.py runserver
```
Open http://127.0.0.1:8000

| Login             | Sees |
|-------------------|------|
| `manager / demo1234`  | Manager dashboard, aging advisor, service board, `/admin` |
| `staff / demo1234`    | Service board (complete jobs) |
| `customer / demo1234` | Garage with 2 cars (one due by time, one due by distance) |
| `priya / demo1234`    | Garage with an overdue heavy-use car and a lightly used one |

## Car photos
`fetch_car_images` downloads one freely licensed photo per car model from Wikimedia Commons into
`media/car_models/`, with author and licence saved in `credits.json`. The credit is shown under the photo on
each vehicle page. Every vehicle of that model uses the photo unless it has its own upload (Admin → Vehicles → image).
Models without a photo fall back to the painted car silhouette. The source for each model is listed in
`inventory/images.py`.

## Deploy (Render, free)
The repo includes a `render.yaml` blueprint and `build.sh`.
1. Sign in at https://render.com with GitHub.
2. **New → Blueprint**, pick this repo, then **Apply**.

Each deploy installs dependencies, collects static files and builds a fresh demo database, so the live site
always starts with the demo data. On the free plan the filesystem resets when the service restarts or sleeps,
which also resets the demo. The service sleeps after 15 min idle (the first request then takes about 50 s).
A free uptime monitor (e.g. UptimeRobot) pinging the URL every 5 minutes keeps it awake.

## Switch to MySQL
```sql
CREATE DATABASE carcraft CHARACTER SET utf8mb4;
```
```powershell
pip install -r requirements-mysql.txt
$env:DB_ENGINE="mysql"; $env:DB_NAME="carcraft"; $env:DB_USER="root"; $env:DB_PASSWORD="yourpassword"
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## Tests
```bash
python manage.py test
```
15 tests cover the regression rate, distance- and time-triggered predictions, reminder de-duplication,
slot suggestion, every aging stage, the cost floor, apply-once markdowns, checkout stock decrement and
a smoke test of every page per role.

## Demo script (for the viva)
1. Log in as **priya**, go to My Garage, then the Nexon. It shows 121 km/day learned from history, General
   Service **overdue** by distance, a suggested slot and the parts bundle. Click book.
2. Log in as **customer**, go to the Swift. It is lightly driven, so service is due by **time**, not km.
   Log a higher odometer reading and watch the prediction update.
3. Log in as **manager**, open the Dashboard, then **Send service reminders**. Customers now see bell notifications.
4. Open the **Aging Advisor**: cars 45-150 days old get suggested markdowns. Apply one, then open the car page
   to see "Price reduced".
5. Open the **Service Board** and complete a job with an odometer reading. This feeds back into the predictor
   and reduces parts stock.
