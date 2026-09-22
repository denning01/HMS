"""What the API says about the signed-in user, and about staff accounts."""

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Role, User


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


class StaffSerializer(serializers.ModelSerializer):
    """A staff account as the administrator manages it.

    Roles are group names, not ids: the specification's permissions matrix is
    written in role names, and an administrator reading this screen should see
    the same words they read in the matrix.
    """

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=Role.choices), required=False
    )
    last_login = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "full_name",
            "phone_number", "staff_id", "roles", "is_active", "is_superuser",
            "last_login", "date_joined",
        ]
        read_only_fields = ["id", "is_superuser", "last_login", "date_joined"]

    def to_representation(self, user):
        data = super().to_representation(user)
        data["roles"] = sorted(user.role_names)
        return data

    def validate_username(self, value):
        taken = User.objects.filter(username__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def _apply_roles(self, user, role_names):
        """Replace the account's roles wholesale — the screen sends the full set."""
        groups = Group.objects.filter(name__in=role_names)
        user.groups.set(groups)

    def create(self, validated_data):
        role_names = validated_data.pop("roles", [])
        password = self.context["password"]

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        self._apply_roles(user, role_names)
        return user

    def update(self, user, validated_data):
        role_names = validated_data.pop("roles", None)

        for field, value in validated_data.items():
            setattr(user, field, value)
        user.save()

        if role_names is not None:
            self._apply_roles(user, role_names)
        return user


class NewPasswordSerializer(serializers.Serializer):
    """A password the administrator sets for someone else.

    Run through Django's own validators, so the weak one an administrator would
    otherwise pick for a colleague in a hurry is refused here and not later.
    """

    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})

    def validate_password(self, value):
        validate_password(value)
        return value
