"""Fill a development database with a clinic that has been trading.

For walking the system before it goes live: a register of patients, stock on the
shelf, and a day's worth of visits at every stage of the journey, so every queue
and every report has something in it.

Development only — it refuses to run with DEBUG off, because a production
database should never be given invented patients.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.appointments.services import book
from apps.billing.models import Service
from apps.billing.services import take_payment
from apps.consultation.services import open_note
from apps.laboratory.services import collect_specimen, record_result, release_result
from apps.orders.services import place_order
from apps.patients.models import BillingMode, Patient, Sex, Visit, VisitStatus
from apps.pharmacy.models import StockItem
from apps.pharmacy.services import dispense, receive_stock
from apps.procedures.services import perform
from apps.triage.models import Vitals

PATIENTS = [
    ("Amina", "Hassan", "1992-03-14", Sex.FEMALE, "0722000111", "Kilimani"),
    ("Joseph", "Kariuki", "1975-06-02", Sex.MALE, "0733111222", "Kawangware"),
    ("Grace", "Wambui", "1999-09-09", Sex.FEMALE, "0711333444", "Kileleshwa"),
    ("Brian", "Kemboi", "1980-05-20", Sex.MALE, "0700555666", "Langata"),
    ("Mercy", "Chebet", "1988-07-03", Sex.FEMALE, "0755777888", "Westlands"),
    ("Samuel", "Kiptoo", "1991-11-02", Sex.MALE, "0766999000", "Embakasi"),
    ("Hellen", "Atieno", "1996-04-18", Sex.FEMALE, "0744222333", "South B"),
    ("Daniel", "Mutua", "2015-02-11", Sex.MALE, "0722444555", "Buruburu"),
]

VITALS = {
    "systolic_bp": 122, "diastolic_bp": 78, "pulse_rate": 84, "temperature": Decimal("37.2"),
    "spo2": 98, "respiratory_rate": 17, "weight": Decimal("68.00"), "height": Decimal("1.68"),
}


class Command(BaseCommand):
    help = "Create demo patients, stock and a day of visits (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Refusing to run with DEBUG off — this invents patients and payments."
            )

        for command in ("seed_roles", "seed_services", "seed_lab_tests", "seed_stock_items"):
            call_command(command)

        staff = self._staff()
        patients = self._patients()
        self._stock(staff)

        self._waiting_for_triage(patients[0], staff)
        self._waiting_for_the_doctor(patients[1], staff)
        self._waiting_at_the_till(patients[2], staff)
        self._waiting_in_the_lab(patients[3], staff)
        self._waiting_at_the_pharmacy(patients[4], staff)
        self._finished_and_paid(patients[5], staff)
        self._booked_for_later(patients[6], staff)

        self.stdout.write(
            self.style.SUCCESS(
                f"{Patient.objects.count()} patients, "
                f"{Visit.objects.filter(status__in=['awaiting_triage', 'awaiting_consultation', 'in_consultation']).count()} "
                "open visits, and something in every queue."
            )
        )

    # --- the people ---------------------------------------------------------

    def _staff(self):
        call_command("seed_demo_staff")
        by_role = {}
        for user in User.objects.prefetch_related("groups"):
            for role in user.role_names:
                by_role.setdefault(role, user)
        return by_role

    def _patients(self):
        created = []
        for first, last, born, sex, phone, area in PATIENTS:
            # Matched rather than get_or_create: a development database that has
            # been walked through by hand may already hold two of the same name,
            # and a seeder is not the place to refuse over it.
            patient = Patient.objects.filter(
                first_name=first, last_name=last, date_of_birth=born
            ).first()
            if patient is None:
                patient = Patient.objects.create(
                    first_name=first, last_name=last, date_of_birth=born,
                    sex=sex, phone_number=phone, residence=area,
                )
            created.append(patient)
        return created

    def _stock(self, staff):
        pharmacist = staff.get(Role.PHARMACIST.value)
        expiry = timezone.localdate() + timedelta(days=300)

        deliveries = [
            ("PHA-PARA", 500, "3.00"),
            ("PHA-AMOX", 200, "9.00"),
            ("PHA-ORS", 100, "18.00"),
        ]
        for code, quantity, cost in deliveries:
            item = StockItem.objects.filter(service__code=code).first()
            if item and item.quantity_in_stock == 0:
                receive_stock(
                    item, quantity=quantity, unit_cost=Decimal(cost),
                    expires_on=expiry, batch_number=f"{code}-DEMO", supplier="Dawa Ltd",
                    received_by=pharmacist,
                )

        for name, quantity, cost in [("Gauze swabs", 100, "12.00"), ("Examination gloves", 200, "20.00")]:
            item = StockItem.objects.filter(name=name).first()
            if item and item.quantity_in_stock == 0:
                receive_stock(
                    item, quantity=quantity, unit_cost=Decimal(cost), expires_on=expiry,
                    batch_number=f"{name[:3].upper()}-DEMO", received_by=pharmacist,
                )

    # --- one patient at each stage ------------------------------------------

    def _open_visit(self, patient, staff, mode=BillingMode.PAY_PER_SERVICE):
        # Any visit at all, not only an open one: running this twice should give
        # the same clinic back, not a second attendance for everybody who has
        # already been through.
        if patient.visits.exists():
            return None

        from apps.billing.services import charge_consultation

        visit = Visit.objects.create(
            patient=patient, billing_mode=mode, created_by=staff.get(Role.RECEPTIONIST.value)
        )
        charge_consultation(visit, ordered_by=staff.get(Role.RECEPTIONIST.value))
        return visit

    def _take_vitals(self, visit, staff):
        Vitals.objects.create(visit=visit, recorded_by=staff.get(Role.TRIAGE_NURSE.value), **VITALS)
        visit.status = VisitStatus.AWAITING_CONSULTATION
        visit.save(update_fields=["status"])

    def _settle(self, visit, method="cash", staff=None):
        unpaid = [line.pk for line in visit.invoice.lines.filter(status="unpaid")]
        if unpaid:
            take_payment(
                invoice=visit.invoice, line_ids=unpaid, method=method,
                received_by=(staff or {}).get(Role.CASHIER.value),
            )

    def _waiting_for_triage(self, patient, staff):
        self._open_visit(patient, staff)

    def _waiting_for_the_doctor(self, patient, staff):
        visit = self._open_visit(patient, staff)
        if visit:
            self._take_vitals(visit, staff)

    def _waiting_at_the_till(self, patient, staff):
        visit = self._open_visit(patient, staff)
        if not visit:
            return
        self._take_vitals(visit, staff)
        doctor = staff.get(Role.DOCTOR.value)
        open_note(visit, doctor=doctor)
        place_order(
            visit=visit, service=Service.objects.get(code="LAB-MPS"),
            clinical_details="Fever, query malaria", ordered_by=doctor,
        )

    def _waiting_in_the_lab(self, patient, staff):
        visit = self._open_visit(patient, staff)
        if not visit:
            return
        self._take_vitals(visit, staff)
        doctor = staff.get(Role.DOCTOR.value)
        open_note(visit, doctor=doctor)
        order = place_order(
            visit=visit, service=Service.objects.get(code="LAB-UA"),
            clinical_details="Burning on passing urine", ordered_by=doctor,
        )
        self._settle(visit, staff=staff)
        order.refresh_from_db()
        collect_specimen(order, collected_by=staff.get(Role.LAB_TECHNICIAN.value))

    def _waiting_at_the_pharmacy(self, patient, staff):
        visit = self._open_visit(patient, staff)
        if not visit:
            return
        self._take_vitals(visit, staff)
        doctor = staff.get(Role.DOCTOR.value)
        open_note(visit, doctor=doctor)
        place_order(
            visit=visit, service=Service.objects.get(code="PHA-AMOX"), quantity=15,
            ordered_by=doctor,
        )
        place_order(
            visit=visit, service=Service.objects.get(code="PRO-INJ"),
            clinical_details="First dose by injection", ordered_by=doctor,
        )
        self._settle(visit, method="mpesa", staff=staff)

    def _finished_and_paid(self, patient, staff):
        visit = self._open_visit(patient, staff)
        if not visit:
            return
        self._take_vitals(visit, staff)
        doctor = staff.get(Role.DOCTOR.value)
        note, _ = open_note(visit, doctor=doctor)
        note.chief_complaint = "Headache for two days"
        note.diagnosis = "Tension headache"
        note.treatment_plan = "Paracetamol, review if no better in three days"
        note.save()

        drug = place_order(
            visit=visit, service=Service.objects.get(code="PHA-PARA"), quantity=12,
            ordered_by=doctor,
        )
        from apps.pharmacy.services import attach_prescription

        attach_prescription(
            drug, dosage="1 tablet", frequency="three times a day",
            duration="4 days", instructions="after food",
        )
        test = place_order(
            visit=visit, service=Service.objects.get(code="LAB-RBS"), ordered_by=doctor
        )
        dressing = place_order(
            visit=visit, service=Service.objects.get(code="PRO-DRESS"), ordered_by=doctor
        )

        self._settle(visit, staff=staff)
        for order in (drug, test, dressing):
            order.refresh_from_db()

        technician = staff.get(Role.LAB_TECHNICIAN.value)
        collect_specimen(test, collected_by=technician)
        record_result(test, findings="6.1 mmol/L", recorded_by=technician)
        release_result(test, released_by=technician)

        dispense(drug, dispensed_by=staff.get(Role.PHARMACIST.value))

        gauze = StockItem.objects.filter(name="Gauze swabs").first()
        perform(
            dressing,
            notes="Cleaned and redressed; patient tolerated it well",
            consumables=[(gauze.pk, 4)] if gauze else (),
            performed_by=staff.get(Role.PROCEDURE_NURSE.value),
        )

        visit.refresh_from_db()
        visit.close()

    def _booked_for_later(self, patient, staff):
        when = timezone.now() + timedelta(days=2)
        already = patient.appointments.filter(status__in=["booked", "confirmed"]).exists()
        if not already:
            book(
                patient=patient, scheduled_for=when, department="consultation",
                reason="Review after treatment",
                created_by=staff.get(Role.RECEPTIONIST.value),
            )
