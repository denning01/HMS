"""The consultation note and the doctor's queue over the wire."""

from rest_framework import serializers

from apps.laboratory.serializers import LabResultSerializer
from apps.orders.serializers import OrderSerializer, PlaceOrderSerializer
from apps.pharmacy.serializers import DirectionsSerializer, PrescriptionSerializer
from apps.procedures.serializers import ProcedureRecordSerializer
from apps.patients.serializers import VisitSerializer
from apps.triage.serializers import VitalsSerializer

from .models import Consultation

# The history sections only some patients are asked. Blanked on the way in for
# everyone else, so an answer is never stored against a patient it does not
# apply to — which is what the specification asks for by showing them
# conditionally rather than making them mandatory.
CONDITIONAL_HISTORY_FIELDS = ["gynaecological_history", "obstetric_history"]


class ConsultationSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    applies_gynae_obstetric_history = serializers.BooleanField(read_only=True)

    class Meta:
        model = Consultation
        fields = [
            "id", "chief_complaint", "history_of_presenting_illness",
            "past_medical_history", "drug_reactions",
            "gynaecological_history", "obstetric_history", "family_history",
            "examination_findings", "diagnosis", "icd10_code", "treatment_plan",
            "doctor_name", "applies_gynae_obstetric_history",
            "started_at", "updated_at",
        ]
        read_only_fields = ["id", "started_at", "updated_at"]

    def validate_chief_complaint(self, value):
        # The note is created the moment the doctor starts, so it can exist
        # unwritten; what it must never do is be saved with the complaint erased.
        if not value.strip():
            raise serializers.ValidationError("Record what the patient came in for.")
        return value

    def get_doctor_name(self, consultation):
        user = consultation.doctor
        if user is None:
            return None
        return user.get_full_name() or user.username


class ConsultationQueueSerializer(VisitSerializer):
    """A row in the doctor's queue: who is waiting, why, and for how long."""

    vitals = serializers.SerializerMethodField()
    urgency_reasons = serializers.SerializerMethodField()
    has_note = serializers.SerializerMethodField()
    open_orders = serializers.SerializerMethodField()
    results_ready = serializers.SerializerMethodField()

    class Meta(VisitSerializer.Meta):
        fields = VisitSerializer.Meta.fields + [
            "vitals", "urgency_reasons", "has_note", "open_orders", "results_ready",
        ]

    def get_vitals(self, visit):
        vitals = getattr(visit, "vitals", None)
        if vitals is None:
            return None
        return {
            "blood_pressure": vitals.blood_pressure,
            "pulse_rate": vitals.pulse_rate,
            "temperature": str(vitals.temperature),
            "spo2": vitals.spo2,
            "presenting_complaint": vitals.presenting_complaint,
        }

    def get_urgency_reasons(self, visit):
        vitals = getattr(visit, "vitals", None)
        return vitals.urgency_reasons() if vitals else []

    def get_has_note(self, visit):
        return hasattr(visit, "consultation")

    def get_open_orders(self, visit):
        """How much of what the doctor asked for is still outstanding — the
        reason a visit sits in the queue after it has been seen."""
        return sum(1 for order in visit.orders.all() if order.is_open)

    def get_results_ready(self, visit):
        """Results back and released. This is what tells the doctor to call a
        patient back in rather than leaving them on a bench outside."""
        return sum(
            1
            for order in visit.orders.all()
            if getattr(order, "lab_result", None) is not None and order.lab_result.is_released
        )


class ConsultationOrderSerializer(OrderSerializer):
    """An order as the doctor reads it back, carrying whatever the department
    has returned so far.

    A result that has not been released is not shown. Until someone in the lab
    has put their name to it, it is a reading on a bench, not something to treat
    a patient on.
    """

    result = serializers.SerializerMethodField()
    prescription = serializers.SerializerMethodField()
    procedure = serializers.SerializerMethodField()

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["result", "prescription", "procedure"]

    def get_result(self, order):
        result = getattr(order, "lab_result", None)
        if result is None or not result.is_released:
            return None
        return LabResultSerializer(result).data

    def get_prescription(self, order):
        prescription = getattr(order, "prescription", None)
        return PrescriptionSerializer(prescription).data if prescription else None

    def get_procedure(self, order):
        record = getattr(order, "procedure_record", None)
        if record is None or not record.is_performed:
            return None
        return ProcedureRecordSerializer(record).data


class ConsultationOrderRequestSerializer(PlaceOrderSerializer):
    """What the doctor posts to order something.

    Directions come with the order rather than after it: a drug ordered without
    saying how it is to be taken is a packet the patient cannot use.
    """

    directions = DirectionsSerializer(required=False)


class VisitHistorySerializer(serializers.Serializer):
    """A previous visit, as the doctor needs it before seeing the patient again.

    Not the whole record — the date, what was concluded, and what came back.
    Enough to know whether this is the same complaint returning, without the
    doctor asking the patient to repeat a history the clinic already holds.
    """

    id = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    closed_at = serializers.DateTimeField()
    status_display = serializers.CharField(source="get_status_display")
    diagnosis = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    orders = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()

    def get_diagnosis(self, visit):
        note = getattr(visit, "consultation", None)
        return note.diagnosis if note else ""

    def get_doctor_name(self, visit):
        note = getattr(visit, "consultation", None)
        user = note.doctor if note else None
        return (user.get_full_name() or user.username) if user else None

    def get_orders(self, visit):
        return [
            order.service.name
            for order in visit.orders.all()
            if order.status != "cancelled"
        ]

    def get_results(self, visit):
        """Released results only, same rule as the current visit."""
        released = [
            order.lab_result
            for order in visit.orders.all()
            if getattr(order, "lab_result", None) is not None and order.lab_result.is_released
        ]
        return LabResultSerializer(released, many=True).data
