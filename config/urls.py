from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [
    path("", include("apps.frontend.urls")),

    path("admin/", admin.site.urls),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    path("api/v1/core/", include("apps.core.api.urls")),
    path("api/v1/", include("apps.accounts.api.urls")),
    path("api/v1/", include("apps.profiles.api.urls")),
    path("api/v1/", include("apps.connections.api.urls")),
    path("api/v1/", include("apps.chats.api.urls")),
    path("api/v1/", include("apps.notifications.api.urls")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)