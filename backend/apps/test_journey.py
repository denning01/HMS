"""One patient, all the way through.

Every other test file asks one module whether it enforces its own rules. This
one asks whether the modules hand off to each other: that what Registration
opens is what Billing settles, that what the doctor orders is what the lab sees,
that what the pharmacy gives out comes off the shelf the owner's report costs,
and that the visit cannot be closed until all of it is accounted for.

It is deliberately written as a walkthrough rather than as small cases. When it
fails, the line it fails on is the step of the patient journey that broke.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.pharmacy.models import StockItem
from apps.pharmacy.services import receive_stock


@pytest.fixture
def clinic(db):
    call_command("seed_roles")
    call_command("seed_services")
    call_command("seed_lab_tests")
    call_command("seed_stock_items")

    # A delivery, so the pharmacy has something to dispense and the procedure
    # room something to reach for.
    expiry = timezone.localdate() + timedelta(days=365)
    receive_stock(
        StockItem.objects.get(service__code="PHA-PARA"),
        quantity=500, unit_cost=Decimal("3.00"), expires_on=expiry, batch_number="PB-1",
    )
    receive_stock(
        StockItem.objects.get(name="Gauze swabs"),
        quantity=100, unit_cost=Decimal("12.00"), expires_on=expiry, batch_number="G-1",
    )


def staff(username, role, first_name, last_name):
    user = User.objects.create_user(
        username=username, password="pw-for-tests-only",
        first_name=first_name, last_name=last_name,
    )
    user.groups.add(Group.objects.get(name=role.value))
    return user


@pytest.fixture
def team(clinic):
    return {
        "reception": staff("reception", Role.RECEPTIONIST, "Ruth", "Wanjiku"),
        "triage": staff("triage", Role.TRIAGE_NURSE, "Tom", "Mwangi"),
        "doctor": staff("doctor", Role.DOCTOR, "Dan", "Kiprop"),
        "lab": staff("lab", Role.LAB_TECHNICIAN, "Lena", "Achieng"),
        "pharmacy": staff("pharmacy", Role.PHARMACIST, "Peter", "Muturi"),
        "room": staff("room", Role.PROCEDURE_NURSE, "Pauline", "Cherono"),
        "cashier": staff("cashier", Role.CASHIER, "Caleb", "Omondi"),
        "finance": staff("finance", Role.FINANCE_MANAGER, "Faith", "Mutiso"),
    }


def post(client, url, payload=None):
    return client.post(url, payload or {}, content_type="application/json")


def service_id(client, department, code):
    rows = client.get(reverse("api_services") + f"?department={department}").json()
    return next(row["id"] for row in rows if row["code"] == code)


def pay_everything(client, invoice_id, method="cash"):
    invoice = client.get(reverse("api_invoice", args=[invoice_id])).json()
    unpaid = [line["id"] for line in invoice["lines"] if line["status"] == "unpaid"]
    if not unpaid:
        return None
    return post(
        client, reverse("api_pay", args=[invoice_id]), {"lines": unpaid, "method": method}
    ).json()


def test_one_patient_all_the_way_through(team, client):
    # --- the front desk -----------------------------------------------------
    client.force_login(team["reception"])
    patient = post(
        client,
        reverse("api_patients"),
        {
            "first_name": "Amina", "last_name": "Hassan",
            "date_of_birth": "1992-03-14", "sex": "F",
            "phone_number": "0722000111", "residence": "Kilimani",
            "next_of_kin_name": "Yusuf Hassan", "next_of_kin_relationship": "spouse",
            "next_of_kin_phone": "0722000112",
        },
    ).json()
    assert patient["mrn"].startswith("MRN")

    visit = post(
        client, reverse("api_start_visit", args=[patient["id"]]),
        {"billing_mode": "pay_per_service"},
    ).json()
    visit_id = visit["id"]
    assert visit["status"] == "awaiting_triage"

    # --- triage -------------------------------------------------------------
    client.force_login(team["triage"])
    assert [row["id"] for row in client.get(reverse("api_triage_queue")).json()] == [visit_id]

    vitals = post(
        client,
        reverse("api_vitals", args=[visit_id]),
        {
            "systolic_bp": 118, "diastolic_bp": 76, "pulse_rate": 92, "temperature": "38.9",
            "spo2": 97, "respiratory_rate": 18, "weight": "64.50", "height": "1.63",
            "presenting_complaint": "Fever and headache for three days",
        },
    ).json()
    # A fever moves her up the doctor's queue without anyone deciding to.
    assert vitals["visit"]["is_urgent"] is True
    assert client.get(reverse("api_triage_queue")).json() == []

    # --- the consulting room ------------------------------------------------
    client.force_login(team["doctor"])
    queue = client.get(reverse("api_consultation_queue")).json()
    assert queue[0]["id"] == visit_id
    assert queue[0]["vitals"]["blood_pressure"] == "118/76"

    post(
        client,
        reverse("api_consultation", args=[visit_id]),
        {
            "chief_complaint": "Fever and headache for three days",
            "history_of_presenting_illness": "Gradual onset, no vomiting.",
            "examination_findings": "Febrile, chest clear. Small laceration, left forearm.",
        },
    )

    smear = post(
        client,
        reverse("api_place_order", args=[visit_id]),
        {"service": service_id(client, "laboratory", "LAB-MPS"),
         "clinical_details": "Fever, query malaria"},
    ).json()
    drug = post(
        client,
        reverse("api_place_order", args=[visit_id]),
        {
            "service": service_id(client, "pharmacy", "PHA-PARA"), "quantity": 12,
            "directions": {"dosage": "1 tablet", "frequency": "three times a day",
                           "duration": "4 days", "instructions": "after food"},
        },
    ).json()
    dressing = post(
        client,
        reverse("api_place_order", args=[visit_id]),
        {"service": service_id(client, "procedure", "PRO-DRESS"),
         "clinical_details": "Clean and dress the laceration"},
    ).json()

    record = client.get(reverse("api_consultation", args=[visit_id])).json()
    invoice_id = record["invoice"]["id"]
    # Consultation 500 + smear 300 + 12 paracetamol 120 + dressing 400.
    assert Decimal(record["invoice"]["total"]) == Decimal("1320.00")
    assert all(order["is_cleared"] is False for order in record["orders"])

    # Nothing may happen anywhere until the money is in.
    client.force_login(team["lab"])
    assert post(client, reverse("api_lab_collect", args=[smear["id"]])).status_code == 409
    client.force_login(team["pharmacy"])
    assert post(client, reverse("api_dispense", args=[drug["id"]])).status_code == 409
    client.force_login(team["room"])
    assert post(client, reverse("api_perform_procedure", args=[dressing["id"]])).status_code == 409

    # --- the till -----------------------------------------------------------
    client.force_login(team["cashier"])
    till = client.get(reverse("api_till")).json()
    assert [row["id"] for row in till] == [invoice_id]

    receipt = pay_everything(client, invoice_id, method="mpesa")
    assert Decimal(receipt["amount"]) == Decimal("1320.00")
    assert client.get(reverse("api_till")).json() == []

    # --- the laboratory -----------------------------------------------------
    client.force_login(team["lab"])
    bench = client.get(reverse("api_lab_worklist")).json()
    assert [row["id"] for row in bench["ready"]] == [smear["id"]]
    assert bench["ready"][0]["specimen"] == "blood"

    post(client, reverse("api_lab_collect", args=[smear["id"]]))
    post(
        client, reverse("api_lab_result", args=[smear["id"]]),
        {"findings": "Plasmodium falciparum seen, ++", "is_abnormal": True},
    )

    # Unreleased, the doctor sees nothing.
    client.force_login(team["doctor"])
    record = client.get(reverse("api_consultation", args=[visit_id])).json()
    assert next(o for o in record["orders"] if o["id"] == smear["id"])["result"] is None

    client.force_login(team["lab"])
    post(client, reverse("api_lab_release", args=[smear["id"]]))

    # --- the pharmacy -------------------------------------------------------
    client.force_login(team["pharmacy"])
    counter = client.get(reverse("api_dispensing")).json()
    assert counter["ready"][0]["prescription"]["directions"] == (
        "1 tablet, three times a day, 4 days — after food"
    )

    dispensed = post(client, reverse("api_dispense", args=[drug["id"]])).json()
    assert dispensed["movements"][0]["quantity"] == -12
    assert StockItem.objects.get(service__code="PHA-PARA").quantity_in_stock == 488

    # --- the procedure room -------------------------------------------------
    client.force_login(team["room"])
    gauze = StockItem.objects.get(name="Gauze swabs")
    done = post(
        client,
        reverse("api_perform_procedure", args=[dressing["id"]]),
        {"notes": "Cleaned with saline and redressed", "consumables": [{"item": gauze.pk, "quantity": 4}]},
    ).json()
    assert done["record"]["consumable_cost"] == "48.00"
    assert gauze.quantity_in_stock == 96

    # --- back to the doctor -------------------------------------------------
    client.force_login(team["doctor"])
    record = client.get(reverse("api_consultation", args=[visit_id])).json()
    by_id = {order["id"]: order for order in record["orders"]}
    assert by_id[smear["id"]]["result"]["findings"].startswith("Plasmodium")
    assert by_id[drug["id"]]["prescription"]["is_dispensed"] is True
    assert by_id[dressing["id"]]["procedure"]["notes"].startswith("Cleaned")

    post(
        client,
        reverse("api_consultation", args=[visit_id]),
        {"chief_complaint": "Fever and headache for three days",
         "diagnosis": "Malaria", "icd10_code": "B50",
         "treatment_plan": "Artemether-lumefantrine; review in three days"},
    )

    follow_up = post(
        client,
        reverse("api_appointments"),
        {
            "patient": patient["id"],
            "scheduled_for": (timezone.now() + timedelta(days=3)).isoformat(),
            "department": "consultation", "reason": "Review after treatment",
        },
    ).json()
    assert follow_up["status"] == "booked"

    closed = post(client, reverse("api_close_visit", args=[visit_id]))
    assert closed.status_code == 200
    assert closed.json()["status"] == "completed"
    assert client.get(reverse("api_consultation_queue")).json() == []

    # --- what the owner sees ------------------------------------------------
    client.force_login(team["finance"])
    report = client.get(reverse("api_revenue_report")).json()
    assert Decimal(report["revenue"]) == Decimal("1320.00")
    # 12 tablets bought at 3.00, 4 swabs at 12.00.
    assert Decimal(report["cost"]) == Decimal("84.00")
    assert Decimal(report["profit"]) == Decimal("1236.00")

    departments = {row["key"]: Decimal(row["total"]) for row in report["by_department"]}
    assert departments == {
        "consultation": Decimal("500.00"),
        "laboratory": Decimal("300.00"),
        "pharmacy": Decimal("120.00"),
        "procedure": Decimal("400.00"),
    }


def test_the_next_visit_shows_the_doctor_what_happened_last_time(team, client):
    """The point of one patient record: the history is there without asking."""
    test_one_patient_all_the_way_through(team, client)

    client.force_login(team["reception"])
    patient_id = client.get(reverse("api_patients") + "?q=Amina").json()[0]["id"]
    second = post(
        client, reverse("api_start_visit", args=[patient_id]), {"billing_mode": "pay_per_service"}
    ).json()

    client.force_login(team["doctor"])
    record = client.get(reverse("api_consultation", args=[second["id"]])).json()

    assert len(record["history"]) == 1
    previous = record["history"][0]
    assert previous["diagnosis"] == "Malaria"
    assert previous["doctor_name"] == "Dan Kiprop"
    assert "Malaria parasite smear" in previous["orders"]
    assert previous["results"][0]["findings"].startswith("Plasmodium")


def test_a_consolidated_visit_is_never_held_up_for_payment(team, client):
    """The staff and corporate path: every department acts at once, and the
    bill is settled before the visit can close."""
    client.force_login(team["reception"])
    patient = post(
        client,
        reverse("api_patients"),
        {"first_name": "Staff", "last_name": "Member", "date_of_birth": "1988-01-01", "sex": "M"},
    ).json()
    visit = post(
        client, reverse("api_start_visit", args=[patient["id"]]), {"billing_mode": "consolidated"}
    ).json()

    client.force_login(team["triage"])
    post(
        client,
        reverse("api_vitals", args=[visit["id"]]),
        {"systolic_bp": 120, "diastolic_bp": 80, "pulse_rate": 70, "temperature": "36.8",
         "spo2": 99, "respiratory_rate": 16, "weight": "80.00", "height": "1.80"},
    )

    client.force_login(team["doctor"])
    post(client, reverse("api_consultation", args=[visit["id"]]), {"chief_complaint": "Cough"})
    order = post(
        client,
        reverse("api_place_order", args=[visit["id"]]),
        {"service": service_id(client, "laboratory", "LAB-MPS")},
    ).json()
    assert order["is_cleared"] is True

    client.force_login(team["lab"])
    collected = post(client, reverse("api_lab_collect", args=[order["id"]]))
    assert collected.status_code == 200

    post(client, reverse("api_lab_result", args=[order["id"]]), {"findings": "No parasites seen"})
    post(client, reverse("api_lab_release", args=[order["id"]]))

    # The work was never held up, and the money is still owed.
    client.force_login(team["doctor"])
    refused = post(client, reverse("api_close_visit", args=[visit["id"]]))
    assert refused.status_code == 409
    assert "still owing" in refused.json()["detail"]

    client.force_login(team["cashier"])
    record_invoice = client.get(reverse("api_till")).json()[0]["id"]
    pay_everything(client, record_invoice)

    client.force_login(team["doctor"])
    assert post(client, reverse("api_close_visit", args=[visit["id"]])).status_code == 200
