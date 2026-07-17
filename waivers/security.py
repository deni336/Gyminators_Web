from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, ProgrammingError
from django.http import Http404
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import never_cache


def no_sensitive_cache(view):
    """Prevent browser, proxy, and shared-cache storage of waiver responses."""

    @never_cache
    @wraps(view)
    def wrapped(*args, **kwargs):
        response = view(*args, **kwargs)
        patch_cache_control(
            response,
            no_cache=True,
            no_store=True,
            must_revalidate=True,
            private=True,
            max_age=0,
        )
        response["Pragma"] = "no-cache"
        return response

    return wrapped


def public_waiver_required(view):
    """Fail closed when the owner has not explicitly enabled online waivers."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            from website.models import SiteConfiguration

            enabled = bool(SiteConfiguration.get_solo().online_waiver_available)
        except (ImportError, AttributeError, OperationalError, ProgrammingError):
            enabled = False
        if not enabled:
            raise Http404("Online waivers are not available.")
        return view(request, *args, **kwargs)

    return wrapped


def waiver_view_permission_required(view):
    """Protect friendly records UI with the dedicated model permission."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not request.user.has_perm("waivers.view_waiver"):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped
