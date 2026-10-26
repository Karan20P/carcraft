#!/usr/bin/env bash
# Render build: install, collect static files, and create a fresh demo database.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py seed_demo --reset
