from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction


CONTENT_PERMISSIONS = {
    "view_siteconfiguration",
    "change_siteconfiguration",
    "view_program",
    "add_program",
    "change_program",
    "delete_program",
    "view_event",
    "add_event",
    "change_event",
    "delete_event",
    "view_homepagefeature",
    "add_homepagefeature",
    "change_homepagefeature",
    "delete_homepagefeature",
    "view_sociallink",
    "add_sociallink",
    "change_sociallink",
    "delete_sociallink",
}

BUSINESS_PERMISSIONS = CONTENT_PERMISSIONS

REPORTING_PERMISSIONS = {
    "view_reporting_dashboard",
}

WAIVER_PERMISSIONS = {
    "view_waiver",
}


def resolve_website_permissions(codenames):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.filter(
            content_type__app_label="website",
            codename__in=codenames,
        )
    }
    missing = sorted(set(codenames) - permissions.keys())
    if missing:
        raise CommandError(
            "Missing website permissions: "
            + ", ".join(missing)
            + ". Run `python manage.py migrate` before setup_roles."
        )
    return list(permissions.values())


def resolve_reporting_permissions(codenames):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.filter(
            content_type__app_label="jackrabbit_reporting",
            codename__in=codenames,
        )
    }
    missing = sorted(set(codenames) - permissions.keys())
    if missing:
        raise CommandError(
            "Missing Jackrabbit reporting permissions: "
            + ", ".join(missing)
            + ". Run `python manage.py migrate` before setup_roles."
        )
    return list(permissions.values())


def resolve_waiver_permissions(codenames):
    permissions = {
        permission.codename: permission
        for permission in Permission.objects.filter(
            content_type__app_label="waivers",
            codename__in=codenames,
        )
    }
    missing = sorted(set(codenames) - permissions.keys())
    if missing:
        raise CommandError(
            "Missing online-waiver permissions: "
            + ", ".join(missing)
            + ". Run `python manage.py migrate` before setup_roles."
        )
    return list(permissions.values())


class Command(BaseCommand):
    help = (
        "Create or reset the Website Managers, Business Managers, Reporting "
        "Managers, and Waiver Managers groups. Financial reporting stays in Jackrabbit."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        existing_tables = set(connection.introspection.table_names())
        required_tables = {
            Group._meta.db_table,
            Permission._meta.db_table,
            ContentType._meta.db_table,
            Group.permissions.through._meta.db_table,
        }
        if not required_tables.issubset(existing_tables):
            raise CommandError(
                "Authentication tables are missing. Run `python manage.py migrate` "
                "before setup_roles."
            )

        roles = (
            ("Website Managers", CONTENT_PERMISSIONS),
            ("Business Managers", BUSINESS_PERMISSIONS),
        )

        for group_name, codenames in roles:
            group, created = Group.objects.get_or_create(name=group_name)
            permissions = resolve_website_permissions(codenames)
            # These two groups are application-owned. Resetting the set removes
            # stale local billing permissions on every safe rerun.
            group.permissions.set(permissions)
            state = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{state} {group_name} with {len(permissions)} permissions."
                )
            )

        reporting_group, created = Group.objects.get_or_create(name="Reporting Managers")
        reporting_group.permissions.set(resolve_reporting_permissions(REPORTING_PERMISSIONS))
        state = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{state} Reporting Managers with {len(REPORTING_PERMISSIONS)} permissions."
            )
        )

        waiver_group, created = Group.objects.get_or_create(name="Waiver Managers")
        waiver_group.permissions.set(resolve_waiver_permissions(WAIVER_PERMISSIONS))
        state = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{state} Waiver Managers with {len(WAIVER_PERMISSIONS)} permissions."
            )
        )

        self.stdout.write(
            "Assign staff accounts to the appropriate groups in Django admin. "
            "The command does not change users or grant superuser access."
        )
