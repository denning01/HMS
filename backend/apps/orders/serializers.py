"""Orders over the wire, for the consulting room and every departmental queue."""

from rest_framework import serializers

from .models import Order


class OrderSerializer(serializers.ModelSerializer):
    """One order, as it reads on the visit it belongs to."""

    service_code = serializers.CharField(source="service.code", read_only=True)
    name = serializers.CharField(source="service.name", read_only=True)
    department = serializers.CharField(read_only=True)
    department_display = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    unit_price = serializers.DecimalField(
        source="invoice_line.unit_price", max_digits=10, decimal_places=2, read_only=True
    )
    line_total = serializers.DecimalField(
        source="invoice_line.line_total", max_digits=12, decimal_places=2, read_only=True
    )
    # What the department is waiting for, in the words the screen shows.
    payment_status = serializers.CharField(source="invoice_line.status", read_only=True)
    is_cleared = serializers.BooleanField(read_only=True)

    ordered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "service", "service_code", "name", "quantity",
            "department", "department_display", "clinical_details",
            "status", "status_display", "unit_price", "line_total",
            "payment_status", "is_cleared", "ordered_at", "ordered_by_name",
        ]

    def get_ordered_by_name(self, order):
        user = order.ordered_by
        if user is None:
            return None
        return user.get_full_name() or user.username


class WorklistOrderSerializer(OrderSerializer):
    """A row on a department's queue: the order, and who it is for."""

    visit_id = serializers.IntegerField(source="visit.id", read_only=True)
    patient_name = serializers.CharField(source="visit.patient.full_name", read_only=True)
    mrn = serializers.CharField(source="visit.patient.mrn", read_only=True)
    age = serializers.IntegerField(source="visit.patient.age", read_only=True)
    sex = serializers.CharField(source="visit.patient.sex", read_only=True)
    is_urgent = serializers.BooleanField(source="visit.is_urgent", read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + [
            "visit_id", "patient_name", "mrn", "age", "sex", "is_urgent",
        ]


class PlaceOrderSerializer(serializers.Serializer):
    """What the doctor chooses. The price is not among it — that comes from the
    catalogue, as it does everywhere else money is raised."""

    service = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)
    clinical_details = serializers.CharField(
        required=False, allow_blank=True, max_length=2000
    )
