from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/bootstrap/", views.api_bootstrap, name="api_bootstrap"),
    path("api/export/", views.api_export, name="api_export"),
    path("api/profile/", views.api_profile, name="api_profile"),
    path("api/records/", views.api_records, name="api_records"),
    path("api/records/<int:record_id>/", views.api_record_detail, name="api_record_detail"),
    path("line/webhook/", views.line_webhook, name="line_webhook"),
]
