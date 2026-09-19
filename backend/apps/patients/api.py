"""Registration over the API: find a patient, register one, open a visit."""

from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole
from apps.billing.services import charge_consultation

from .models import OPEN_VISIT_STATUSES, Patient, Visit
from .serializers import (
    PatientSerializer,
    PatientSummarySerializer,
    StartVisitSerializer,
    VisitSerializer,
)
from .selectors import search_patients

REGISTRATION_ROLES = (Role.RECEPTIONIST, Role.ADMINISTRATOR)
RECORD_VIEW_ROLES = REGISTRATION_ROLES + (Role.TRIAGE_NURSE, Role.DOCTOR, Role.CASHIER)


class PatientListView(generics.ListCreateAPIView):
    """Search before create, so a returning patient is not registered twice."""

    permission_classes = [HasAnyRole]
    roles = REGISTRATION_ROLES

    def get_serializer_class(self):
        return PatientSerializer if self.request.method == "POST" else PatientSummarySerializer

    def get_queryset(self):
        term = self.request.query_params.get("q", "")
        if not term.strip():
            return Patient.objects.none()
        return search_patients(term)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PatientDetailView(generics.RetrieveAPIView):
    permission_classes = [HasAnyRole]
    roles = RECORD_VIEW_ROLES
    serializer_class = PatientSerializer
    queryset = Patient.objects.all()

    def retrieve(self, request, *args, **kwargs):
        patient = self.get_object()
        visits = patient.visits.select_related("created_by")

        return Response(
            {
                "patient": PatientSerializer(patient).data,
                "visits": VisitSerializer(visits, many=True).data,
                "open_visit": VisitSerializer(
                    visits.filter(status__in=OPEN_VISIT_STATUSES).first()
                ).data
                if visits.filter(status__in=OPEN_VISIT_STATUSES).exists()
                else None,
                "can_start_visit": request.user.is_superuser
                or any(request.user.has_role(role) for role in REGISTRATION_ROLES),
            }
        )


class StartVisitView(APIView):
    """Open a visit, raise the consultation charge, send the patient to triage."""

    permission_classes = [HasAnyRole]
    roles = REGISTRATION_ROLES

    def post(self, request, pk):
        patient = generics.get_object_or_404(Patient, pk=pk)

        if patient.visits.filter(status__in=OPEN_VISIT_STATUSES).exists():
            return Response(
                {"detail": f"{patient.full_name} already has an open visit — continue that one."},
                status=status.HTTP_409_CONFLICT,
            )

        form = StartVisitSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        try:
            visit = Visit.objects.create(
                patient=patient,
                created_by=request.user,
                billing_mode=form.validated_data["billing_mode"],
            )
        except IntegrityError:
            # The one-open-visit constraint fired: a concurrent request won.
            return Response(
                {"detail": f"{patient.full_name} already has an open visit — continue that one."},
                status=status.HTTP_409_CONFLICT,
            )

        charge_consultation(visit, ordered_by=request.user)

        return Response(VisitSerializer(visit).data, status=status.HTTP_201_CREATED)
