def populate_form_context(context, config, request, form=None, obj=None):
    from decimal import Decimal
    from core.templatetags.crud_extras import format_money
    model_name = config.model._meta.model_name
    tenant = getattr(request, 'tenant', None)

    if model_name in {'fuelpurchase', 'cashtransaction', 'armada'}:
        armada_obj = None
        if obj and getattr(obj, 'armada', None):
            armada_obj = obj.armada
        elif form and form.is_bound and form.data.get('armada'):
            from master.models import Armada
            armada_obj = Armada.objects.filter(pk=form.data.get('armada'), tenant=tenant, is_deleted=False).first()
        if armada_obj:
            parts = [armada_obj.nopol]
            if armada_obj.kendaraan:
                parts.append(armada_obj.kendaraan)
            if armada_obj.driver:
                parts.append(f'Supir: {armada_obj.driver.nama}')
            elif armada_obj.pemilik:
                parts.append(f'Milik: {armada_obj.pemilik}')
            context['initial_armada_label'] = ' - '.join(parts)

    if model_name == 'employeecashadvancepayment':
        adv_obj = None
        current_nominal = Decimal('0')
        if obj and getattr(obj, 'kas_bon_karyawan', None):
            adv_obj = obj.kas_bon_karyawan
            current_nominal = obj.nominal or Decimal('0')
        elif form and form.is_bound and form.data.get('kas_bon_karyawan'):
            from finance.models import EmployeeCashAdvance
            adv_obj = EmployeeCashAdvance.objects.filter(pk=form.data.get('kas_bon_karyawan'), tenant=tenant, is_deleted=False).first()
            if form.data.get('nominal'):
                try:
                    current_nominal = Decimal(str(form.data.get('nominal')))
                except Exception:
                    pass
        if adv_obj:
            saldo_val = adv_obj.saldo + current_nominal
            context['initial_cash_advance_label'] = f"{adv_obj.no_register} - {adv_obj.karyawan.nama if adv_obj.karyawan else ''} (Sisa: {format_money(saldo_val)})"
            context['initial_cash_advance_name'] = adv_obj.karyawan.nama if adv_obj.karyawan else ''
            context['initial_cash_advance_address'] = getattr(adv_obj.karyawan, 'alamat', '') if adv_obj.karyawan else ''
            context['initial_cash_advance_balance'] = format_money(saldo_val)

    if model_name == 'loandebt':
        acc_obj = getattr(obj, 'perkiraan_hutang', None) if obj else None
        stk_obj = getattr(obj, 'pemberi_pinjaman', None) if obj else None
        if form and form.is_bound:
            if not acc_obj and form.data.get('perkiraan_hutang'):
                from master.models import ChartOfAccount
                acc_obj = ChartOfAccount.objects.filter(pk=form.data.get('perkiraan_hutang'), tenant=tenant, is_deleted=False).first()
            if not stk_obj and form.data.get('pemberi_pinjaman'):
                from master.models import StakeHolder
                stk_obj = StakeHolder.objects.filter(pk=form.data.get('pemberi_pinjaman'), tenant=tenant, is_deleted=False).first()
        if acc_obj:
            context['initial_account_label'] = str(acc_obj)
        if stk_obj:
            context['initial_pemberi_pinjaman_label'] = str(stk_obj)

    if model_name == 'loandebtpayment':
        debt_obj = None
        current_nominal = Decimal('0')
        if obj and getattr(obj, 'hutang_pinjaman', None):
            debt_obj = obj.hutang_pinjaman
            current_nominal = obj.nominal or Decimal('0')
        elif form and form.is_bound and form.data.get('hutang_pinjaman'):
            from finance.models import LoanDebt
            debt_obj = LoanDebt.objects.filter(pk=form.data.get('hutang_pinjaman'), tenant=tenant, is_deleted=False).first()
            if form.data.get('nominal'):
                try:
                    current_nominal = Decimal(str(form.data.get('nominal')))
                except Exception:
                    pass
        if debt_obj:
            saldo_val = debt_obj.saldo + current_nominal
            context['initial_loan_debt_label'] = f"{debt_obj.no_register} - {debt_obj.pemberi_pinjaman.nama if debt_obj.pemberi_pinjaman else ''} (Sisa: {format_money(saldo_val)})"
            context['initial_cash_advance_name'] = debt_obj.pemberi_pinjaman.nama if debt_obj.pemberi_pinjaman else ''
            context['initial_cash_advance_address'] = getattr(debt_obj.pemberi_pinjaman, 'alamat', '') if debt_obj.pemberi_pinjaman else ''
            context['initial_cash_advance_balance'] = format_money(saldo_val)

    if model_name == 'loanreceivable':
        acc_obj = getattr(obj, 'perkiraan_piutang', None) if obj else None
        stk_obj = getattr(obj, 'penerima_pinjaman', None) if obj else None
        if form and form.is_bound:
            if not acc_obj and form.data.get('perkiraan_piutang'):
                from master.models import ChartOfAccount
                acc_obj = ChartOfAccount.objects.filter(pk=form.data.get('perkiraan_piutang'), tenant=tenant, is_deleted=False).first()
            if not stk_obj and form.data.get('penerima_pinjaman'):
                from master.models import StakeHolder
                stk_obj = StakeHolder.objects.filter(pk=form.data.get('penerima_pinjaman'), tenant=tenant, is_deleted=False).first()
        if acc_obj:
            context['initial_account_label'] = str(acc_obj)
        if stk_obj:
            context['initial_penerima_pinjaman_label'] = str(stk_obj)

    if model_name == 'loanreceivablepayment':
        rec_obj = None
        current_nominal = Decimal('0')
        if obj and getattr(obj, 'piutang_pinjaman', None):
            rec_obj = obj.piutang_pinjaman
            current_nominal = obj.nominal or Decimal('0')
        elif form and form.is_bound and form.data.get('piutang_pinjaman'):
            from finance.models import LoanReceivable
            rec_obj = LoanReceivable.objects.filter(pk=form.data.get('piutang_pinjaman'), tenant=tenant, is_deleted=False).first()
            if form.data.get('nominal'):
                try:
                    current_nominal = Decimal(str(form.data.get('nominal')))
                except Exception:
                    pass
        if rec_obj:
            saldo_val = rec_obj.saldo + current_nominal
            context['initial_loan_receivable_label'] = f"{rec_obj.no_register} - {rec_obj.penerima_pinjaman.nama if rec_obj.penerima_pinjaman else ''} (Sisa: {format_money(saldo_val)})"
            context['initial_cash_advance_name'] = rec_obj.penerima_pinjaman.nama if rec_obj.penerima_pinjaman else ''
            context['initial_cash_advance_address'] = getattr(rec_obj.penerima_pinjaman, 'alamat', '') if rec_obj.penerima_pinjaman else ''
            context['initial_cash_advance_balance'] = format_money(saldo_val)


from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from audit.models import AuditLog
from audit.services import snapshot, write_audit
from core.exporters import excel_response, pdf_response
from core.templatetags.crud_extras import format_money, get_attr, is_money_field


class TenantRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser and request.tenant is None:
            raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
        if request.tenant is None:
            raise PermissionDenied('User belum terhubung ke tenant.')
        return super().dispatch(request, *args, **kwargs)


class TenantQuerysetMixin(TenantRequiredMixin):
    search_fields = []
    date_filter_field = None
    date_filter_default = 'month'
    fixed_filters = {}

    def get_queryset(self):
        queryset = super().get_queryset().filter(tenant=self.request.tenant, is_deleted=False)
        if self.fixed_filters:
            queryset = queryset.filter(**self.fixed_filters)
        q = self.request.GET.get('q', '').strip()
        if q and self.search_fields:
            from django.db.models import Q
            condition = Q()
            for field in self.search_fields:
                condition |= Q(**{f'{field}__icontains': q})
            queryset = queryset.filter(condition)
        if self.date_filter_field:
            today = timezone.localdate()
            start_default = today.replace(month=1, day=1) if self.date_filter_default == 'year' else today.replace(day=1)
            end_default = today.replace(month=12, day=31) if self.date_filter_default == 'year' else today
            start_date = self.request.GET.get('start_date', '').strip() or start_default.isoformat()
            end_date = self.request.GET.get('end_date', '').strip() or end_default.isoformat()
            try:
                s_date = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
                e_date = timezone.datetime.strptime(end_date, '%Y-%m-%d').date()
                # if s_date.year != e_date.year:
                #     from django.contrib import messages
                #     title_name = getattr(self, 'config', None).title if hasattr(self, 'config') and getattr(self, 'config', None) else 'data'
                #     messages.warning(self.request, f'Periode filter {title_name} harus berada pada tahun yang sama.')
                #     e_date = s_date.replace(month=12, day=31)
                #     end_date = e_date.isoformat()
            except (ValueError, TypeError):
                pass
            self.effective_start_date = start_date
            self.effective_end_date = end_date
            queryset = queryset.filter(**{f'{self.date_filter_field}__gte': start_date})
            queryset = queryset.filter(**{f'{self.date_filter_field}__lte': end_date})
        return queryset


class TenantFormMixin(TenantRequiredMixin):
    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.tenant = self.request.tenant
        for field_name, value in getattr(self, 'fixed_values', {}).items():
            setattr(obj, field_name, value)
        before = snapshot(type(obj).objects.filter(pk=obj.pk).first()) if obj.pk else None
        if obj.pk:
            obj.updated_by = self.request.user
        else:
            obj.created_by = self.request.user
        if hasattr(obj, 'save_with_business_rules'):
            try:
                self.object = obj.save_with_business_rules(user=self.request.user)
            except ValidationError as exc:
                form.add_error(None, exc)
                return self.form_invalid(form)
        else:
            self.object = obj
            self.object.save()
            form.save_m2m()
        action = AuditLog.Action.UPDATE if before else AuditLog.Action.CREATE
        write_audit(actor=self.request.user, tenant=self.request.tenant, action=action, instance=self.object, before=before, after=snapshot(self.object))
        messages.success(self.request, 'Data berhasil disimpan.')
        return redirect(self.get_success_url())

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field_name, field in form.fields.items():
            queryset = getattr(field, 'queryset', None)
            if queryset is not None and hasattr(queryset.model, 'tenant'):
                field.queryset = queryset.filter(tenant=self.request.tenant, is_deleted=False)
                if form.__class__.__name__ == 'ArmadaForm' and field_name == 'driver':
                    from master.models import StakeHolder
                    field.queryset = field.queryset.filter(jenis=StakeHolder.StakeHolderType.KARYAWAN)
                if form.__class__.__name__ in {'FuelPurchaseForm', 'CashTransactionForm'} and field_name == 'armada':
                    field.queryset = field.queryset.select_related('driver')
                if form.__class__.__name__ == 'FuelPurchaseForm' and field_name == 'driver':
                    from master.models import StakeHolder
                    field.queryset = field.queryset.filter(jenis=StakeHolder.StakeHolderType.KARYAWAN)
                if form.__class__.__name__ == 'EmployeeCashAdvanceForm' and field_name == 'karyawan':
                    from master.models import StakeHolder
                    field.queryset = field.queryset.filter(jenis=StakeHolder.StakeHolderType.KARYAWAN)
                if form.__class__.__name__ == 'CustomerInvoiceForm' and field_name == 'customer':
                    from master.models import StakeHolder
                    field.queryset = field.queryset.filter(jenis=StakeHolder.StakeHolderType.CUSTOMER)
                if form.__class__.__name__ == 'EmployeeCashAdvanceForm' and field_name == 'perkiraan_pinjaman':
                    field.queryset = field.queryset.filter(kode__in=['1030100', '1030200'])
                if form.__class__.__name__ == 'LoanDebtForm' and field_name == 'perkiraan_hutang':
                    from django.db.models import Exists, OuterRef, Q
                    from master.models import ChartOfAccount
                    child_accounts = ChartOfAccount.objects.filter(
                        tenant=self.request.tenant,
                        is_deleted=False,
                        parent=OuterRef('pk'),
                    )
                    field.queryset = field.queryset.filter(kelompok='KEWAJIBAN').annotate(has_children=Exists(child_accounts)).filter(has_children=False)
                if form.__class__.__name__ == 'LoanReceivableForm' and field_name == 'perkiraan_piutang':
                    from django.db.models import Exists, OuterRef, Q
                    from master.models import ChartOfAccount
                    child_accounts = ChartOfAccount.objects.filter(
                        tenant=self.request.tenant,
                        is_deleted=False,
                        parent=OuterRef('pk'),
                    )
                    field.queryset = field.queryset.filter(kelompok='PIUTANG').annotate(has_children=Exists(child_accounts)).filter(has_children=False)
                if form.__class__.__name__ == 'LoanReceivablePaymentForm' and field_name == 'piutang_pinjaman':
                    current_rec_id = getattr(getattr(self, 'object', None), 'piutang_pinjaman_id', None)
                    field.queryset = (
                        field.queryset.filter(status_lunas='Belum') | field.queryset.filter(pk=current_rec_id)
                    )
                if form.__class__.__name__ == 'LoanDebtPaymentForm' and field_name == 'hutang_pinjaman':
                    current_debt_id = getattr(getattr(self, 'object', None), 'hutang_pinjaman_id', None)
                    field.queryset = (
                        field.queryset.filter(status_lunas='Belum') | field.queryset.filter(pk=current_debt_id)
                    )
                if form.__class__.__name__ == 'EmployeeCashAdvancePaymentForm' and field_name == 'kas_bon_karyawan':
                    current_cash_advance_id = getattr(getattr(self, 'object', None), 'kas_bon_karyawan_id', None)
                    from django.db.models import Case, DecimalField, ExpressionWrapper, F, Value, When
                    current_nominal = getattr(getattr(self, 'object', None), 'nominal', 0) or 0
                    field.queryset = (
                        field.queryset.filter(status_lunas='Belum') | field.queryset.filter(pk=current_cash_advance_id)
                    ).annotate(
                        display_saldo=ExpressionWrapper(
                            F('nominal') - F('pelunasan') + Case(
                                When(pk=current_cash_advance_id, then=Value(current_nominal)),
                                default=Value(0),
                                output_field=DecimalField(max_digits=18, decimal_places=2),
                            ),
                            output_field=DecimalField(max_digits=18, decimal_places=2),
                        )
                    )
                if form.__class__.__name__ == 'CustomerInvoicePaymentForm' and field_name == 'tagihan_customer':
                    current_invoice_id = getattr(getattr(self, 'object', None), 'tagihan_customer_id', None)
                    from django.db.models import Case, DecimalField, ExpressionWrapper, F, Value, When
                    current_total = (getattr(getattr(self, 'object', None), 'nominal_kas', 0) or 0) + (getattr(getattr(self, 'object', None), 'pph', 0) or 0)
                    field.queryset = (
                        field.queryset.filter(status_lunas='Belum') | field.queryset.filter(pk=current_invoice_id)
                    ).annotate(
                        display_saldo=ExpressionWrapper(
                            F('total') - F('pelunasan') + Case(
                                When(pk=current_invoice_id, then=Value(current_total)),
                                default=Value(0),
                                output_field=DecimalField(max_digits=18, decimal_places=2),
                            ),
                            output_field=DecimalField(max_digits=18, decimal_places=2),
                        )
                    )
                if form.__class__.__name__ == 'ChartOfAccountForm' and field_name == 'parent' and self.object and self.object.pk:
                    excluded_ids = [self.object.pk]
                    pending = list(self.object.children.filter(is_deleted=False).values_list('pk', flat=True))
                    while pending:
                        child_id = pending.pop()
                        excluded_ids.append(child_id)
                        pending.extend(field.queryset.model.objects.filter(parent_id=child_id, is_deleted=False).values_list('pk', flat=True))
                    field.queryset = field.queryset.exclude(pk__in=excluded_ids)
                if (
                    (form.__class__.__name__ == 'BankAccountForm' and field_name == 'akun')
                    or (form.__class__.__name__ == 'TransactionTypeForm' and field_name == 'akun')
                    or (form.__class__.__name__ == 'CashTransactionForm' and field_name == 'akun_transaksi')
                ):
                    from django.db.models import Exists, OuterRef
                    from master.models import ChartOfAccount
                    child_accounts = ChartOfAccount.objects.filter(
                        tenant=self.request.tenant,
                        is_deleted=False,
                        parent=OuterRef('pk'),
                    )
                    field.queryset = field.queryset.filter(is_active=True).annotate(
                        has_children=Exists(child_accounts),
                    ).filter(has_children=False)
                plain_select_fields = {
                    ('BankAccountForm', 'akun'),
                    ('TransactionTypeForm', 'akun'),
                    ('CashTransactionForm', 'akun_transaksi'),
                    ('CashTransactionForm', 'bank'),
                    ('ChartOfAccountForm', 'parent'),
                    ('FuelPurchaseForm', 'bank'),
                    ('FuelPurchaseForm', 'driver'),
                    ('BankTransactionForm', 'bank_utama'),
                    ('BankTransactionForm', 'jenis_transaksi'),
                    ('BankTransactionForm', 'bank_tujuan'),
                    ('EmployeeCashAdvanceForm', 'bank'),
                    ('EmployeeCashAdvanceForm', 'perkiraan_pinjaman'),
                    ('EmployeeCashAdvanceForm', 'karyawan'),
                    ('EmployeeCashAdvancePaymentForm', 'bank'),
                    ('CustomerInvoicePaymentForm', 'bank'),
                    ('CustomerInvoicePaymentForm', 'tagihan_customer'),
                    ('CustomerInvoiceForm', 'customer'),
                }
                use_lookup = (form.__class__.__name__, field_name) not in plain_select_fields
                if use_lookup and field.widget.__class__.__name__ != 'HiddenInput':
                    field.widget.attrs['data-lookup'] = 'true'
                    field.widget.attrs['lookup'] = 'true'
            if isinstance(field, forms.DateField):
                field.input_formats = ['%Y-%m-%d']
                field.widget = forms.DateInput(format='%Y-%m-%d', attrs=field.widget.attrs)
                field.widget.input_type = 'date'
                if not self.object and form.__class__.__name__ == 'ClosingPeriodForm' and field_name == 'tanggal':
                    from accounting.services import expected_closing_date
                    field.initial = expected_closing_date(self.request.tenant)
                if not self.object and field_name == 'tanggal' and not field.initial:
                    field.initial = timezone.localdate()
            css = 'w-full rounded border px-3 py-2 text-sm'
            if field.widget.__class__.__name__ == 'CheckboxInput':
                css = 'rounded border'
            field.widget.attrs.setdefault('class', css)
        return form


class TenantDeleteMixin(TenantRequiredMixin):
    protected_message = 'Data tidak bisa dihapus karena sudah dipakai di data lain.'

    def form_valid(self, form):
        self.object = self.get_object()
        before = snapshot(self.object)
        try:
            if hasattr(self.object, 'delete_with_business_rules'):
                self.object.delete_with_business_rules(user=self.request.user)
            else:
                self.object.delete()
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        except ProtectedError:
            form.add_error(None, self.protected_message)
            return self.form_invalid(form)
        write_audit(actor=self.request.user, tenant=self.request.tenant, action=AuditLog.Action.DELETE, instance=self.object, before=before, after=None)
        messages.success(self.request, 'Data berhasil dihapus.')
        return redirect(self.get_success_url())


class CrudConfig:
    def __init__(self, *, model, form_class, title, list_display, search_fields=None, success_url_name=None, detail_url_name=None, date_filter_field=None, date_filter_default='month', list_labels=None, list_pdf_widths=None, hide_list_edit=False, list_actions=None, fixed_filters=None, fixed_values=None):
        self.model = model
        self.form_class = form_class
        self.title = title
        self.list_display = list_display
        self.list_labels = list_labels or {}
        self.list_pdf_widths = list_pdf_widths
        self.search_fields = search_fields or []
        self.success_url_name = success_url_name
        self.detail_url_name = detail_url_name
        self.hide_list_edit = hide_list_edit
        self.list_actions = list_actions or []
        self.fixed_filters = fixed_filters or {}
        self.fixed_values = fixed_values or {}
        self.date_filter_default = date_filter_default
        self.date_filter_field = date_filter_field if date_filter_field is not None else self.detect_date_filter_field()

    def detect_date_filter_field(self):
        field_names = {field.name for field in self.model._meta.fields}
        return 'tanggal' if 'tanggal' in field_names else None

    def get_list_headers(self):
        headers = []
        for field_name in self.list_display:
            label = self.list_labels.get(field_name)
            if label is None:
                try:
                    label = self.model._meta.get_field(field_name).verbose_name
                except Exception:
                    label = field_name.replace('_', ' ')
                label = str(label).title()
            headers.append((field_name, label))
        return headers

def build_crud_views(config):
    crud_config = config
    class GeneratedListView(TenantQuerysetMixin, ListView):
        config = crud_config
        title = crud_config.title
        model = crud_config.model
        template_name = 'crud/list.html'
        paginate_by = 20
        search_fields = config.search_fields
        date_filter_field = config.date_filter_field
        date_filter_default = config.date_filter_default
        fixed_filters = config.fixed_filters

        def get(self, request, *args, **kwargs):
            export = request.GET.get('export')
            if export in {'excel', 'pdf'}:
                queryset = self.get_queryset()
                headers = config.get_list_headers()
                labels = [label for _, label in headers]
                number_columns = [index for index, (field_name, _) in enumerate(headers) if is_money_field(field_name)]
                rows = []
                for obj in queryset:
                    row = []
                    for field_name, _ in headers:
                        value = get_attr(obj, field_name)
                        if is_money_field(field_name):
                            value = format_money(value)
                        row.append(value)
                    rows.append(row)
                filename = config.title.lower().replace(' ', '-')
                if export == 'excel':
                    return excel_response(f'{filename}.xls', config.title, labels, rows, tenant=request.tenant, number_columns=number_columns)
                return pdf_response(f'{filename}.pdf', config.title, labels, rows, tenant=request.tenant, number_columns=number_columns, col_widths=config.list_pdf_widths)
            return super().get(request, *args, **kwargs)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context.update({
                'title': config.title,
                'list_display': config.list_display,
                'list_headers': config.get_list_headers(),
                'detail_url_name': config.detail_url_name,
                'hide_list_edit': config.hide_list_edit,
                'list_actions': config.list_actions,
                'date_filter_field': config.date_filter_field,
                'start_date': getattr(self, 'effective_start_date', '') or self.request.GET.get('start_date', '') or (timezone.localdate().replace(month=1, day=1).isoformat() if config.date_filter_field and config.date_filter_default == 'year' else timezone.localdate().replace(day=1).isoformat() if config.date_filter_field else ''),
                'end_date': getattr(self, 'effective_end_date', '') or self.request.GET.get('end_date', '') or (timezone.localdate().replace(month=12, day=31).isoformat() if config.date_filter_field and config.date_filter_default == 'year' else timezone.localdate().isoformat() if config.date_filter_field else ''),
                'q': self.request.GET.get('q', ''),
            })
            return context

    class GeneratedCreateView(TenantFormMixin, CreateView):
        model = config.model
        form_class = config.form_class
        template_name = 'crud/form.html'
        fixed_values = config.fixed_values

        def get_success_url(self):
            return reverse_lazy(config.success_url_name)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context.update({'title': f'Tambah {config.title}', 'cancel_url': reverse_lazy(config.success_url_name), 'form_model_name': config.model._meta.model_name})
            populate_form_context(context, config, self.request, form=kwargs.get('form') or context.get('form'))
            return context

    class GeneratedUpdateView(TenantFormMixin, UpdateView):
        model = config.model
        form_class = config.form_class
        template_name = 'crud/form.html'
        slug_field = 'uuid'
        slug_url_kwarg = 'uuid'
        fixed_values = config.fixed_values

        def get_queryset(self):
            return super().get_queryset().filter(tenant=self.request.tenant, is_deleted=False, **config.fixed_filters)

        def get_success_url(self):
            return reverse_lazy(config.success_url_name)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context.update({'title': f'Edit {config.title}', 'cancel_url': reverse_lazy(config.success_url_name), 'form_model_name': config.model._meta.model_name})
            populate_form_context(context, config, self.request, form=kwargs.get('form') or context.get('form'), obj=getattr(self, 'object', None))
            return context

    class GeneratedDeleteView(TenantDeleteMixin, DeleteView):
        model = config.model
        template_name = 'crud/confirm_delete.html'
        slug_field = 'uuid'
        slug_url_kwarg = 'uuid'

        def get_queryset(self):
            return super().get_queryset().filter(tenant=self.request.tenant, is_deleted=False, **config.fixed_filters)

        def get_success_url(self):
            return reverse_lazy(config.success_url_name)

        def get_context_data(self, **kwargs):
            context = super().get_context_data(**kwargs)
            context.update({'title': f'Hapus {config.title}', 'cancel_url': reverse_lazy(config.success_url_name)})
            return context

    return GeneratedListView, GeneratedCreateView, GeneratedUpdateView, GeneratedDeleteView






