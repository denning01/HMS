"""Role gating for views.

The specification's permissions matrix is expressed as role membership, so views
declare the roles they serve rather than checking individual model permissions.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def user_has_any_role(user, roles):
    """True if the user holds at least one of these roles. Superusers hold all."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return any(user.has_role(role) for role in roles)


def role_required(*roles):
    """Restrict a view to the given roles.

    An anonymous visitor is sent to the login page; a signed-in user without the
    role gets 403 rather than a login loop, which would otherwise look like a
    broken password to front-desk staff.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not user_has_any_role(request.user, roles):
                raise PermissionDenied(
                    "Your role does not give you access to this screen."
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
