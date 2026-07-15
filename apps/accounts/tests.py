from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


User = get_user_model()


class UserManagerTests(TestCase):
    def test_create_user_normalizes_email_and_username(self):
        user = User.objects.create_user(
            email="NewUser@Example.com",
            username="Mixed.Case",
            password="Password123!",
        )

        self.assertEqual(user.email, "newuser@example.com")
        self.assertEqual(user.username, "mixed.case")
        self.assertTrue(user.check_password("Password123!"))


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_and_login_flow(self):
        register_response = self.client.post(
            reverse("auth-register"),
            {
                "email": "fresh@example.com",
                "username": "freshuser",
                "name": "Fresh User",
                "password": "Password123!",
                "password2": "Password123!",
            },
            format="json",
        )

        self.assertEqual(register_response.status_code, 201)
        self.assertTrue(User.objects.filter(username="freshuser").exists())

        login_response = self.client.post(
            reverse("auth-login"),
            {
                "identifier": "freshuser",
                "password": "Password123!",
            },
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
        self.assertEqual(login_response.data["user"]["username"], "freshuser")
