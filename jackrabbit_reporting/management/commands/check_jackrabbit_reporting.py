from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from jackrabbit_reporting.models import ClassSyncRun, JackrabbitEvent
from jackrabbit_reporting.security import usable_webhook_token


class Command(BaseCommand):
    help = "Show Jackrabbit reporting configuration, event coverage, and class-feed freshness."

    def handle(self, *args, **options):
        organization_id = str(settings.JACKRABBIT_ORG_ID).strip()
        self.stdout.write(f"Reporting enabled: {'yes' if settings.JACKRABBIT_REPORTING_ENABLED else 'no'}")
        self.stdout.write(f"Organization ID: {organization_id or 'missing'}")
        self.stdout.write(
            "Webhook token usable: "
            f"{'yes' if usable_webhook_token(settings.JACKRABBIT_WEBHOOK_TOKEN) else 'no'}"
        )
        required_tables = {
            JackrabbitEvent._meta.db_table,
            ClassSyncRun._meta.db_table,
        }
        if not required_tables.issubset(connection.introspection.table_names()):
            raise CommandError(
                "Jackrabbit reporting tables are unavailable. Run manage.py migrate, "
                "then retry this status check."
            )
        self.stdout.write("Event coverage:")
        for value, label in JackrabbitEvent.EVENT_TYPES:
            events = JackrabbitEvent.objects.filter(
                organization_id=organization_id,
                event_type=value,
            )
            first = events.order_by("occurred_at").values_list("occurred_at", flat=True).first()
            last = events.order_by("-occurred_at").values_list("occurred_at", flat=True).first()
            self.stdout.write(f"  {label}: {events.count()} records; first={first or 'none'}; last={last or 'none'}")
        run = ClassSyncRun.objects.filter(organization_id=organization_id).first()
        if run:
            self.stdout.write(
                f"Latest class sync: {run.status} at {run.started_at}; fetched={run.fetched_count}; "
                f"finished={run.finished_at or 'not finished'}"
            )
        else:
            self.stdout.write("Latest class sync: never")
