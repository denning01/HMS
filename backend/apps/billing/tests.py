"""Tests for the price list."""

from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.billing.management.commands.seed_services import SERVICES
from apps.billing.models import Department, Service


@pytest.fixture
def services(db):
    call_command("seed_services")


def test_seed_services_creates_the_starting_catalogue(services):
    # Counted from the seeder's own list rather than written out here: the
    # catalogue grows as departments are built, and a number in two places is
    # a test that breaks on a price list change rather than on a bug.
    assert Service.objects.count() == len(SERVICES)
    assert Service.objects.filter(department=Department.LABORATORY).count() == sum(
        1 for row in SERVICES if row[2] == Department.LABORATORY
    )


def test_seed_services_is_idempotent(services):
    call_command("seed_services")

    assert Service.objects.count() == len(SERVICES)


def test_seeding_again_does_not_overwrite_a_price_the_clinic_has_changed(services):
    """A later deploy must not reset prices back to the indicative defaults."""
    consultation = Service.objects.get(code="CONS-GEN")
    consultation.unit_price = Decimal("750.00")
    consultation.save()

    call_command("seed_services")

    consultation.refresh_from_db()
    assert consultation.unit_price == Decimal("750.00")


def test_service_codes_are_unique(services):
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        Service.objects.create(
            code="CONS-GEN",
            name="Duplicate",
            department=Department.CONSULTATION,
            unit_price=Decimal("100.00"),
        )


def test_retired_services_stay_in_the_catalogue(services):
    """Old bills must still read correctly, so retiring is a flag, not a delete."""
    service = Service.objects.get(code="LAB-MPS")
    service.is_active = False
    service.save()

    assert Service.objects.filter(code="LAB-MPS").exists()
    assert Service.objects.filter(is_active=True).count() == len(SERVICES) - 1
