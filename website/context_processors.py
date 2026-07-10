from .models import SiteConfiguration


def site_configuration(request):
    """Make current branding available to public and manager templates."""
    return {"site": SiteConfiguration.get_solo()}
