from django.urls import path

from apps.frontend.views import DashboardPageView, LoginPageView, RegisterPageView


app_name = "frontend"

urlpatterns = [
    path("", LoginPageView.as_view(), name="login"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("dashboard/", DashboardPageView.as_view(), name="dashboard"),
]