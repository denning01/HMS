"""The diary over the wire."""

from rest_framework import serializers

from apps.patients.models import BillingMode
from apps.patients.serializers import PatientSummarySerializer

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    patient = PatientSummarySerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    clinician_name = serializers.SerializerMethodField()
    is_overdue = serializers.BooleanField(read_only=True)
    visit_id = serializers.IntegerField(source="visit.id", read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            "id", "patient", "scheduled_for", "department", "clinician", "clinician_name",
            "reason", "status", "status_display", "outcome_note", "is_overdue",
            "visit_id", "created_at",
        ]

    def get_clinician_name(self, appointment):
        user = appointment.clinician
        return (user.get_full_name() or user.username) if user else None


class BookAppointmentSerializer(serializers.Serializer):
    patient = serializers.IntegerField()
    scheduled_for = serializers.DateTimeField()
    department = serializers.CharField(max_length=20)
    clinician = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)


class OutcomeNoteSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


class ArriveSerializer(serializers.Serializer):
    billing_mode = serializers.ChoiceField(
        choices=BillingMode.choices, default=BillingMode.PAY_PER_SERVICE
    )
