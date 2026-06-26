from django.urls import path

from apps.core.api.views import HealthCheckAPIView


app_name = "core_api"

urlpatterns = [
    path("health/", HealthCheckAPIView.as_view(), name="health-check"),
]