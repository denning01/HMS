"""Appointments over the API: the diary, booking, and what became of each one."""

from datetime import date

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role, User
from apps.accounts.permissions import HasAnyRole, user_has_any_role
from apps.patients.models import Patient
from apps.patients.serializers import VisitSerializer

from . import selectors
from .models import Appointment
from .serializers import (
    AppointmentSerializer,
    ArriveSerializer,
    BookAppointmentSerializer,
    OutcomeNoteSerializer,
)
from .services import (
    AppointmentError,
    arrive,
    book,
    cancel,
    confirm,
    mark_no_show,
)

DESK_ROLES = (Role.RECEPTIONIST, Role.ADMINISTRATOR)
# The doctor books the follow-up they have just asked for, and reads the diary
# to know when the patient is coming back. The desk runs everything else.
BOOKING_ROLES = DESK_ROLES + (Role.DOCTOR,)


class AppointmentListView(APIView):
    """One day's diary, what is still to come, and who has not turned up."""

    permission_classes = [HasAnyRole]
    roles = BOOKING_ROLES

    def get(self, request):
        term = request.query_params.get("q", "")

        day = timezone.localdate()
        invalid_day = False
        requested = request.query_params.get("day", "")
        if requested:
            try:
                day = date.fromisoformat(requested)
            except ValueError:
                invalid_day = True

        return Response(
            {
                "day": day.isoformat(),
                "is_today": day == timezone.localdate(),
                "invalid_day": invalid_day,
                "day_list": AppointmentSerializer(selectors.diary(day, term=term), many=True).data,
                "upcoming": AppointmentSerializer(selectors.upcoming(term=term), many=True).data,
                "overdue": AppointmentSerializer(selectors.overdue(), many=True).data,
                "can_run_desk": user_has_any_role(request.user, DESK_ROLES),
            }
        )

    def post(self, request):
        form = BookAppointmentSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        patient = generics.get_object_or_404(Patient, pk=form.validated_data["patient"])

        clinician = None
        clinician_id = form.validated_data.get("clinician")
        if clinician_id:
            clinician = generics.get_object_or_404(User, pk=clinician_id)

        try:
            appointment = book(
                patient=patient,
                scheduled_for=form.validated_data["scheduled_for"],
                department=form.validated_data["department"],
                clinician=clinician,
                reason=form.validated_data.get("reason", ""),
                created_by=request.user,
            )
        except AppointmentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED
        )


class AppointmentActionView(APIView):
    """Confirm, cancel, mark a no-show — all the desk's, all the same shape."""

    permission_classes = [HasAnyRole]
    roles = DESK_ROLES
    action = None

    def post(self, request, pk):
        appointment = generics.get_object_or_404(
            Appointment.objects.select_related("patient"), pk=pk
        )

        form = OutcomeNoteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        note = form.validated_data.get("note", "")

        try:
            self.run(appointment, note)
        except AppointmentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(AppointmentSerializer(appointment).data)

    def run(self, appointment, note):  # pragma: no cover - implemented by each action
        raise NotImplementedError


class ConfirmAppointmentView(AppointmentActionView):
    def run(self, appointment, note):
        confirm(appointment)


class CancelAppointmentView(AppointmentActionView):
    def run(self, appointment, note):
        cancel(appointment, note=note)


class NoShowAppointmentView(AppointmentActionView):
    def run(self, appointment, note):
        mark_no_show(appointment, note=note)


class ArriveAppointmentView(APIView):
    """The patient is here: open the visit without retyping them."""

    permission_classes = [HasAnyRole]
    roles = DESK_ROLES

    def post(self, request, pk):
        appointment = generics.get_object_or_404(
            Appointment.objects.select_related("patient"), pk=pk
        )

        form = ArriveSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        try:
            appointment, visit = arrive(
                appointment,
                billing_mode=form.validated_data["billing_mode"],
                arrived_by=request.user,
            )
        except AppointmentError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "appointment": AppointmentSerializer(appointment).data,
                "visit": VisitSerializer(visit).data,
            },
            status=status.HTTP_201_CREATED,
        )
