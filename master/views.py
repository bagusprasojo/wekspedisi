from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse

from master.models import StakeHolder


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


@login_required
def stakeholder_lookup(request):
    require_tenant(request)
    q = request.GET.get('q', '').strip()
    jenis = request.GET.get('jenis', '').strip()
    queryset = StakeHolder.objects.filter(tenant=request.tenant, is_deleted=False)
    if jenis:
        queryset = queryset.filter(jenis=jenis)
    if q:
        queryset = queryset.filter(Q(nama__icontains=q) | Q(telp__icontains=q))
    results = [
        {'id': stakeholder.pk, 'label': str(stakeholder)}
        for stakeholder in queryset.order_by('nama')[:20]
    ]
    return JsonResponse({'results': results})
