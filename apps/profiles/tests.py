from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.connections.models import UserBlock
from apps.profiles.models import Profile


User = get_user_model()


class ProfileApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(
            email="alice@example.com",
            username="alice",
            password="Password123!",
        )
        self.bob = User.objects.create_user(
            email="bob@example.com",
            username="bob",
            password="Password123!",
        )
        self.carol = User.objects.create_user(
            email="carol@example.com",
            username="carol",
            password="Password123!",
        )
        self.dave = User.objects.create_user(
            email="dave@example.com",
            username="dave",
            password="Password123!",
        )

        self.alice_profile, _ = Profile.objects.get_or_create(user=self.alice)
        self.bob_profile, _ = Profile.objects.get_or_create(user=self.bob)
        self.carol_profile, _ = Profile.objects.get_or_create(user=self.carol)
        self.dave_profile, _ = Profile.objects.get_or_create(user=self.dave)

        self.bob_profile.account_visibility = Profile.AccountVisibility.PRIVATE
        self.bob_profile.save(update_fields=["account_visibility"])
        self.carol_profile.account_visibility = Profile.AccountVisibility.PUBLIC
        self.carol_profile.save(update_fields=["account_visibility"])
        self.dave_profile.account_visibility = Profile.AccountVisibility.PUBLIC
        self.dave_profile.save(update_fields=["account_visibility"])

        UserBlock.objects.create(
            blocker=self.alice,
            blocked=self.carol,
        )

        self.client.force_authenticate(user=self.alice)

    def test_profile_list_excludes_private_and_blocked_users(self):
        response = self.client.get(reverse("profiles-list"))

        self.assertEqual(response.status_code, 200)
        usernames = [item["username"] for item in response.data["results"]]
        self.assertIn("dave", usernames)
        self.assertNotIn("bob", usernames)
        self.assertNotIn("carol", usernames)

    def test_private_profile_returns_preview(self):
        response = self.client.get(reverse("profiles-detail", kwargs={"username": "bob"}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "This account is private.")
        self.assertEqual(response.data["username"], "bob")

    def test_blocked_profile_is_not_available(self):
        response = self.client.get(reverse("profiles-detail", kwargs={"username": "carol"}))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "This profile is not available.")
