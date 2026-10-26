from django.core.management.base import BaseCommand

from inventory.images import attach_all, download_all


class Command(BaseCommand):
    help = "Download stock photos for each car model from Wikimedia Commons and attach them."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Re-download photos that already exist")

    def handle(self, *args, force=False, **options):
        self.stdout.write("Downloading model photos...")
        download_all(stdout=self.stdout, force=force)
        count = attach_all()
        self.stdout.write(self.style.SUCCESS(f"Attached photos to {count} car model(s)."))
