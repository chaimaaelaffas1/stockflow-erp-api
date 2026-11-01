from django.urls import include, path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.viewsets import UserViewSet

from .views import LoginView, LogoutView, MeView


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Refresh Access Token",
        description="""
        Generate a new access token using a valid refresh token.

        Request body:
        - refresh: A valid JWT refresh token.

        If refresh token rotation is enabled, a new refresh token
        may also be returned.

        Returns HTTP 401 if the refresh token is invalid,
        expired, or blacklisted.
        """,
    )
)
class DocumentedTokenRefreshView(TokenRefreshView):
    pass


router = DefaultRouter()
router.register("users", UserViewSet, basename="users")

urlpatterns = [
    path("auth/token/", LoginView.as_view(), name="token_obtain_pair"),
    path(
        "auth/token/refresh/",
        DocumentedTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("auth/me/", MeView.as_view(), name="auth_me"),
    path("", include(router.urls)),
]
