import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from apps.chats.middleware import JWTAuthMiddlewareStack
from apps.chats.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from apps.notifications.routing import websocket_urlpatterns as notification_websocket_urlpatterns


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

websocket_urlpatterns = chat_websocket_urlpatterns + notification_websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)