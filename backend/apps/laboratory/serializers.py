"""Lab orders and their results over the wire."""

from django.utils import timezone
from rest_framework import serializers

from apps.orders.serializers import WorklistOrderSerializer

from .models import LabResult, Specimen


class LabResultSerializer(serializers.ModelSerializer):
    """A result as the doctor reads it back."""

    specimen_display = serializers.CharField(source="get_specimen_display", read_only=True)
    stage = serializers.CharField(read_only=True)
    is_released = serializers.BooleanField(read_only=True)
    turnaround_minutes = serializers.IntegerField(read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    released_by_name = serializers.SerializerMethodField()
    collected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LabResult
        fields = [
            "id", "specimen", "specimen_display", "stage",
            "collected_at", "collected_by_name",
            "findings", "is_abnormal", "recorded_at", "recorded_by_name",
            "released_at", "released_by_name", "is_released", "turnaround_minutes",
        ]

    def _name(self, user):
        if user is None:
            return None
        return user.get_full_name() or user.username

    def get_recorded_by_name(self, result):
        return self._name(result.recorded_by)

    def get_released_by_name(self, result):
        return self._name(result.released_by)

    def get_collected_by_name(self, result):
        return self._name(result.collected_by)


class LabOrderSerializer(WorklistOrderSerializer):
    """One row on the bench: the order, who it is for, and how far it has got."""

    result = serializers.SerializerMethodField()
    specimen = serializers.SerializerMethodField()
    reference_range = serializers.CharField(
        source="service.lab_test.reference_range", read_only=True, default=""
    )
    preparation = serializers.CharField(
        source="service.lab_test.preparation", read_only=True, default=""
    )
    waiting_minutes = serializers.SerializerMethodField()

    class Meta(WorklistOrderSerializer.Meta):
        fields = WorklistOrderSerializer.Meta.fields + [
            "result", "specimen", "reference_range", "preparation", "waiting_minutes",
        ]

    def get_result(self, order):
        result = getattr(order, "lab_result", None)
        return LabResultSerializer(result).data if result else None

    def get_specimen(self, order):
        lab_test = getattr(order.service, "lab_test", None)
        return lab_test.specimen if lab_test else Specimen.OTHER

    def get_waiting_minutes(self, order):
        result = getattr(order, "lab_result", None)
        if result is not None:
            return result.waiting_minutes
        return int((timezone.now() - order.ordered_at).total_seconds() // 60)


class CollectSpecimenSerializer(serializers.Serializer):
    specimen = serializers.ChoiceField(choices=Specimen.choices, required=False)


class RecordResultSerializer(serializers.Serializer):
    findings = serializers.CharField(max_length=4000)
    is_abnormal = serializers.BooleanField(default=False)
