from django.urls import path

from apps.frontend.views import DashboardPageView, LoginPageView, RegisterPageView


app_name = "frontend"

urlpatterns = [
    path("", LoginPageView.as_view(), name="login"),
    path("login/", LoginPageView.as_view(), name="login"),
    path("register/", RegisterPageView.as_view(), name="register"),
    path("dashboard/", DashboardPageView.as_view(), name="dashboard"),
    path("dashboard/chat/", DashboardPageView.as_view(), {"section": "chat"}, name="dashboard-chat"),
    path("dashboard/profile/", DashboardPageView.as_view(), {"section": "profile"}, name="dashboard-profile"),
    path("dashboard/connections/", DashboardPageView.as_view(), {"section": "connections"}, name="dashboard-connections"),
    path("dashboard/notifications/", DashboardPageView.as_view(), {"section": "notifications"}, name="dashboard-notifications"),
    path("dashboard/privacy/", DashboardPageView.as_view(), {"section": "privacy"}, name="dashboard-privacy"),
]
