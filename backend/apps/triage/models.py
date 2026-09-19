"""Vitals recorded at triage, and the rules that flag a visit urgent."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.patients.models import Visit

# Thresholds that mark a visit urgent so it is prioritised in the doctor's queue.
# These are conservative adult screening bounds, not a clinical triage score —
# they are deliberately easy to adjust once the clinic confirms its own protocol.
URGENT_THRESHOLDS = {
    "spo2_below": 92,
    "systolic_above": 180,
    "systolic_below": 90,
    "diastolic_above": 120,
    "temperature_above": Decimal("38.5"),
    "temperature_below": Decimal("35.0"),
    "pulse_above": 120,
    "pulse_below": 50,
    "respiratory_rate_above": 24,
    "respiratory_rate_below": 10,
}


class Vitals(models.Model):
    """One set of readings, taken once per visit at triage."""

    visit = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name="vitals")

    systolic_bp = models.PositiveSmallIntegerField(
        "Systolic BP (mmHg)",
        validators=[MinValueValidator(40), MaxValueValidator(300)],
    )
    diastolic_bp = models.PositiveSmallIntegerField(
        "Diastolic BP (mmHg)",
        validators=[MinValueValidator(20), MaxValueValidator(200)],
    )
    pulse_rate = models.PositiveSmallIntegerField(
        "Pulse rate (bpm)",
        validators=[MinValueValidator(20), MaxValueValidator(250)],
    )
    temperature = models.DecimalField(
        "Temperature (°C)",
        max_digits=4,
        decimal_places=1,
        validators=[MinValueValidator(Decimal("25.0")), MaxValueValidator(Decimal("45.0"))],
    )
    spo2 = models.PositiveSmallIntegerField(
        "SpO₂ (%)",
        validators=[MinValueValidator(50), MaxValueValidator(100)],
    )
    respiratory_rate = models.PositiveSmallIntegerField(
        "Respiratory rate (breaths/min)",
        validators=[MinValueValidator(4), MaxValueValidator(80)],
    )
    weight = models.DecimalField(
        "Weight (kg)",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.5")), MaxValueValidator(Decimal("400"))],
    )
    height = models.DecimalField(
        "Height (m)",
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.30")), MaxValueValidator(Decimal("2.50"))],
    )

    presenting_complaint = models.TextField(
        blank=True,
        help_text="What the patient says is wrong, so the doctor has context before calling them in.",
    )

    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vitals_recorded",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "vitals"
        verbose_name_plural = "vitals"
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Vitals for {self.visit.patient.mrn} at {self.recorded_at:%Y-%m-%d %H:%M}"

    @property
    def bmi(self):
        """Body mass index, derived rather than stored so it cannot contradict the readings."""
        if not self.height or not self.weight:
            return None
        return round(self.weight / (self.height * self.height), 1)

    @property
    def bmi_category(self):
        bmi = self.bmi
        if bmi is None:
            return None
        if bmi < Decimal("18.5"):
            return "Underweight"
        if bmi < Decimal("25"):
            return "Normal"
        if bmi < Decimal("30"):
            return "Overweight"
        return "Obese"

    @property
    def blood_pressure(self):
        return f"{self.systolic_bp}/{self.diastolic_bp}"

    def urgency_reasons(self):
        """Readings outside the screening bounds, in plain words for the doctor's queue."""
        t = URGENT_THRESHOLDS
        checks = [
            (self.spo2 < t["spo2_below"], f"SpO₂ {self.spo2}%"),
            (self.systolic_bp > t["systolic_above"], f"Systolic BP {self.systolic_bp}"),
            (self.systolic_bp < t["systolic_below"], f"Systolic BP {self.systolic_bp}"),
            (self.diastolic_bp > t["diastolic_above"], f"Diastolic BP {self.diastolic_bp}"),
            (self.temperature > t["temperature_above"], f"Temperature {self.temperature}°C"),
            (self.temperature < t["temperature_below"], f"Temperature {self.temperature}°C"),
            (self.pulse_rate > t["pulse_above"], f"Pulse {self.pulse_rate} bpm"),
            (self.pulse_rate < t["pulse_below"], f"Pulse {self.pulse_rate} bpm"),
            (self.respiratory_rate > t["respiratory_rate_above"], f"Respiratory rate {self.respiratory_rate}"),
            (self.respiratory_rate < t["respiratory_rate_below"], f"Respiratory rate {self.respiratory_rate}"),
        ]
        return [reason for failed, reason in checks if failed]

    @property
    def is_urgent(self):
        return bool(self.urgency_reasons())
