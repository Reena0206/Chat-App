from django.views.generic import TemplateView


class LoginPageView(TemplateView):
    template_name = "frontend/login.html"


class RegisterPageView(TemplateView):
    template_name = "frontend/register.html"


class DashboardPageView(TemplateView):
    template_name = "frontend/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_section"] = getattr(self, "section", None) or self.kwargs.get("section", "chat")
        return context
