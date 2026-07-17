from django.urls import path

from . import views


app_name = "waivers"

urlpatterns = [
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/<uuid:waiver_id>/", views.staff_detail, name="staff_detail"),
    path("staff/<uuid:waiver_id>/pdf/", views.staff_pdf, name="staff_pdf"),
    path("success/<uuid:confirmation_id>/", views.success, name="success"),
    path("<slug:enrollment_type>/new/", views.new_waiver, name="new"),
    path(
        "<slug:enrollment_type>/returning/search/",
        views.returning_search,
        name="returning_search",
    ),
    path(
        "<slug:enrollment_type>/returning/<str:token>/",
        views.returning_waiver,
        name="returning",
    ),
    path("<slug:enrollment_type>/", views.gymnast_status, name="gymnast_status"),
    path("", views.start, name="start"),
]
