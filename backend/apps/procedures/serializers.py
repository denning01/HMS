"""The procedure room over the wire."""

from rest_framework import serializers

from apps.orders.serializers import WorklistOrderSerializer
from apps.pharmacy.serializers import StockMovementSerializer

from .models import ProcedureRecord


class ProcedureRecordSerializer(serializers.ModelSerializer):
    is_performed = serializers.BooleanField(read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    consumables = serializers.SerializerMethodField()
    consumable_cost = serializers.SerializerMethodField()

    class Meta:
        model = ProcedureRecord
        fields = [
            "id", "notes", "is_performed", "performed_at", "performed_by_name",
            "consumables", "consumable_cost",
        ]

    def get_performed_by_name(self, record):
        user = record.performed_by
        return (user.get_full_name() or user.username) if user else None

    def get_consumables(self, record):
        """What it used, read from the stock ledger rather than a second list."""
        return StockMovementSerializer(
            record.stock_movements.select_related("batch", "item", "recorded_by"), many=True
        ).data

    def get_consumable_cost(self, record):
        return str(record.consumable_cost)


class ProcedureOrderSerializer(WorklistOrderSerializer):
    """A row in the procedure room: the order, and whether it has been done."""

    record = serializers.SerializerMethodField()

    class Meta(WorklistOrderSerializer.Meta):
        fields = WorklistOrderSerializer.Meta.fields + ["record"]

    def get_record(self, order):
        record = getattr(order, "procedure_record", None)
        return ProcedureRecordSerializer(record).data if record else None


class ConsumableUsedSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=999)


class PerformProcedureSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    consumables = ConsumableUsedSerializer(many=True, required=False)
