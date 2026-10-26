from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Allow only dealership staff / managers."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_dealer_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
