"""Tests for the role system and dashboard routing."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.models import Role, User


@pytest.fixture
def roles(db):
    call_command("seed_roles")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(username="jane", password="pw-for-tests-only")


def test_seed_roles_creates_all_nine(roles):
    assert Group.objects.count() == 9
    assert set(Group.objects.values_list("name", flat=True)) == {r.value for r in Role}


def test_seed_roles_is_idempotent(roles):
    call_command("seed_roles")
    assert Group.objects.count() == 9


def test_user_can_hold_several_roles(roles, staff_user):
    """The specification requires one account to carry more than one role."""
    for role in (Role.RECEPTIONIST, Role.CASHIER):
        staff_user.groups.add(Group.objects.get(name=role.value))

    assert staff_user.has_role(Role.RECEPTIONIST)
    assert staff_user.has_role(Role.CASHIER)
    assert not staff_user.has_role(Role.DOCTOR)
    assert staff_user.role_names == {"Receptionist", "Cashier"}


def test_primary_role_follows_priority_order(roles, staff_user):
    """Cashier outranks Receptionist, so that is the dashboard they land on."""
    for role in (Role.RECEPTIONIST, Role.CASHIER):
        staff_user.groups.add(Group.objects.get(name=role.value))

    assert staff_user.primary_role == Role.CASHIER


def test_user_with_no_role_has_no_primary_role(staff_user):
    assert staff_user.primary_role is None


def test_superuser_holds_every_role(db):
    admin = User.objects.create_superuser(username="root", password="pw-for-tests-only")

    assert all(admin.has_role(role) for role in Role)
    assert admin.primary_role == Role.ADMINISTRATOR


def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboard"))

    assert response.status_code == 302
    assert reverse("login") in response["Location"]


def test_dashboard_shows_modules_for_the_users_role(roles, staff_user, client):
    staff_user.groups.add(Group.objects.get(name=Role.PHARMACIST.value))
    client.force_login(staff_user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"Dispensing queue" in response.content
    assert b"Stock" in response.content
    # A pharmacist must not be offered another department's screens.
    assert b"Point of sale" not in response.content


def test_dashboard_warns_when_no_role_assigned(staff_user, client):
    client.force_login(staff_user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"No role has been assigned" in response.content


def test_login_redirects_to_dashboard(roles, staff_user, client):
    response = client.post(
        reverse("login"),
        {"username": "jane", "password": "pw-for-tests-only"},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("dashboard")
