"""Consultation over the API: the queue, the note, the orders, closing the visit."""

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole, user_has_any_role
from apps.billing.models import Service
from apps.billing.serializers import InvoiceSerializer
from apps.orders.models import Order
from apps.orders.selectors import orders_for
from apps.orders.serializers import OrderSerializer, PlaceOrderSerializer
from apps.orders.services import OrderError, cancel_order, place_order
from apps.patients.models import Sex, Visit, VisitStatus
from apps.patients.serializers import VisitSerializer
from apps.triage.serializers import VitalsSerializer

from .models import Consultation
from .serializers import (
    CONDITIONAL_HISTORY_FIELDS,
    ConsultationOrderSerializer,
    ConsultationQueueSerializer,
    ConsultationSerializer,
)
from .services import ConsultationError, close_visit, open_note

CONSULTING_ROLES = (Role.DOCTOR, Role.ADMINISTRATOR)
# The nurse who took the vitals may read the record back; nobody else writes it.
RECORD_VIEW_ROLES = CONSULTING_ROLES + (Role.TRIAGE_NURSE,)

# Waiting to be seen, and already being seen. Both belong on the doctor's screen:
# a visit that has gone off for a test is still theirs to pick up afterwards.
QUEUE_STATUSES = [VisitStatus.AWAITING_CONSULTATION, VisitStatus.IN_CONSULTATION]


def visit_queryset():
    return Visit.objects.select_related("patient", "vitals", "consultation").prefetch_related(
        "orders__service", "orders__invoice_line__invoice__visit", "orders__lab_result"
    )


class ConsultationQueueView(generics.ListAPIView):
    """Who is waiting, urgent cases first, then longest wait first."""

    permission_classes = [HasAnyRole]
    roles = RECORD_VIEW_ROLES
    serializer_class = ConsultationQueueSerializer

    def get_queryset(self):
        return visit_queryset().filter(status__in=QUEUE_STATUSES).order_by(
            "-is_urgent", "started_at"
        )


class ConsultationDetailView(APIView):
    """Everything the doctor needs on one screen: the patient, this visit's
    vitals, the note so far, what has been ordered, and what the bill says."""

    permission_classes = [HasAnyRole]
    roles = RECORD_VIEW_ROLES

    def get(self, request, visit_id):
        visit = generics.get_object_or_404(visit_queryset(), pk=visit_id)
        note = getattr(visit, "consultation", None)
        invoice = getattr(visit, "invoice", None)

        return Response(
            {
                "visit": VisitSerializer(visit).data,
                "vitals": VitalsSerializer(visit.vitals).data
                if hasattr(visit, "vitals")
                else None,
                "consultation": ConsultationSerializer(note).data if note else None,
                "orders": ConsultationOrderSerializer(
                    orders_for(visit).select_related("lab_result"), many=True
                ).data,
                "invoice": InvoiceSerializer(invoice).data if invoice else None,
                # Navigation for the client; the server refuses the write regardless.
                "can_edit": user_has_any_role(request.user, CONSULTING_ROLES),
                "applies_gynae_obstetric_history": visit.patient.sex == Sex.FEMALE,
            }
        )

    def post(self, request, visit_id):
        """Write the note. The first write is what starts the consultation.

        The view is readable by the nurse who took the vitals, so writing is
        gated here rather than on the class: one URL, two audiences.
        """
        if not user_has_any_role(request.user, CONSULTING_ROLES):
            raise PermissionDenied("Only a clinician writes the consultation note.")

        visit = generics.get_object_or_404(visit_queryset(), pk=visit_id)

        if not visit.is_open:
            return Response(
                {"detail": "That visit is closed — the note can no longer be changed."},
                status=status.HTTP_409_CONFLICT,
            )

        # Validated before anything is created, so a rejected save leaves the
        # visit exactly as the doctor found it.
        form = ConsultationSerializer(
            getattr(visit, "consultation", None), data=request.data, partial=True
        )
        form.is_valid(raise_exception=True)

        # A male patient's record never carries a gynaecological or obstetric
        # history, whatever the form posts.
        if visit.patient.sex != Sex.FEMALE:
            for field in CONDITIONAL_HISTORY_FIELDS:
                form.validated_data.pop(field, None)

        note, created = open_note(visit, doctor=request.user)
        form.instance = note
        form.save(doctor=note.doctor or request.user)

        return Response(
            form.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ConsultationOrdersView(APIView):
    """Order a test, a drug or a procedure against this visit."""

    permission_classes = [HasAnyRole]
    roles = CONSULTING_ROLES

    def post(self, request, visit_id):
        visit = generics.get_object_or_404(
            Visit.objects.select_related("patient"), pk=visit_id
        )

        if not visit.is_open:
            return Response(
                {"detail": "That visit is closed — nothing more can be ordered on it."},
                status=status.HTTP_409_CONFLICT,
            )

        form = PlaceOrderSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        service = generics.get_object_or_404(Service, pk=form.validated_data["service"])

        # Ordering is also the start of the consultation for a doctor who acts
        # before writing anything down.
        open_note(visit, doctor=request.user)

        try:
            order = place_order(
                visit=visit,
                service=service,
                quantity=form.validated_data["quantity"],
                clinical_details=form.validated_data.get("clinical_details", ""),
                ordered_by=request.user,
            )
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CancelOrderView(APIView):
    """Withdraw an order raised in error, voiding its charge with it."""

    permission_classes = [HasAnyRole]
    roles = CONSULTING_ROLES

    def post(self, request, pk):
        order = generics.get_object_or_404(
            Order.objects.select_related("service", "invoice_line__invoice__visit"), pk=pk
        )

        try:
            cancel_order(order)
        except OrderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(OrderSerializer(order).data)


class CloseVisitView(APIView):
    """End the visit, once nothing is left outstanding on it."""

    permission_classes = [HasAnyRole]
    roles = CONSULTING_ROLES

    def post(self, request, visit_id):
        visit = generics.get_object_or_404(
            Visit.objects.select_related("patient", "invoice"), pk=visit_id
        )

        try:
            close_visit(visit)
        except ConsultationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(VisitSerializer(visit).data)
