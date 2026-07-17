from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from waivers.models import Waiver
from waivers.services import ensure_stored_waiver_pdf


class Command(BaseCommand):
    help = (
        "Generate immutable, parsed PDF artifacts for legacy signed waivers that "
        "do not already have one. Existing artifacts are never replaced."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of waiver IDs fetched from the database per iterator batch.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not 1 <= batch_size <= 1000:
            raise CommandError("--batch-size must be between 1 and 1000.")

        waiver_ids = (
            Waiver.objects.filter(stored_pdf__isnull=True)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        examined = 0
        created = 0
        for waiver_id in waiver_ids.iterator(chunk_size=batch_size):
            examined += 1
            with transaction.atomic():
                waiver = Waiver.objects.select_for_update().get(pk=waiver_id)
                _artifact, was_created = ensure_stored_waiver_pdf(waiver)
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Stored {created} waiver PDF artifact(s); "
                f"examined {examined} missing waiver(s)."
            )
        )
