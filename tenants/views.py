from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from master.models import TenantConfig, TransactionType
from tenants.forms import PlatformTenantConfigForm, PlatformTransactionTypeForm, TenantAdmissionForm, TenantForm, TenantUserCreateForm
from tenants.models import Tenant
from tenants.services import admit_tenant, create_tenant_user


def superadmin_required(view_func):
    return login_required(user_passes_test(lambda user: user.is_superuser)(view_func))


@superadmin_required
def platform_tenant_list(request):
    tenants = Tenant.objects.prefetch_related('user_profiles__user').order_by('name')
    return render(request, 'platform/tenant_list.html', {'tenants': tenants})


@superadmin_required
def platform_tenant_admission(request):
    if request.method == 'POST':
        form = TenantAdmissionForm(request.POST, request.FILES)
        if form.is_valid():
            tenant_data = {
                'name': form.cleaned_data['name'],
                'address': form.cleaned_data['address'],
                'city': form.cleaned_data['city'],
                'province': form.cleaned_data['province'],
                'postal_code': form.cleaned_data['postal_code'],
                'phone': form.cleaned_data['phone'],
                'email': form.cleaned_data['email'],
                'logo': form.cleaned_data['logo'],
            }
            admin_data = {
                'username': form.cleaned_data['admin_username'],
                'email': form.cleaned_data['admin_email'],
                'first_name': form.cleaned_data['admin_first_name'],
                'last_name': form.cleaned_data['admin_last_name'],
                'password': form.cleaned_data['admin_password'],
                'role': form.cleaned_data['admin_role'],
            }
            tenant, user = admit_tenant(actor=request.user, tenant_data=tenant_data, admin_data=admin_data)
            messages.success(request, f'Tenant {tenant.name} berhasil didaftarkan dengan admin {user.username}.')
            return redirect(reverse('platform_tenant_list'))
    else:
        form = TenantAdmissionForm()
    return render(request, 'platform/tenant_admission.html', {'form': form})

@superadmin_required
def platform_tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tenant {tenant.name} berhasil disimpan.')
            return redirect(reverse('platform_tenant_list'))
    else:
        form = TenantForm(instance=tenant)
    return render(request, 'platform/tenant_form.html', {'form': form, 'tenant': tenant})


@superadmin_required
def platform_tenant_user_create(request):
    if request.method == 'POST':
        form = TenantUserCreateForm(request.POST)
        if form.is_valid():
            user_data = {
                'username': form.cleaned_data['username'],
                'email': form.cleaned_data['email'],
                'first_name': form.cleaned_data['first_name'],
                'last_name': form.cleaned_data['last_name'],
                'password': form.cleaned_data['password'],
                'role': form.cleaned_data['role'],
                'is_staff': form.cleaned_data['is_staff'],
            }
            user = create_tenant_user(actor=request.user, tenant=form.cleaned_data['tenant'], user_data=user_data)
            messages.success(request, f'User {user.username} berhasil dibuat.')
            return redirect(reverse('platform_tenant_list'))
    else:
        form = TenantUserCreateForm()
    return render(request, 'platform/tenant_user_form.html', {'form': form})

def platform_setting_queryset(model, request):
    queryset = model.objects.filter(is_deleted=False).select_related('tenant')
    if model is TransactionType:
        queryset = queryset.select_related('akun')
    tenant_id = request.GET.get('tenant', '').strip()
    q = request.GET.get('q', '').strip()
    if tenant_id:
        queryset = queryset.filter(tenant_id=tenant_id)
    if q:
        if model is TenantConfig:
            queryset = queryset.filter(Q(kode__icontains=q) | Q(nilai__icontains=q) | Q(keterangan__icontains=q))
        else:
            queryset = queryset.filter(Q(kode__icontains=q) | Q(nama__icontains=q) | Q(akun__kode__icontains=q) | Q(akun__nama__icontains=q))
    return queryset.order_by('tenant__name', 'kode')

@superadmin_required
def platform_config_list(request):
    rows = platform_setting_queryset(TenantConfig, request)
    return render(
        request,
        'platform/config_list.html',
        {
            'title': 'Config Tenant',
            'rows': rows,
            'tenants': Tenant.objects.order_by('name'),
            'selected_tenant': request.GET.get('tenant', ''),
            'q': request.GET.get('q', ''),
        },
    )

@superadmin_required
def platform_config_create(request):
    form = PlatformTenantConfigForm(request.POST or None, initial={'tenant': request.GET.get('tenant')})
    if request.method == 'POST' and form.is_valid():
        config = form.save(commit=False)
        config.created_by = request.user
        config.save()
        messages.success(request, 'Config tenant berhasil disimpan.')
        return redirect(reverse('platform_config_list'))
    return render(request, 'platform/setting_form.html', {'title': 'Tambah Config Tenant', 'form': form, 'cancel_url': reverse('platform_config_list')})

@superadmin_required
def platform_config_edit(request, uuid):
    config = get_object_or_404(TenantConfig, uuid=uuid, is_deleted=False)
    form = PlatformTenantConfigForm(request.POST or None, instance=config)
    if request.method == 'POST' and form.is_valid():
        config = form.save(commit=False)
        config.updated_by = request.user
        config.save()
        messages.success(request, 'Config tenant berhasil disimpan.')
        return redirect(reverse('platform_config_list'))
    return render(request, 'platform/setting_form.html', {'title': f'Edit Config {config.kode}', 'form': form, 'cancel_url': reverse('platform_config_list')})

@superadmin_required
def platform_config_delete(request, uuid):
    config = get_object_or_404(TenantConfig, uuid=uuid, is_deleted=False)
    if request.method == 'POST':
        config.is_deleted = True
        config.deleted_at = timezone.now()
        config.deleted_by = request.user
        config.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])
        messages.success(request, 'Config tenant berhasil dihapus.')
        return redirect(reverse('platform_config_list'))
    return render(request, 'platform/setting_confirm_delete.html', {'title': f'Hapus Config {config.kode}', 'object': config, 'cancel_url': reverse('platform_config_list')})

@superadmin_required
def platform_transaction_type_list(request):
    rows = platform_setting_queryset(TransactionType, request)
    return render(
        request,
        'platform/transaction_type_list.html',
        {
            'title': 'Jenis Transaksi',
            'rows': rows,
            'tenants': Tenant.objects.order_by('name'),
            'selected_tenant': request.GET.get('tenant', ''),
            'q': request.GET.get('q', ''),
        },
    )

@superadmin_required
def platform_transaction_type_create(request):
    form = PlatformTransactionTypeForm(request.POST or None, initial={'tenant': request.GET.get('tenant')})
    if request.method == 'POST' and form.is_valid():
        transaction_type = form.save(commit=False)
        transaction_type.created_by = request.user
        transaction_type.save()
        messages.success(request, 'Jenis transaksi berhasil disimpan.')
        return redirect(reverse('platform_transaction_type_list'))
    return render(request, 'platform/setting_form.html', {'title': 'Tambah Jenis Transaksi', 'form': form, 'cancel_url': reverse('platform_transaction_type_list')})

@superadmin_required
def platform_transaction_type_edit(request, uuid):
    transaction_type = get_object_or_404(TransactionType, uuid=uuid, is_deleted=False)
    form = PlatformTransactionTypeForm(request.POST or None, instance=transaction_type)
    if request.method == 'POST' and form.is_valid():
        transaction_type = form.save(commit=False)
        transaction_type.updated_by = request.user
        transaction_type.save()
        messages.success(request, 'Jenis transaksi berhasil disimpan.')
        return redirect(reverse('platform_transaction_type_list'))
    return render(request, 'platform/setting_form.html', {'title': f'Edit Jenis Transaksi {transaction_type.kode}', 'form': form, 'cancel_url': reverse('platform_transaction_type_list')})

@superadmin_required
def platform_transaction_type_delete(request, uuid):
    transaction_type = get_object_or_404(TransactionType, uuid=uuid, is_deleted=False)
    if request.method == 'POST':
        if transaction_type.bank_transactions.filter(is_deleted=False).exists():
            messages.error(request, 'Jenis transaksi tidak bisa dihapus karena sudah dipakai transaksi.')
            return redirect(reverse('platform_transaction_type_list'))
        transaction_type.is_deleted = True
        transaction_type.deleted_at = timezone.now()
        transaction_type.deleted_by = request.user
        transaction_type.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])
        messages.success(request, 'Jenis transaksi berhasil dihapus.')
        return redirect(reverse('platform_transaction_type_list'))
    return render(request, 'platform/setting_confirm_delete.html', {'title': f'Hapus Jenis Transaksi {transaction_type.kode}', 'object': transaction_type, 'cancel_url': reverse('platform_transaction_type_list')})
