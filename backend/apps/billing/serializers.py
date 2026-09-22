"""Bills, charges, payments and receipts over the wire.

Money is serialised as a string, not a float: a bill that renders as 919.9999999
is not a bill anyone will sign off, and JSON numbers are binary floats.
"""

from rest_framework import serializers

from .models import Invoice, InvoiceLine, Payment, PaymentMethod, Service


class ServiceSerializer(serializers.ModelSerializer):
    department_display = serializers.CharField(source="get_department_display", read_only=True)

    class Meta:
        model = Service
        fields = ["id", "code", "name", "department", "department_display", "unit_price"]


class ServiceAdminSerializer(ServiceSerializer):
    """The price list as the administrator maintains it.

    The code is set once and never changed: bills already issued keep their own
    copy of the description and price, but the code is what reports and the
    seeders match on, and renaming it would quietly orphan both.
    """

    class Meta(ServiceSerializer.Meta):
        fields = ServiceSerializer.Meta.fields + ["is_active", "updated_at"]
        read_only_fields = ["updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None:
            fields["code"].read_only = True
        return fields

    def validate_code(self, value):
        return value.strip().upper()

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("A price cannot be negative.")
        return value


class InvoiceLineSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    department = serializers.CharField(read_only=True)
    department_display = serializers.CharField(
        source="service.get_department_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    receipt_number = serializers.CharField(source="payment.receipt_number", read_only=True, default=None)
    is_cleared = serializers.BooleanField(read_only=True)

    class Meta:
        model = InvoiceLine
        fields = [
            "id", "description", "unit_price", "quantity", "line_total",
            "department", "department_display", "status", "status_display",
            "is_cleared", "receipt_number", "ordered_at", "paid_at",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(source="get_method_display", read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "receipt_number", "amount", "method", "method_display",
            "reference", "received_at", "received_by_name",
        ]

    def get_received_by_name(self, payment):
        user = payment.received_by
        if user is None:
            return None
        return user.get_full_name() or user.username


class InvoiceSummarySerializer(serializers.ModelSerializer):
    """A row on the till: who it belongs to and what is still owing."""

    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)
    mrn = serializers.CharField(source="visit.patient.mrn", read_only=True)
    billing_mode = serializers.CharField(source="visit.billing_mode", read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_label = serializers.CharField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "number", "patient_name", "mrn", "billing_mode",
            "total", "balance", "status_label", "created_at",
        ]


class InvoiceSerializer(InvoiceSummarySerializer):
    """One bill, with its charges and the receipts raised against it."""

    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    paid_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    patient_id = serializers.IntegerField(source="visit.patient.id", read_only=True)

    class Meta(InvoiceSummarySerializer.Meta):
        fields = InvoiceSummarySerializer.Meta.fields + [
            "lines", "payments", "paid_total", "patient_id",
        ]


class TakePaymentSerializer(serializers.Serializer):
    """The cashier chooses lines and a method. The amount is not theirs to set —
    it is recomputed from those lines on the server."""

    lines = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
        error_messages={"empty": "Select at least one charge to pay for."},
    )
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=50)


class ReceiptSerializer(PaymentSerializer):
    """A payment, with the lines it settled and the bill it belongs to."""

    lines = InvoiceLineSerializer(many=True, read_only=True)
    invoice = InvoiceSummarySerializer(read_only=True)
    patient_name = serializers.CharField(source="invoice.visit.patient.full_name", read_only=True)
    mrn = serializers.CharField(source="invoice.visit.patient.mrn", read_only=True)

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ["lines", "invoice", "patient_name", "mrn"]
