from rest_framework.routers import DefaultRouter

from apps.profiles.api.views import ProfileViewSet


router = DefaultRouter()
router.register("profiles", ProfileViewSet, basename="profiles")

urlpatterns = router.urls