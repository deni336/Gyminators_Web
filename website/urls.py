from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("favicon.ico", views.favicon, name="favicon"),
    path("api/health", views.health, name="health"),
    # One-release compatibility redirects for private links issued by the
    # retired local checkout. They never read data or process a payment.
    path("pay/<uuid:token>/", views.legacy_payment_redirect, name="payment_request"),
    path("pay/<uuid:token>/checkout/", views.legacy_payment_redirect, name="payment_request_checkout"),
    path("checkout/success/", views.legacy_checkout_redirect, name="checkout_success"),
    path("stripe/webhook/", views.stripe_webhook_retired, name="stripe_webhook"),
    path("staff/login/", auth_views.LoginView.as_view(template_name="website/login.html"), name="login"),
    path("staff/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/content/", views.content_hub, name="content_hub"),
    path("dashboard/content/site/", views.site_configuration_edit, name="site_configuration_edit"),
    path("dashboard/content/<slug:kind>/", views.content_list, name="content_list"),
    path("dashboard/content/<slug:kind>/new/", views.content_edit, name="content_add"),
    path("dashboard/content/<slug:kind>/<int:pk>/edit/", views.content_edit, name="content_edit"),
    path("dashboard/content/<slug:kind>/<int:pk>/delete/", views.content_delete, name="content_delete"),
]
