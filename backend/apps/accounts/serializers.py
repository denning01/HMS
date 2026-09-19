"""What the API says about the signed-in user."""

from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The client needs the name to greet, and the roles to decide navigation.

    Roles are sent as a plain list because every screen the client gates is
    gated on role membership, exactly as the server gates it.
    """

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    roles = serializers.SerializerMethodField()
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "roles", "primary_role", "is_superuser"]

    def get_roles(self, user):
        return sorted(user.role_names)

    def get_primary_role(self, user):
        role = user.primary_role
        return role.value if role else None


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)
