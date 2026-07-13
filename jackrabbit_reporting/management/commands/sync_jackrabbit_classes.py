from threading import Event

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jackrabbit_reporting.services.class_feed import ClassFeedError, sync_classes


class Command(BaseCommand):
    help = "Synchronize Gyminators' public Jackrabbit class schedule, openings, and published tuition."

    def add_arguments(self, parser):
        parser.add_argument("--organization-id", default=settings.JACKRABBIT_ORG_ID)
        parser.add_argument("--loop", action="store_true", help="Continue synchronizing at a fixed interval.")
        parser.add_argument("--interval", type=int, default=900, help="Seconds between loop runs (minimum 60).")

    def _run_once(self, organization_id):
        run = sync_classes(organization_id=organization_id)
        self.stdout.write(
            self.style.SUCCESS(
                f"Synchronized {run.fetched_count} classes: {run.created_count} created, "
                f"{run.updated_count} updated, {run.deactivated_count} no longer current."
            )
        )

    def handle(self, *args, **options):
        if not settings.JACKRABBIT_REPORTING_ENABLED:
            if options["loop"]:
                self.stdout.write(
                    "Jackrabbit reporting is disabled; the class-sync worker is idle."
                )
                try:
                    Event().wait()
                except KeyboardInterrupt:
                    self.stdout.write("Jackrabbit class synchronization stopped.")
                return
            raise CommandError("Jackrabbit reporting is disabled.")
        organization_id = str(options["organization_id"]).strip()
        if not organization_id:
            raise CommandError("A Jackrabbit organization ID is required.")
        interval = options["interval"]
        if interval < 60:
            raise CommandError("--interval must be at least 60 seconds.")

        if not options["loop"]:
            try:
                self._run_once(organization_id)
            except ClassFeedError as exc:
                raise CommandError(str(exc)) from exc
            return

        stop = Event()
        self.stdout.write(f"Starting Jackrabbit class synchronization every {interval} seconds.")
        try:
            while not stop.is_set():
                try:
                    self._run_once(organization_id)
                except ClassFeedError as exc:
                    self.stderr.write(self.style.ERROR(str(exc)))
                stop.wait(interval)
        except KeyboardInterrupt:
            self.stdout.write("Jackrabbit class synchronization stopped.")
