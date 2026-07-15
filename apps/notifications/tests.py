from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.chats.models import ChatRoom, Message
from apps.connections.models import Connection
from apps.notifications.models import Notification
from apps.profiles.models import Profile


User = get_user_model()


class NotificationApiTests(TestCase):
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
        for user in [self.alice, self.bob]:
            Profile.objects.get_or_create(user=user)
        Connection.create_connection(self.alice, self.bob)
        self.room = ChatRoom.get_or_create_one_to_one_room(self.alice, self.bob, created_by=self.alice)
        self.message = Message.objects.create(
            room=self.room,
            sender=self.bob,
            text="Hello alice",
        )

        self.connection_request_notification = Notification.objects.create(
            recipient=self.alice,
            actor=self.bob,
            notification_type=Notification.NotificationType.CONNECTION_REQUEST,
            title="Request",
            body="bob sent you a request.",
        )
        self.connection_accepted_notification = Notification.objects.create(
            recipient=self.alice,
            actor=self.bob,
            notification_type=Notification.NotificationType.CONNECTION_ACCEPTED,
            title="Accepted",
            body="bob accepted.",
        )
        self.new_message_notification = Notification.objects.create(
            recipient=self.alice,
            actor=self.bob,
            notification_type=Notification.NotificationType.NEW_MESSAGE,
            title="New message",
            body="bob sent a message.",
            chat_room=self.room,
            message=self.message,
        )

        self.client.force_authenticate(user=self.alice)

    def test_list_excludes_new_message_notifications(self):
        response = self.client.get(reverse("notifications-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertTrue(
            all(item["notification_type"] != Notification.NotificationType.NEW_MESSAGE for item in response.data["results"])
        )

    def test_unread_count_and_mark_read_endpoints(self):
        unread_response = self.client.get(reverse("notifications-unread-count"))
        self.assertEqual(unread_response.status_code, 200)
        self.assertEqual(unread_response.data["unread_count"], 2)

        mark_read_response = self.client.post(
            reverse("notifications-mark-read", kwargs={"pk": self.connection_request_notification.pk}),
            {},
            format="json",
        )
        self.assertEqual(mark_read_response.status_code, 200)
        self.connection_request_notification.refresh_from_db()
        self.assertTrue(self.connection_request_notification.is_read)

        mark_all_response = self.client.post(reverse("notifications-mark-all-read"), {}, format="json")
        self.assertEqual(mark_all_response.status_code, 200)
        self.assertEqual(mark_all_response.data["updated_count"], 1)

        self.connection_accepted_notification.refresh_from_db()
        self.new_message_notification.refresh_from_db()
        self.assertTrue(self.connection_accepted_notification.is_read)
        self.assertFalse(self.new_message_notification.is_read)

        final_unread_response = self.client.get(reverse("notifications-unread-count"))
        self.assertEqual(final_unread_response.data["unread_count"], 0)
