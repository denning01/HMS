"""Patient and Visit over the wire."""

from rest_framework import serializers

from .models import BillingMode, Patient, Visit


class PatientSummarySerializer(serializers.ModelSerializer):
    """Enough to identify a patient in a search result or a queue."""

    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    sex_display = serializers.CharField(source="get_sex_display", read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "mrn", "full_name", "age", "sex", "sex_display",
            "phone_number", "is_paediatric",
        ]


class PatientSerializer(serializers.ModelSerializer):
    """The full record, as Registration captures it."""

    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    sex_display = serializers.CharField(source="get_sex_display", read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id", "mrn", "first_name", "middle_name", "last_name", "full_name",
            "date_of_birth", "age", "sex", "sex_display", "is_paediatric",
            "phone_number", "residence", "national_id",
            "next_of_kin_name", "next_of_kin_relationship", "next_of_kin_phone",
            "created_at",
        ]
        read_only_fields = ["id", "mrn", "created_at"]

    def validate_date_of_birth(self, value):
        from django.utils import timezone

        if value > timezone.localdate():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value


class VisitSerializer(serializers.ModelSerializer):
    patient = PatientSummarySerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    billing_mode_display = serializers.CharField(
        source="get_billing_mode_display", read_only=True
    )
    has_vitals = serializers.SerializerMethodField()

    class Meta:
        model = Visit
        fields = [
            "id", "patient", "status", "status_display",
            "billing_mode", "billing_mode_display",
            "is_urgent", "is_open", "started_at", "closed_at", "has_vitals",
        ]

    def get_has_vitals(self, visit):
        return hasattr(visit, "vitals")


class StartVisitSerializer(serializers.Serializer):
    """Only the billing mode is chosen at the door; everything else is derived."""

    billing_mode = serializers.ChoiceField(
        choices=BillingMode.choices, default=BillingMode.PAY_PER_SERVICE
    )
