from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts.api.views import AuthViewSet, UserViewSet


router = DefaultRouter()
router.register("auth", AuthViewSet, basename="auth")
router.register("users", UserViewSet, basename="users")


urlpatterns = [
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "auth/token/verify/",
        TokenVerifyView.as_view(),
        name="token-verify",
    ),
]

urlpatterns += router.urls