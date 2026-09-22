"""The laboratory over the API: the bench worklist and one test's three steps."""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole
from apps.billing.models import Department
from apps.orders.selectors import worklist

from .serializers import (
    CollectSpecimenSerializer,
    LabOrderSerializer,
    RecordResultSerializer,
)
from .services import (
    LabError,
    collect_specimen,
    order_queryset,
    record_result,
    release_result,
    worklist_queryset,
)

LAB_ROLES = (Role.LAB_TECHNICIAN, Role.ADMINISTRATOR)


class LabWorklistView(APIView):
    """What the bench may work on, and what it is still waiting on money for.

    Both lists, in one response. A technician who cannot see the held orders
    has no answer for the patient standing in front of them asking why their
    test has not been done.
    """

    permission_classes = [HasAnyRole]
    roles = LAB_ROLES

    def get(self, request):
        ready = worklist_queryset(worklist(Department.LABORATORY))
        held = worklist_queryset(worklist(Department.LABORATORY, cleared=False))

        return Response(
            {
                "ready": LabOrderSerializer(ready, many=True).data,
                "awaiting_payment": LabOrderSerializer(held, many=True).data,
            }
        )


class LabOrderView(generics.RetrieveAPIView):
    """One test: who it is for, why it was asked for, and how far it has got."""

    permission_classes = [HasAnyRole]
    roles = LAB_ROLES
    serializer_class = LabOrderSerializer

    def get_queryset(self):
        return order_queryset().filter(service__department=Department.LABORATORY)


class LabStepView(APIView):
    """Shared plumbing for the three steps: find the order, run it, report it."""

    permission_classes = [HasAnyRole]
    roles = LAB_ROLES

    def run(self, request, pk):  # pragma: no cover - implemented by each step
        raise NotImplementedError

    def post(self, request, pk):
        order = generics.get_object_or_404(
            order_queryset().filter(service__department=Department.LABORATORY), pk=pk
        )

        try:
            self.run(request, order)
        except LabError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        order.refresh_from_db()
        return Response(LabOrderSerializer(order).data)


class CollectSpecimenView(LabStepView):
    def run(self, request, order):
        form = CollectSpecimenSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        collect_specimen(
            order,
            specimen=form.validated_data.get("specimen"),
            collected_by=request.user,
        )


class RecordResultView(LabStepView):
    def run(self, request, order):
        form = RecordResultSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        record_result(
            order,
            findings=form.validated_data["findings"],
            is_abnormal=form.validated_data["is_abnormal"],
            recorded_by=request.user,
        )


class ReleaseResultView(LabStepView):
    def run(self, request, order):
        release_result(order, released_by=request.user)
