from django.urls import re_path

from apps.chats.consumers import ChatRoomConsumer, ChatUpdatesConsumer


websocket_urlpatterns = [
    re_path(
        r"ws/chat/rooms/(?P<room_id>\d+)/$",
        ChatRoomConsumer.as_asgi(),
    ),
    re_path(
        r"ws/chat/updates/$",
        ChatUpdatesConsumer.as_asgi(),
    ),
]
