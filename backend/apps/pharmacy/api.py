"""The pharmacy over the API: the dispensing queue, and the shelf behind it."""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole
from apps.billing.models import Department
from apps.orders.models import Order
from apps.orders.selectors import worklist

from . import selectors
from .models import StockBatch, StockItem, StockMovement
from .serializers import (
    DispensingOrderSerializer,
    ReceiveStockSerializer,
    StockBatchSerializer,
    StockItemSerializer,
    StockMovementSerializer,
    WriteOffSerializer,
)
from .services import PharmacyError, dispense, receive_stock, write_off

PHARMACY_ROLES = (Role.PHARMACIST, Role.ADMINISTRATOR)
# The people who answer for the money tied up on the shelf read it too.
STOCK_VIEW_ROLES = PHARMACY_ROLES + (Role.FINANCE_MANAGER,)

MOVEMENT_HISTORY_LIMIT = 50


def order_queryset():
    return Order.objects.select_related(
        "visit__patient",
        "service__stock_item",
        "invoice_line__invoice__visit",
        "prescription",
    ).filter(service__department=Department.PHARMACY)


class DispensingQueueView(APIView):
    """What may be dispensed, and what is still waiting on the till."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES

    def get(self, request):
        def prepared(queryset):
            return queryset.select_related("prescription", "service__stock_item")

        return Response(
            {
                "ready": DispensingOrderSerializer(
                    prepared(worklist(Department.PHARMACY)), many=True
                ).data,
                "awaiting_payment": DispensingOrderSerializer(
                    prepared(worklist(Department.PHARMACY, cleared=False)), many=True
                ).data,
            }
        )


class PrescriptionView(generics.RetrieveAPIView):
    """One prescription: the directions, and what is on the shelf for it."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES
    serializer_class = DispensingOrderSerializer

    def get_queryset(self):
        return order_queryset()


class DispenseView(APIView):
    """Give out what was prescribed, oldest stock first."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES

    def post(self, request, pk):
        order = generics.get_object_or_404(order_queryset(), pk=pk)

        try:
            _, movements = dispense(order, dispensed_by=request.user)
        except PharmacyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        order.refresh_from_db()
        return Response(
            {
                "order": DispensingOrderSerializer(order).data,
                "movements": StockMovementSerializer(movements, many=True).data,
            }
        )


class StockView(APIView):
    """The shelf: every item with its count, and the two things worth a warning."""

    permission_classes = [HasAnyRole]
    roles = STOCK_VIEW_ROLES

    def get(self, request):
        items = selectors.stock_levels()
        expiring = selectors.expiring_batches()

        return Response(
            {
                "items": StockItemSerializer(items, many=True).data,
                "low_stock": StockItemSerializer(
                    [item for item in items if item.quantity <= item.reorder_level], many=True
                ).data,
                "expiring": StockBatchSerializer(expiring, many=True).data,
            }
        )


class StockItemView(APIView):
    """One item: its batches, and the last of its movements."""

    permission_classes = [HasAnyRole]
    roles = STOCK_VIEW_ROLES

    def get(self, request, pk):
        item = generics.get_object_or_404(StockItem.objects.select_related("service"), pk=pk)
        movements = (
            StockMovement.objects.filter(item=item)
            .select_related("batch", "recorded_by", "prescription__order__visit__patient")
            [:MOVEMENT_HISTORY_LIMIT]
        )

        return Response(
            {
                "item": StockItemSerializer(item).data,
                "batches": StockBatchSerializer(
                    item.batches.select_related("received_by"), many=True
                ).data,
                "movements": StockMovementSerializer(movements, many=True).data,
            }
        )


class ReceiveStockView(APIView):
    """Take a delivery onto the shelf."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES

    def post(self, request, pk):
        item = generics.get_object_or_404(StockItem, pk=pk)

        form = ReceiveStockSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        try:
            batch = receive_stock(item, received_by=request.user, **form.validated_data)
        except PharmacyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(StockBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class WriteOffView(APIView):
    """Take stock off the shelf for something other than a patient."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES

    def post(self, request, pk):
        batch = generics.get_object_or_404(StockBatch.objects.select_related("item"), pk=pk)

        form = WriteOffSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        try:
            movement = write_off(batch, recorded_by=request.user, **form.validated_data)
        except PharmacyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED)


# --- the stock list, as the administrator and the pharmacist maintain it ----


class StockItemAdminListView(generics.ListCreateAPIView):
    """Every item the clinic counts, retired ones included, and a way to add one."""

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES
    serializer_class = StockItemSerializer
    queryset = StockItem.objects.select_related("service").order_by("name")


class StockItemAdminDetailView(generics.RetrieveUpdateAPIView):
    """Change what an item is called, what one unit means, or when to reorder.

    No delete: an item with movements against it is part of the ledger, and the
    way out is `is_active`, exactly as it is for a priced service.
    """

    permission_classes = [HasAnyRole]
    roles = PHARMACY_ROLES
    serializer_class = StockItemSerializer
    queryset = StockItem.objects.select_related("service")
