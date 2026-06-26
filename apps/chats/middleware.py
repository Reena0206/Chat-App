from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope["user"] = AnonymousUser()

        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)

        token_list = query_params.get("token")

        if token_list:
            token = token_list[0]
            scope["user"] = await self.get_user_from_token(token)

        return await self.app(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        jwt_authentication = JWTAuthentication()

        try:
            validated_token = jwt_authentication.get_validated_token(token)
            user = jwt_authentication.get_user(validated_token)
            return user
        except Exception:
            return AnonymousUser()


def JWTAuthMiddlewareStack(app):
    return JWTAuthMiddleware(app)