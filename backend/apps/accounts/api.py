"""Authentication for the React client.

Session cookies, not tokens: the client is served from the same origin, so the
cookie is set httpOnly and never has to be stored or attached by JavaScript.
"""

from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Role, User
from .permissions import HasAnyRole
from .serializers import (
    LoginSerializer,
    NewPasswordSerializer,
    StaffSerializer,
    UserSerializer,
)

# Accounts and roles are the Administrator's alone, as the matrix has it.
ADMIN_ONLY = (Role.ADMINISTRATOR,)


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Hand the client a CSRF cookie before it posts anything.

    Session authentication still requires the CSRF token, and the client cannot
    be sent one in the page because there is no server-rendered page any more.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class StaffListView(generics.ListCreateAPIView):
    """The staff register: who holds an account, and which roles they hold."""

    permission_classes = [HasAnyRole]
    roles = ADMIN_ONLY
    serializer_class = StaffSerializer

    def get_queryset(self):
        term = self.request.query_params.get("q", "").strip()
        staff = User.objects.prefetch_related("groups")

        if term:
            staff = staff.filter(
                Q(username__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(staff_id__icontains=term)
            )
        return staff

    def create(self, request, *args, **kwargs):
        password = NewPasswordSerializer(data=request.data)
        password.is_valid(raise_exception=True)

        form = self.get_serializer(
            data=request.data, context={"password": password.validated_data["password"]}
        )
        form.is_valid(raise_exception=True)
        form.save()

        return Response(form.data, status=status.HTTP_201_CREATED)


class StaffDetailView(generics.RetrieveUpdateAPIView):
    """Change a colleague's details, their roles, or whether they can sign in."""

    permission_classes = [HasAnyRole]
    roles = ADMIN_ONLY
    serializer_class = StaffSerializer
    queryset = User.objects.prefetch_related("groups")

    def update(self, request, *args, **kwargs):
        user = self.get_object()

        # An administrator who can remove their own last way back in is one
        # locked out of the system by a screen that should have said no.
        if user == request.user:
            losing_admin = (
                "roles" in request.data
                and Role.ADMINISTRATOR.value not in request.data.get("roles", [])
            )
            if losing_admin or request.data.get("is_active") is False:
                return Response(
                    {"detail": "You cannot remove your own access — ask another administrator."},
                    status=status.HTTP_409_CONFLICT,
                )

        return super().update(request, *args, **kwargs)


class ResetPasswordView(APIView):
    """Set a colleague's password, for the ones that are always forgotten."""

    permission_classes = [HasAnyRole]
    roles = ADMIN_ONLY

    def post(self, request, pk):
        user = generics.get_object_or_404(User, pk=pk)

        form = NewPasswordSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        user.set_password(form.validated_data["password"])
        user.save(update_fields=["password"])

        return Response(status=status.HTTP_204_NO_CONTENT)
