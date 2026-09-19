"""Triage over the API: the queue, and recording one set of vitals."""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole
from apps.patients.models import Visit, VisitStatus
from apps.patients.serializers import VisitSerializer

from .serializers import VitalsSerializer

TRIAGE_ROLES = (Role.TRIAGE_NURSE, Role.ADMINISTRATOR)


class TriageQueueView(generics.ListAPIView):
    """Visits waiting for vitals, oldest first so nobody is left behind."""

    permission_classes = [HasAnyRole]
    roles = TRIAGE_ROLES
    serializer_class = VisitSerializer

    def get_queryset(self):
        return (
            Visit.objects.filter(status=VisitStatus.AWAITING_TRIAGE)
            .select_related("patient")
            .order_by("started_at")
        )


class VitalsView(APIView):
    """Record vitals against an open visit and move it on to consultation."""

    permission_classes = [HasAnyRole]
    roles = TRIAGE_ROLES

    def get(self, request, visit_id):
        visit = generics.get_object_or_404(
            Visit.objects.select_related("patient"), pk=visit_id
        )
        return Response(
            {
                "visit": VisitSerializer(visit).data,
                "vitals": VitalsSerializer(visit.vitals).data
                if hasattr(visit, "vitals")
                else None,
            }
        )

    def post(self, request, visit_id):
        visit = generics.get_object_or_404(
            Visit.objects.select_related("patient"), pk=visit_id
        )

        if not visit.is_open:
            return Response(
                {"detail": "That visit is already closed."},
                status=status.HTTP_409_CONFLICT,
            )

        if hasattr(visit, "vitals"):
            return Response(
                {"detail": f"Vitals were already recorded for {visit.patient.full_name}."},
                status=status.HTTP_409_CONFLICT,
            )

        form = VitalsSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        vitals = form.save(visit=visit, recorded_by=request.user)

        # Out-of-range readings prioritise this visit in the doctor's queue.
        visit.is_urgent = vitals.is_urgent
        visit.status = VisitStatus.AWAITING_CONSULTATION
        visit.save(update_fields=["is_urgent", "status"])

        return Response(
            {
                "vitals": VitalsSerializer(vitals).data,
                "visit": VisitSerializer(visit).data,
            },
            status=status.HTTP_201_CREATED,
        )
