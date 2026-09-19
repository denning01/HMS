"""Authentication for the React client.

Session cookies, not tokens: the client is served from the same origin, so the
cookie is set httpOnly and never has to be stored or attached by JavaScript.
"""

from django.contrib.auth import authenticate, login, logout
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, UserSerializer


class LoginView(APIView):
    """Sign in and start a session."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        form = LoginSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=form.validated_data["username"],
            password=form.validated_data["password"],
        )
        if user is None:
            # One message for both wrong username and wrong password, so the
            # form cannot be used to find out which accounts exist.
            return Response(
                {"detail": "That username and password do not match an account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Who is signed in — the client calls this on load to restore the session."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)
