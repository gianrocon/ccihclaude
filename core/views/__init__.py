from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def carregador_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from core.models import Vinculo
        if getattr(request, "papel_atual", None) != Vinculo.ROLE_CARREGADOR:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def staff_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
