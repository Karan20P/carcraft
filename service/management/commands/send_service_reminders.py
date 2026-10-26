from django.core.management.base import BaseCommand

from service.predict import send_reminders


class Command(BaseCommand):
    help = "Send predictive service reminders. Schedule daily (cron / Windows Task Scheduler)."

    def handle(self, *args, **options):
        count = send_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {count} service reminder(s)."))
