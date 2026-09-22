"""The shelf, the prescription and the dispensing over the wire."""

from rest_framework import serializers

from apps.orders.serializers import WorklistOrderSerializer

from .models import MovementReason, Prescription, StockBatch, StockItem, StockMovement


class StockItemSerializer(serializers.ModelSerializer):
    form_display = serializers.CharField(source="get_form_display", read_only=True)
    service_code = serializers.CharField(source="service.code", read_only=True, default=None)
    unit_price = serializers.DecimalField(
        source="service.unit_price", max_digits=10, decimal_places=2, read_only=True, default=None
    )
    # Annotated by the selector; falls back to the model property for a single
    # item read on its own.
    quantity = serializers.SerializerMethodField()
    in_date_quantity = serializers.SerializerMethodField()
    is_low = serializers.SerializerMethodField()

    class Meta:
        model = StockItem
        fields = [
            "id", "name", "generic_name", "form", "form_display", "strength", "unit",
            "reorder_level", "service", "service_code", "unit_price",
            "quantity", "in_date_quantity", "is_low",
        ]

    def get_quantity(self, item):
        return getattr(item, "quantity", None) or item.quantity_in_stock

    def get_in_date_quantity(self, item):
        annotated = getattr(item, "in_date_quantity", None)
        return annotated if annotated is not None else item.quantity_in_stock

    def get_is_low(self, item):
        return self.get_quantity(item) <= item.reorder_level


class StockBatchSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    unit = serializers.CharField(source="item.unit", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_to_expiry = serializers.IntegerField(read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockBatch
        fields = [
            "id", "item", "item_name", "unit", "batch_number",
            "quantity_received", "quantity_remaining", "unit_cost",
            "expires_on", "is_expired", "days_to_expiry", "supplier",
            "received_at", "received_by_name",
        ]

    def get_received_by_name(self, batch):
        user = batch.received_by
        return (user.get_full_name() or user.username) if user else None


class StockMovementSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    cost_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    recorded_by_name = serializers.SerializerMethodField()
    patient_mrn = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = [
            "id", "quantity", "reason", "reason_display", "note",
            "batch_number", "unit_cost", "cost_total",
            "recorded_at", "recorded_by_name", "patient_mrn",
        ]

    def get_recorded_by_name(self, movement):
        user = movement.recorded_by
        return (user.get_full_name() or user.username) if user else None

    def get_patient_mrn(self, movement):
        if movement.prescription_id is None:
            return None
        return movement.prescription.order.visit.patient.mrn


class PrescriptionSerializer(serializers.ModelSerializer):
    directions = serializers.CharField(read_only=True)
    is_dispensed = serializers.BooleanField(read_only=True)
    dispensed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            "id", "dosage", "frequency", "duration", "instructions", "directions",
            "is_dispensed", "dispensed_at", "dispensed_by_name",
        ]

    def get_dispensed_by_name(self, prescription):
        user = prescription.dispensed_by
        return (user.get_full_name() or user.username) if user else None


class DispensingOrderSerializer(WorklistOrderSerializer):
    """A row on the dispensing queue: what to give, to whom, and what is left."""

    prescription = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()

    class Meta(WorklistOrderSerializer.Meta):
        fields = WorklistOrderSerializer.Meta.fields + ["prescription", "stock"]

    def get_prescription(self, order):
        prescription = getattr(order, "prescription", None)
        return PrescriptionSerializer(prescription).data if prescription else None

    def get_stock(self, order):
        """What the pharmacist needs before reaching for the shelf: is it there,
        and is enough of it in date."""
        item = getattr(order.service, "stock_item", None)
        if item is None:
            return None

        from .services import available

        in_date = available(item)
        return {
            "item_id": item.id,
            "name": str(item),
            "unit": item.unit,
            "available": in_date,
            "is_enough": in_date >= order.quantity,
        }


class ReceiveStockSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    unit_cost = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    expires_on = serializers.DateField()
    batch_number = serializers.CharField(required=False, allow_blank=True, max_length=40)
    supplier = serializers.CharField(required=False, allow_blank=True, max_length=120)


class WriteOffSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(
        choices=[
            (MovementReason.WASTAGE, MovementReason.WASTAGE.label),
            (MovementReason.EXPIRED, MovementReason.EXPIRED.label),
            (MovementReason.CORRECTION, MovementReason.CORRECTION.label),
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


class DirectionsSerializer(serializers.Serializer):
    """How the drug is to be taken, written with the order that raises it."""

    dosage = serializers.CharField(required=False, allow_blank=True, max_length=60)
    frequency = serializers.CharField(required=False, allow_blank=True, max_length=60)
    duration = serializers.CharField(required=False, allow_blank=True, max_length=60)
    instructions = serializers.CharField(required=False, allow_blank=True, max_length=200)
