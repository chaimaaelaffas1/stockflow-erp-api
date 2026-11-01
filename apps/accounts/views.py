from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
)

from .serializers import MeSerializer


@extend_schema(
    tags=["Authentication"],
    summary="Obtain JWT Tokens",
    description="""
    Authenticate a user using their email and password.

    If the credentials are valid, the API returns an access token
    and a refresh token.

    The access token must be included in the Authorization header
    when accessing protected endpoints.

    Only active users are allowed to authenticate.
    """,
)
class LoginView(TokenObtainPairView):

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

@extend_schema(
    tags=["Authentication"],
    summary="Retrieve Current User Profile",
    description="""
    Retrieve the profile information of the currently authenticated user.

    The response contains the current user's account information,
    including their assigned role.
    """,
)

class MeView(RetrieveAPIView):

    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

@extend_schema(
    tags=["Authentication"],
    summary="Logout User",
    description="""
    Log out the authenticated user by blacklisting their refresh token.

    Request body:
    - refresh: The refresh token to invalidate.

    Returns HTTP 204 when the token is successfully blacklisted.

    Returns HTTP 400 if the refresh token is missing or invalid.
    """,
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "refresh": {
                    "type": "string",
                    "description": "The refresh token to blacklist.",
                },
            },
            "required": ["refresh"],
        }
    },
)
class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "The refresh token is required.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

        except TokenError:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid refresh token.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
