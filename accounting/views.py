from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounting.forms import JournalForm, JournalLineEditFormSet, JournalLineFormSet
from accounting.models import ClosingPeriod, Journal, JournalLine
from accounting.services import assign_number, ensure_open_period
from audit.models import AuditLog
from audit.services import snapshot, write_audit
from master.models import BankAccount, ChartOfAccount

JOURNAL_TITLE = 'Jurnal Penyesuaian'
MANUAL_TRANSACTION = 'jurnal_memorial'


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


def manual_journals(request):
    return Journal.objects.filter(
        tenant=request.tenant,
        is_deleted=False,
        transaksi=MANUAL_TRANSACTION,
    )

def adjustment_account_queryset(request):
    child_accounts = ChartOfAccount.objects.filter(tenant=request.tenant, is_deleted=False, parent=OuterRef('pk'))
    bank_accounts = BankAccount.objects.filter(tenant=request.tenant, is_deleted=False, akun=OuterRef('pk'))
    return (
        ChartOfAccount.objects.filter(tenant=request.tenant, is_deleted=False, is_active=True)
        .annotate(has_children=Exists(child_accounts), used_by_bank=Exists(bank_accounts))
        .filter(has_children=False, used_by_bank=False)
    )

@login_required
def adjustment_account_lookup(request):
    require_tenant(request)
    q = request.GET.get('q', '').strip()
    queryset = adjustment_account_queryset(request)
    if q:
        queryset = queryset.filter(Q(kode__icontains=q) | Q(nama__icontains=q))
    results = [
        {'id': account.pk, 'label': f'{account.kode} - {account.nama}'}
        for account in queryset.order_by('kode')[:20]
    ]
    return JsonResponse({'results': results})


def journal_snapshot(journal):
    data = snapshot(journal)
    if not data:
        return data
    data['lines'] = [
        {
            'perkiraan': line.perkiraan_id,
            'debet': str(line.debet),
            'kredit': str(line.kredit),
        }
        for line in journal.lines.select_related('perkiraan').all()
    ]
    return data


def collect_lines(formset):
    lines = []
    total_debet = Decimal('0')
    total_kredit = Decimal('0')
    for form in formset.forms:
        if not getattr(form, 'cleaned_data', None):
            continue
        if form.cleaned_data.get('DELETE'):
            continue
        account = form.cleaned_data.get('perkiraan')
        debet = form.cleaned_data.get('debet') or Decimal('0')
        kredit = form.cleaned_data.get('kredit') or Decimal('0')
        if not account and not debet and not kredit:
            continue
        lines.append({'account': account, 'debet': debet, 'kredit': kredit})
        total_debet += debet
        total_kredit += kredit
    return lines, total_debet, total_kredit


@login_required
def journal_list(request):
    require_tenant(request)
    queryset = manual_journals(request)
    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    if q:
        queryset = queryset.filter(Q(no_jurnal__icontains=q) | Q(keterangan__icontains=q))
    if start_date:
        queryset = queryset.filter(tanggal__gte=start_date)
    if end_date:
        queryset = queryset.filter(tanggal__lte=end_date)
    paginator = Paginator(queryset, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'crud/list.html',
        {
            'title': JOURNAL_TITLE,
            'object_list': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'list_display': ['no_jurnal', 'tanggal', 'keterangan'],
            'detail_url_name': 'accounting_jurnal_detail',
            'hide_list_edit': True,
            'date_filter_field': 'tanggal',
            'start_date': start_date,
            'end_date': end_date,
            'q': q,
        },
    )


def render_journal_form(request, form, formset, title, journal=None):
    return render(
        request,
        'accounting/journal_form.html',
        {
            'title': title,
            'form': form,
            'formset': formset,
            'object': journal,
            'cancel_url': reverse('accounting_jurnal_list'),
        },
    )


def save_journal(request, journal, title):
    before = journal_snapshot(journal) if journal.pk else None
    old_tanggal = journal.tanggal if journal.pk else None
    form = JournalForm(request.POST, instance=journal)
    formset = JournalLineFormSet(request.POST, instance=journal, tenant=request.tenant, prefix='lines')
    if not (form.is_valid() and formset.is_valid()):
        return render_journal_form(request, form, formset, title, journal)

    lines, total_debet, total_kredit = collect_lines(formset)
    if not lines:
        form.add_error(None, 'Minimal satu baris debet dan satu baris kredit wajib diisi.')
    elif total_debet <= 0 or total_kredit <= 0:
        form.add_error(None, 'Total debet dan total kredit harus lebih dari nol.')
    elif total_debet != total_kredit:
        form.add_error(None, 'Total debet harus sama dengan total kredit.')
    if form.errors:
        return render_journal_form(request, form, formset, title, journal)

    try:
        with transaction.atomic():
            journal = form.save(commit=False)
            journal.tenant = request.tenant
            journal.transaksi = MANUAL_TRANSACTION
            journal.transaksi_id = 0
            if journal.pk:
                journal.updated_by = request.user
            else:
                journal.created_by = request.user
            ensure_open_period(journal.tenant, journal.tanggal, old_tanggal)
            assign_number(journal, 'no_jurnal', 'JUR')
            journal.save()
            JournalLine.objects.filter(journal=journal).delete()
            for line in lines:
                JournalLine.objects.create(
                    tenant=request.tenant,
                    journal=journal,
                    perkiraan=line['account'],
                    debet=line['debet'],
                    kredit=line['kredit'],
                    created_by=request.user,
                )
            action = AuditLog.Action.UPDATE if before else AuditLog.Action.CREATE
            write_audit(
                actor=request.user,
                tenant=request.tenant,
                action=action,
                instance=journal,
                before=before,
                after=None,
            )
    except ValidationError as exc:
        form.add_error(None, exc)
        return render_journal_form(request, form, formset, title, journal)

    messages.success(request, 'Data berhasil disimpan.')
    return redirect('accounting_jurnal_list')


@login_required
def journal_create(request):
    require_tenant(request)
    journal = Journal(tenant=request.tenant, transaksi=MANUAL_TRANSACTION)
    if request.method == 'POST':
        return save_journal(request, journal, f'Tambah {JOURNAL_TITLE}')
    form = JournalForm(instance=journal)
    formset = JournalLineFormSet(instance=journal, tenant=request.tenant, prefix='lines')
    return render_journal_form(request, form, formset, f'Tambah {JOURNAL_TITLE}', journal)


@login_required
def journal_detail(request, uuid):
    require_tenant(request)
    journal = get_object_or_404(
        manual_journals(request).prefetch_related('lines__perkiraan'),
        uuid=uuid,
    )
    return render(
        request,
        'accounting/journal_detail.html',
        {
            'title': f'Detail {JOURNAL_TITLE} {journal.no_jurnal}',
            'object': journal,
            'cancel_url': reverse('accounting_jurnal_list'),
        },
    )

@login_required
def journal_update(request, uuid):
    require_tenant(request)
    journal = get_object_or_404(manual_journals(request), uuid=uuid)
    if request.method == 'POST':
        return save_journal(request, journal, f'Edit {JOURNAL_TITLE}')
    form = JournalForm(instance=journal)
    formset = JournalLineEditFormSet(instance=journal, tenant=request.tenant, prefix='lines')
    return render_journal_form(request, form, formset, f'Edit {JOURNAL_TITLE}', journal)


@login_required
def journal_delete(request, uuid):
    require_tenant(request)
    journal = get_object_or_404(manual_journals(request), uuid=uuid)
    if request.method == 'POST':
        before = journal_snapshot(journal)
        try:
            ensure_open_period(journal.tenant, journal.tanggal)
            with transaction.atomic():
                JournalLine.objects.filter(journal=journal).delete()
                journal.delete()
                write_audit(
                    actor=request.user,
                    tenant=request.tenant,
                    action=AuditLog.Action.DELETE,
                    instance=journal,
                    before=before,
                    after=None,
                )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('accounting_jurnal_list')
        messages.success(request, 'Data berhasil dihapus.')
        return redirect('accounting_jurnal_list')
    return render(
        request,
        'crud/confirm_delete.html',
        {'title': f'Hapus {JOURNAL_TITLE}', 'object': journal, 'cancel_url': reverse('accounting_jurnal_list')},
    )

@login_required
def closing_detail(request, uuid):
    require_tenant(request)
    closing = get_object_or_404(
        ClosingPeriod.objects.filter(tenant=request.tenant, is_deleted=False),
        uuid=uuid,
    )
    return render(
        request,
        'accounting/closing_detail.html',
        {
            'title': f'Detail Closing {closing.tanggal}',
            'object': closing,
            'bank_balances': closing.bank_balances.select_related('bank').all(),
            'account_balances': closing.account_balances.select_related('perkiraan').all(),
            'cancel_url': reverse('accounting_closing_list'),
        },
    )



