"""Who may do what in Billing.

Separate from the API views so the rule reads in one place: the Finance Manager
reads the bills, the Cashier works the till, and the Administrator does both.
"""

from apps.accounts.models import Role

TILL_ROLES = (Role.CASHIER, Role.ADMINISTRATOR)
VIEW_ROLES = TILL_ROLES + (Role.FINANCE_MANAGER,)
REPORT_ROLES = (Role.FINANCE_MANAGER, Role.ADMINISTRATOR, Role.CASHIER)

# Who may read the price list. Everyone who orders from it or quotes from it —
# which is every clinical department plus the till. Editing it stays with the
# Administrator, in the admin, so pricing changes are auditable.
CATALOGUE_ROLES = (
    Role.ADMINISTRATOR,
    Role.DOCTOR,
    Role.LAB_TECHNICIAN,
    Role.PHARMACIST,
    Role.PROCEDURE_NURSE,
    Role.CASHIER,
    Role.FINANCE_MANAGER,
)

SEARCH_RESULT_LIMIT = 20
