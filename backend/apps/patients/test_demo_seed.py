"""The demo clinic seeder, which is what anyone testing the system starts from."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.billing.models import Department
from apps.orders.selectors import worklist
from apps.patients.models import Patient, Visit, VisitStatus
from apps.pharmacy.models import StockItem


def test_it_refuses_to_invent_patients_on_a_production_database(db):
    # DEBUG is off during tests, which is the same guard production has.
    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_demo_clinic")


@override_settings(DEBUG=True)
def test_it_puts_something_in_every_queue(db):
    call_command("seed_demo_clinic")

    assert Patient.objects.count() >= 8
    assert Visit.objects.filter(status=VisitStatus.AWAITING_TRIAGE).exists()
    assert Visit.objects.filter(status=VisitStatus.AWAITING_CONSULTATION).exists()
    assert Visit.objects.filter(status=VisitStatus.COMPLETED).exists()

    # Every department has work, and the shelf has something on it.
    assert worklist(Department.LABORATORY).exists()
    assert worklist(Department.PHARMACY).exists()
    assert worklist(Department.PROCEDURE).exists()
    assert StockItem.objects.get(service__code="PHA-PARA").quantity_in_stock > 0


@override_settings(DEBUG=True)
def test_running_it_twice_does_not_double_the_clinic(db):
    call_command("seed_demo_clinic")
    patients = Patient.objects.count()
    visits = Visit.objects.count()

    call_command("seed_demo_clinic")

    assert Patient.objects.count() == patients
    assert Visit.objects.count() == visits


@override_settings(DEBUG=True)
def test_the_days_trading_is_readable_as_revenue_and_cost(db):
    from decimal import Decimal

    from django.utils import timezone

    from apps.reporting import reports

    call_command("seed_demo_clinic")
    today = timezone.localdate()

    figures = reports.summary(today, today)

    assert figures["revenue"] > Decimal("0.00")
    assert figures["cost"] > Decimal("0.00")
    assert figures["profit"] == figures["revenue"] - figures["cost"]
