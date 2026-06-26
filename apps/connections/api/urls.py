from rest_framework.routers import DefaultRouter

from apps.connections.api.views import (
    ConnectionRequestViewSet,
    ConnectionViewSet,
    UserBlockViewSet,
    UserRestrictionViewSet,
)


router = DefaultRouter()
router.register(
    "connection-requests",
    ConnectionRequestViewSet,
    basename="connection-requests",
)
router.register(
    "connections",
    ConnectionViewSet,
    basename="connections",
)
router.register(
    "blocks",
    UserBlockViewSet,
    basename="blocks",
)
router.register(
    "restrictions",
    UserRestrictionViewSet,
    basename="restrictions",
)

urlpatterns = router.urls