from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chats.models import ChatRoom, ChatRoomParticipant, Message
from apps.chats.services import get_room_unread_count_for_user, get_total_unread_count_for_user
from apps.connections.models import Connection, UserBlock
from apps.profiles.models import Profile


User = get_user_model()


class ChatApiTests(TestCase):
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

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_one_to_one_room_endpoint_creates_room_for_connected_users(self):
        self.authenticate(self.alice)
        response = self.client.post(
            reverse("chat-rooms-one-to-one"),
            {
                "username": "bob",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["room"]["room_key"], self.room.room_key)
        self.assertEqual(len(response.data["room"]["participants"]), 2)

    def test_one_to_one_room_endpoint_rejects_blocked_users(self):
        UserBlock.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

        self.authenticate(self.alice)
        response = self.client.post(
            reverse("chat-rooms-one-to-one"),
            {
                "username": "bob",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["non_field_errors"][0], "You cannot start a chat with this user.")

    def test_unread_counts_track_incoming_messages(self):
        participant = ChatRoomParticipant.objects.get(room=self.room, user=self.alice)
        participant.last_seen_at = timezone.now() - timedelta(days=1)
        participant.save(update_fields=["last_seen_at"])

        Message.objects.create(
            room=self.room,
            sender=self.bob,
            text="first",
        )
        Message.objects.create(
            room=self.room,
            sender=self.bob,
            text="second",
        )
        Message.objects.create(
            room=self.room,
            sender=self.alice,
            text="self message",
        )

        self.assertEqual(
            get_room_unread_count_for_user(room_id=self.room.id, user_id=self.alice.id),
            2,
        )
        self.assertEqual(
            get_total_unread_count_for_user(user_id=self.alice.id),
            2,
        )

    def test_room_list_excludes_blocked_users(self):
        UserBlock.objects.create(
            blocker=self.alice,
            blocked=self.bob,
        )

        self.authenticate(self.alice)
        response = self.client.get(reverse("chat-rooms-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_send_message_creates_message(self):
        self.authenticate(self.alice)
        response = self.client.post(
            reverse("chat-rooms-send-message", kwargs={"pk": self.room.pk}),
            {
                "text": "Hello there",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(Message.objects.filter(room=self.room, sender=self.alice, text="Hello there").exists())

