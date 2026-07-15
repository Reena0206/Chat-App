from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.connections.models import Connection, ConnectionRequest, UserBlock, UserRestriction
from apps.profiles.models import Profile


User = get_user_model()


class ConnectionPrivacyApiTests(TestCase):
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
        for user in [self.alice, self.bob, self.carol]:
            Profile.objects.get_or_create(user=user)

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_block_cleans_up_connections_requests_and_restrictions(self):
        Connection.create_connection(self.alice, self.bob)
        ConnectionRequest.objects.create(
            from_user=self.bob,
            to_user=self.alice,
        )
        UserRestriction.objects.create(
            owner=self.alice,
            restricted_user=self.bob,
        )

        self.authenticate(self.alice)
        response = self.client.post(
            reverse("blocks-block"),
            {
                "username": "bob",
                "reason": "Not interested",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserBlock.objects.filter(blocker=self.alice, blocked=self.bob).exists())
        self.assertFalse(UserRestriction.objects.filter(owner=self.alice, restricted_user=self.bob).exists())
        self.assertFalse(Connection.objects.filter(user1__in=[self.alice, self.bob], user2__in=[self.alice, self.bob]).exists())
        self.assertEqual(
            ConnectionRequest.objects.get(from_user=self.bob, to_user=self.alice).status,
            ConnectionRequest.Status.CANCELLED,
        )

    def test_restrict_creates_entry_and_unrestrict_removes_it(self):
        self.authenticate(self.alice)
        response = self.client.post(
            reverse("restrictions-restrict"),
            {
                "username": "carol",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserRestriction.objects.filter(owner=self.alice, restricted_user=self.carol).exists())

        second_response = self.client.post(
            reverse("restrictions-restrict"),
            {
                "username": "carol",
            },
            format="json",
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            UserRestriction.objects.filter(owner=self.alice, restricted_user=self.carol).count(),
            1,
        )

        unblock_response = self.client.post(
            reverse("restrictions-unrestrict"),
            {
                "username": "carol",
            },
            format="json",
        )

        self.assertEqual(unblock_response.status_code, 200)
        self.assertFalse(UserRestriction.objects.filter(owner=self.alice, restricted_user=self.carol).exists())

    def test_cannot_restrict_blocked_user(self):
        UserBlock.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

        self.authenticate(self.alice)
        response = self.client.post(
            reverse("restrictions-restrict"),
            {
                "username": "bob",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Unblock this user before restricting them.")

    def test_unblock_returns_error_when_user_is_not_blocked(self):
        self.authenticate(self.alice)
        response = self.client.post(
            reverse("blocks-unblock"),
            {
                "username": "bob",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "This user is not blocked.")
