from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from tenants.forms import TenantAdmissionForm, TenantForm, TenantUserCreateForm
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
