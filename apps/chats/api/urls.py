from rest_framework.routers import DefaultRouter

from apps.chats.api.views import ChatRoomViewSet


router = DefaultRouter()
router.register("chat-rooms", ChatRoomViewSet, basename="chat-rooms")

urlpatterns = router.urls