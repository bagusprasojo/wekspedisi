from django.core.exceptions import PermissionDenied


class CurrentTenantMiddleware:
    """Attach the user's single tenant to request. Anonymous users have no tenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            if profile is None and not request.user.is_superuser:
                raise PermissionDenied('User belum terhubung ke tenant.')
            request.tenant = getattr(profile, 'tenant', None)
        return self.get_response(request)
