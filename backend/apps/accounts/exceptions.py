"""How the API says "sign in" as distinct from "you may not".

DRF answers both with 403 when the authentication is a session cookie, because
there is no authentication header to challenge with. The client has to tell them
apart: one means the session has run out and the person should sign in again,
the other means they are signed in and the answer is still no. Sending 401 for
the first is the whole difference.
"""

from rest_framework.exceptions import NotAuthenticated
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is not None and isinstance(exc, NotAuthenticated):
        response.status_code = 401

    return response
