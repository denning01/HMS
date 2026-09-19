"""Vitals over the wire."""

from rest_framework import serializers

from .models import Vitals


class VitalsSerializer(serializers.ModelSerializer):
    bmi = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    bmi_category = serializers.CharField(read_only=True)
    blood_pressure = serializers.CharField(read_only=True)
    is_urgent = serializers.BooleanField(read_only=True)
    urgency_reasons = serializers.SerializerMethodField()

    class Meta:
        model = Vitals
        fields = [
            "id", "systolic_bp", "diastolic_bp", "pulse_rate", "temperature",
            "spo2", "respiratory_rate", "weight", "height",
            "presenting_complaint", "bmi", "bmi_category", "blood_pressure",
            "is_urgent", "urgency_reasons", "recorded_at",
        ]
        read_only_fields = ["id", "recorded_at"]

    def get_urgency_reasons(self, vitals):
        return vitals.urgency_reasons()

    def validate(self, attrs):
        systolic = attrs.get("systolic_bp")
        diastolic = attrs.get("diastolic_bp")

        if systolic and diastolic and diastolic >= systolic:
            raise serializers.ValidationError(
                {"diastolic_bp": "Diastolic pressure must be lower than systolic — check the reading."}
            )
        return attrs
