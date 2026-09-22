"""Revenue and profit over the API, for the people who answer for the money."""

from datetime import date, timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import HasAnyRole

from . import reports

# Profit is the owner's figure. The cashier reconciles their own day through
# Collections, which is a different question asked of the same payments.
FINANCE_ROLES = (Role.FINANCE_MANAGER, Role.ADMINISTRATOR)

# A week reads as a week: today and the six days behind it.
DEFAULT_RANGE_DAYS = 6
MAX_RANGE_DAYS = 366


def _money(rows, key="total"):
    return [{**row, key: str(row[key])} for row in rows]


class RevenueReportView(APIView):
    """What the clinic earned, what its stock cost, and the difference."""

    permission_classes = [HasAnyRole]
    roles = FINANCE_ROLES

    def get(self, request):
        today = timezone.localdate()
        invalid_range = False

        def read(name, fallback):
            nonlocal invalid_range
            raw = request.query_params.get(name, "")
            if not raw:
                return fallback
            try:
                return date.fromisoformat(raw)
            except ValueError:
                invalid_range = True
                return fallback

        end = read("to", today)
        start = read("from", end - timedelta(days=DEFAULT_RANGE_DAYS))

        # A range the wrong way round is a typo, not a reason to return nothing.
        if start > end:
            start, end = end, start
        # And an unbounded one is a query that locks the database for a report
        # nobody asked for.
        if (end - start).days > MAX_RANGE_DAYS:
            start = end - timedelta(days=MAX_RANGE_DAYS)
            invalid_range = True

        figures = reports.summary(start, end)

        return Response(
            {
                "from": start.isoformat(),
                "to": end.isoformat(),
                "days": (end - start).days + 1,
                "invalid_range": invalid_range,
                "revenue": str(figures["revenue"]),
                "cost": str(figures["cost"]),
                "profit": str(figures["profit"]),
                "losses": str(figures["losses"]),
                "receipts": figures["receipts"],
                "daily": [
                    {
                        "day": row["day"].isoformat(),
                        "revenue": str(row["revenue"]),
                        "cost": str(row["cost"]),
                        "profit": str(row["profit"]),
                    }
                    for row in figures["daily"]
                ],
                "by_department": _money(figures["by_department"]),
                "by_method": _money(figures["by_method"]),
                "by_cashier": _money(figures["by_cashier"]),
                "cost_by_reason": _money(figures["cost_by_reason"]),
            }
        )
