"""The procedure room over the API: the queue, and doing one procedure."""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole
from apps.billing.models import Department
from apps.orders.models import Order
from apps.orders.selectors import worklist
from apps.pharmacy.selectors import stock_levels
from apps.pharmacy.serializers import StockItemSerializer

from .serializers import (
    PerformProcedureSerializer,
    ProcedureOrderSerializer,
)
from .services import ProcedureError, perform

PROCEDURE_ROLES = (Role.PROCEDURE_NURSE, Role.ADMINISTRATOR)


def order_queryset():
    return Order.objects.select_related(
        "visit__patient", "service", "invoice_line__invoice__visit", "procedure_record"
    ).filter(service__department=Department.PROCEDURE)


class ProcedureWorklistView(APIView):
    """What may be done, and what is still waiting on the till."""

    permission_classes = [HasAnyRole]
    roles = PROCEDURE_ROLES

    def get(self, request):
        def prepared(queryset):
            return queryset.select_related("procedure_record")

        return Response(
            {
                "ready": ProcedureOrderSerializer(
                    prepared(worklist(Department.PROCEDURE)), many=True
                ).data,
                "awaiting_payment": ProcedureOrderSerializer(
                    prepared(worklist(Department.PROCEDURE, cleared=False)), many=True
                ).data,
            }
        )


class ProcedureOrderView(APIView):
    """One procedure, with the consumables the nurse can reach for."""

    permission_classes = [HasAnyRole]
    roles = PROCEDURE_ROLES

    def get(self, request, pk):
        order = generics.get_object_or_404(order_queryset(), pk=pk)

        # Only what is actually on the shelf and in date; a nurse should not be
        # offered something they would then be refused.
        consumables = [item for item in stock_levels() if item.in_date_quantity > 0]

        return Response(
            {
                "order": ProcedureOrderSerializer(order).data,
                "consumables": StockItemSerializer(consumables, many=True).data,
            }
        )


class PerformProcedureView(APIView):
    """Record the procedure and take what it used off the shelf, in one action."""

    permission_classes = [HasAnyRole]
    roles = PROCEDURE_ROLES

    def post(self, request, pk):
        order = generics.get_object_or_404(order_queryset(), pk=pk)

        form = PerformProcedureSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        used = [
            (row["item"], row["quantity"])
            for row in form.validated_data.get("consumables", [])
        ]

        try:
            perform(
                order,
                notes=form.validated_data.get("notes", ""),
                consumables=used,
                performed_by=request.user,
            )
        except ProcedureError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        order.refresh_from_db()
        return Response(ProcedureOrderSerializer(order).data)
