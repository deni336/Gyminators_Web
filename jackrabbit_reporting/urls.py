from django.urls import path

from . import views


app_name = "jackrabbit_reporting"

urlpatterns = [
    path("api/jackrabbit/v1/events/", views.ingest_event, name="ingest_event"),
    path("dashboard/reporting/", views.reporting_dashboard, name="dashboard"),
    path("dashboard/reporting/classes/", views.class_list, name="classes"),
    path("dashboard/reporting/classes/sync/", views.sync_class_feed, name="sync_classes"),
]
