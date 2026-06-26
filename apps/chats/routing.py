from django.urls import re_path

from apps.chats.consumers import ChatRoomConsumer


websocket_urlpatterns = [
    re_path(
        r"ws/chat/rooms/(?P<room_id>\d+)/$",
        ChatRoomConsumer.as_asgi(),
    ),
]