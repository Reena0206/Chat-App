from django.views.generic import TemplateView


class LoginPageView(TemplateView):
    template_name = "frontend/login.html"


class RegisterPageView(TemplateView):
    template_name = "frontend/register.html"


class DashboardPageView(TemplateView):
    template_name = "frontend/dashboard.html"