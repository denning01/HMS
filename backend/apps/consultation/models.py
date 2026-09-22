"""The consulting room: what the doctor found, and what they concluded.

One note per visit rather than one per time the patient is called in. A visit
comes back to the doctor after lab results or a procedure, and the history taken
at the start is still the history — re-asking it would be the paper file all over
again. The note is written once and added to as the visit goes on; what the
doctor *asks for* is an Order, which carries its own time and its own author.
"""

from django.conf import settings
from django.db import models

from apps.patients.models import Sex


class Consultation(models.Model):
    """The clinical record of one visit, in the sections of the clinic's form."""

    visit = models.OneToOneField(
        "patients.Visit", on_delete=models.CASCADE, related_name="consultation"
    )

    # History, as the paper form takes it.
    chief_complaint = models.TextField("C/C", help_text="What the patient came in for.")
    history_of_presenting_illness = models.TextField("HPI", blank=True)
    past_medical_history = models.TextField("Past medical and surgical history", blank=True)
    drug_reactions = models.TextField(
        "Drug reactions", blank=True, help_text="Known allergies and adverse reactions."
    )
    gynaecological_history = models.TextField("Gynaecological history", blank=True)
    obstetric_history = models.TextField("Obstetric history", blank=True)
    family_history = models.TextField("Family history", blank=True)

    # Findings and conclusion.
    examination_findings = models.TextField(blank=True)
    diagnosis = models.CharField(max_length=200, blank=True)
    icd10_code = models.CharField(
        "ICD-10 code",
        max_length=10,
        blank=True,
        help_text="Optional; carried for reporting rather than required at the bedside.",
    )
    treatment_plan = models.TextField(blank=True)

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="consultations",
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Consultation for {self.visit.patient.mrn} on {self.started_at:%Y-%m-%d}"

    @property
    def applies_gynae_obstetric_history(self):
        """Gyna/Obs history is asked of some patients, not all.

        Kept on the server as well as the form, so an answer that does not apply
        is never quietly stored against a patient it was never asked of.
        """
        return self.visit.patient.sex == Sex.FEMALE
