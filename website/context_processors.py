from .models import SiteConfiguration


def _can_access_django_admin(user):
    if not user or not user.is_authenticated or not user.is_staff:
        return False
    if user.is_superuser:
        return True
    dashboard_only_permissions = {
        "jackrabbit_reporting.view_reporting_dashboard",
        "jackrabbit_reporting.manage_jackrabbit_sync",
        "waivers.view_waiver",
    }
    return any(
        permission not in dashboard_only_permissions
        and permission.rsplit(".", 1)[-1].startswith(
            ("add_", "change_", "delete_", "view_")
        )
        for permission in user.get_all_permissions()
    )


def site_configuration(request):
    """Make current branding available to public and manager templates."""
    user = getattr(request, "user", None)
    can_manage_website_content = bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.has_perm("website.change_siteconfiguration")
            or any(
                user.has_perm(permission)
                for permission in (
                    "website.change_program",
                    "website.change_event",
                    "website.change_homepagefeature",
                    "website.change_sociallink",
                )
            )
        )
    )
    return {
        "site": SiteConfiguration.get_solo(),
        "can_manage_website_content": can_manage_website_content,
        "can_access_django_admin": _can_access_django_admin(user),
    }
