"""Who may do what in Billing.

Separate from the API views so the rule reads in one place: the Finance Manager
reads the bills, the Cashier works the till, and the Administrator does both.
"""

from apps.accounts.models import Role

TILL_ROLES = (Role.CASHIER, Role.ADMINISTRATOR)
VIEW_ROLES = TILL_ROLES + (Role.FINANCE_MANAGER,)
REPORT_ROLES = (Role.FINANCE_MANAGER, Role.ADMINISTRATOR, Role.CASHIER)

SEARCH_RESULT_LIMIT = 20
