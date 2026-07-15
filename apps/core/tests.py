from django.test import TestCase


class FrontendRouteTests(TestCase):
    def test_public_frontend_pages_render(self):
        for path in [
            "/",
            "/login/",
            "/register/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=path)

    def test_dashboard_section_routes_render(self):
        expected_sections = {
            "/dashboard/": "chat",
            "/dashboard/chat/": "chat",
            "/dashboard/profile/": "profile",
            "/dashboard/connections/": "connections",
            "/dashboard/notifications/": "notifications",
            "/dashboard/privacy/": "privacy",
        }

        for path, section in expected_sections.items():
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, msg=path)
            self.assertEqual(response.context["active_section"], section)

    def test_health_check_endpoint_is_available(self):
        response = self.client.get("/api/v1/core/health/")
        self.assertEqual(response.status_code, 200)
