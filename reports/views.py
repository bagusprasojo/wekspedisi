import csv
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from accounting.models import Journal
from core.exporters import excel_response, legacy_report_excel_response, legacy_report_pdf_response, pdf_response
from core.templatetags.crud_extras import format_money
from master.models import Armada, BankAccount, ChartOfAccount
from reports import services

ZERO = Decimal('0')


def require_tenant(request):
    if request.user.is_superuser and request.tenant is None:
        raise PermissionDenied('Superadmin tidak berada di tenant. Gunakan menu Platform.')
    if request.tenant is None:
        raise PermissionDenied('User belum terhubung ke tenant.')


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def report_filters(request):
    return {
        'start_date': parse_date(request.GET.get('start_date')),
        'end_date': parse_date(request.GET.get('end_date')),
    }


def month_report_filters(request):
    today = date.today()
    return {
        'start_date': parse_date(request.GET.get('start_date')) or today.replace(day=1),
        'end_date': parse_date(request.GET.get('end_date')) or today,
    }


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@login_required
def index(request):
    require_tenant(request)
    return render(request, 'reports/index.html', {'title': 'Laporan'})


@login_required
def daftar_jurnal(request):
    require_tenant(request)
    filters = month_report_filters(request)
    journals = services.daftar_jurnal(request.tenant, filters['start_date'], filters['end_date'])
    totals = journals.aggregate(total_debet=Sum('lines__debet'), total_kredit=Sum('lines__kredit'))
    total_debet = totals['total_debet'] or ZERO
    total_kredit = totals['total_kredit'] or ZERO
    if request.GET.get('export') == 'csv':
        rows = [
            [journal.tanggal, journal.no_jurnal, journal.transaksi, journal.keterangan, journal.total_debet or 0, journal.total_kredit or 0]
            for journal in journals
        ]
        rows.append(['', '', '', 'Total', total_debet, total_kredit])
        return csv_response('daftar-jurnal.csv', ['Tanggal', 'No Jurnal', 'Jenis Transaksi', 'Keterangan', 'Total Debet', 'Total Kredit'], rows)
    paginator = Paginator(journals, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'reports/daftar_jurnal.html',
        {
            'title': 'Daftar Jurnal',
            'journals': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_debet': total_debet,
            'total_kredit': total_kredit,
            **filters,
        },
    )


@login_required
def daftar_jurnal_detail(request, uuid):
    require_tenant(request)
    journal = get_object_or_404(
        Journal.objects.filter(tenant=request.tenant, is_deleted=False).prefetch_related('lines__perkiraan'),
        uuid=uuid,
    )
    return render(request, 'reports/daftar_jurnal_detail.html', {'title': f'Detail Jurnal {journal.no_jurnal}', 'journal': journal})


@login_required
def buku_besar(request):
    require_tenant(request)
    filters = month_report_filters(request)
    child_accounts = ChartOfAccount.objects.filter(tenant=request.tenant, is_deleted=False, parent=OuterRef('pk'))
    accounts = (
        ChartOfAccount.objects.filter(tenant=request.tenant, is_deleted=False, is_active=True)
        .annotate(has_children=Exists(child_accounts))
        .filter(has_children=False)
        .order_by('kode')
    )
    account = None
    account_id = request.GET.get('account')
    if account_id:
        account = accounts.filter(pk=account_id).first()
    rows = services.buku_besar(request.tenant, filters['start_date'], filters['end_date'], account=account)
    opening = services.opening_balance(request.tenant, account, filters['start_date']) if account else ZERO

    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        extra_lines = []
        if account:
            extra_lines = [
                f'Kode Akun : {account.kode}     Nama Akun : {account.nama}',
                f'Saldo Normal : {account.saldo_normal}     Saldo Awal : {format_money(opening)}',
            ]
        headers = ['Tanggal', 'No Jurnal', 'Keterangan', 'Kode Akun', 'Akun', 'Debet', 'Kredit', 'Saldo']
        export_rows = [
            [
                (row['line'].journal.tanggal.strftime('%d/%m/%Y'), 'center'),
                (row['line'].journal.no_jurnal, 'center'),
                (row['line'].journal.keterangan, 'text'),
                (row['line'].perkiraan.kode, 'center'),
                (row['line'].perkiraan.nama, 'text'),
                (row['line'].debet, 'number'),
                (row['line'].kredit, 'number'),
                (row['saldo'] if row['saldo'] is not None else '', 'number'),
            ]
            for row in rows
        ]
        totals = [
            (0, 5, 'Total   ', 'text', 5),
            (sum((row['line'].debet for row in rows), ZERO), 'number', 1),
            (sum((row['line'].kredit for row in rows), ZERO), 'number', 1),
            ('', 'text', 1),
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'buku-besar.xls',
                'Buku Besar',
                request.tenant,
                period,
                headers,
                export_rows,
                totals,
                extra_lines=extra_lines,
            )
        return legacy_report_pdf_response(
            'buku-besar.pdf',
            'Buku Besar',
            request.tenant,
            period,
            [
                {'label': 'Tanggal', 'x': 0, 'w': 60, 'max': 8},
                {'label': 'No Jurnal', 'x': 60, 'w': 80, 'max': 12},
                {'label': 'Keterangan', 'x': 140, 'w': 220, 'max': 40},
                {'label': 'Kode', 'x': 360, 'w': 50, 'max': 8},
                {'label': 'Akun', 'x': 410, 'w': 140, 'max': 25},
                {'label': 'Debet', 'x': 550, 'w': 80, 'max': 12},
                {'label': 'Kredit', 'x': 630, 'w': 80, 'max': 12},
                {'label': 'Saldo', 'x': 710, 'w': 90, 'max': 12},
            ],
            export_rows,
            totals,
            extra_lines=extra_lines,
            landscape=True,
        )
    return render(
        request,
        'reports/buku_besar.html',
        {
            'title': 'Buku Besar',
            'accounts': accounts,
            'selected_account': account,
            'opening': opening,
            'rows': rows,
            **filters,
        },
    )


@login_required
def neraca_saldo(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Neraca Saldo harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    include_closing = request.GET.get('include_closing') == '1'
    rows = services.trial_balance(request.tenant, filters['start_date'], filters['end_date'], include_closing=include_closing)
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        headers = ['Kode', 'Nama Perkiraan', 'Pos', 'Saldo Awal Debet', 'Saldo Awal Kredit', 'Mutasi Debet', 'Mutasi Kredit', 'Saldo Akhir Debet', 'Saldo Akhir Kredit']
        export_rows = [
            [
                (row['account'].kode, 'center'),
                (row['account'].nama, 'text'),
                (row['account'].saldo_normal, 'center'),
                (row['sow_debet'], 'number'),
                (row['sow_kredit'], 'number'),
                (row['debet'], 'number'),
                (row['kredit'], 'number'),
                (row['akhir_debet'], 'number'),
                (row['akhir_kredit'], 'number'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        totals = [
            (0, 3, 'Total   ', 'text', 3),
            (sum((r['sow_debet'] for r in rows), ZERO), 'number', 1),
            (sum((r['sow_kredit'] for r in rows), ZERO), 'number', 1),
            (sum((r['debet'] for r in rows), ZERO), 'number', 1),
            (sum((r['kredit'] for r in rows), ZERO), 'number', 1),
            (sum((r['akhir_debet'] for r in rows), ZERO), 'number', 1),
            (sum((r['akhir_kredit'] for r in rows), ZERO), 'number', 1),
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'neraca-saldo.xls',
                'Neraca Saldo',
                request.tenant,
                period,
                headers,
                export_rows,
                totals,
            )
        return legacy_report_pdf_response(
            'neraca-saldo.pdf',
            'Neraca Saldo',
            request.tenant,
            period,
            [
                {'label': 'Kode', 'x': 0, 'w': 50, 'max': 8},
                {'label': 'Nama Perkiraan', 'x': 50, 'w': 180, 'max': 30},
                {'label': 'Pos', 'x': 230, 'w': 40, 'max': 6},
                {'label': 'S.Awal (D)', 'x': 270, 'w': 75, 'max': 12},
                {'label': 'S.Awal (K)', 'x': 345, 'w': 75, 'max': 12},
                {'label': 'Mutasi (D)', 'x': 420, 'w': 75, 'max': 12},
                {'label': 'Mutasi (K)', 'x': 495, 'w': 75, 'max': 12},
                {'label': 'S.Akhir (D)', 'x': 570, 'w': 80, 'max': 12},
                {'label': 'S.Akhir (K)', 'x': 650, 'w': 80, 'max': 12},
            ],
            export_rows,
            totals,
            landscape=True,
        )
    return render(request, 'reports/neraca_saldo.html', {'title': 'Neraca Saldo', 'rows': rows, 'include_closing': include_closing, **filters})


@login_required
def saldo_bank(request):
    require_tenant(request)
    filters = report_filters(request)
    end_date = filters['end_date'] or date.today()
    filters['end_date'] = end_date
    first_of_month = end_date.replace(day=1)
    rows = services.saldo_bank(request.tenant, end_date)
    total_saldo = sum((row['saldo'] for row in rows), ZERO)
    period = f"s.d. {end_date.strftime('%d/%m/%Y')}"

    if request.GET.get('export') in {'excel', 'pdf'}:
        headers = ['No', 'Bank/Kas', 'No Rekening', 'Atas Nama', 'Kode Akun', 'Saldo']
        export_rows = [
            [
                (index, 'number'),
                (row['bank'].nama_bank, 'text'),
                (row['bank'].no_rekening, 'text'),
                (row['bank'].atas_nama, 'text'),
                (row['akun'].kode if row['akun'] else '', 'center'),
                (row['saldo'], 'number'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        totals = [('Total', 'text', 5), (total_saldo, 'number', 1)]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'saldo-bank.xls',
                'Saldo Bank Kas',
                request.tenant,
                period,
                headers,
                export_rows,
                totals,
            )
        return legacy_report_pdf_response(
            'saldo-bank.pdf',
            'Saldo Bank/Kas',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 32, 'max': 4},
                {'label': 'Bank/Kas', 'x': 32, 'w': 140, 'max': 24},
                {'label': 'No Rekening', 'x': 172, 'w': 110, 'max': 18},
                {'label': 'Atas Nama', 'x': 282, 'w': 150, 'max': 25},
                {'label': 'Kode', 'x': 432, 'w': 50, 'max': 8},
                {'label': 'Saldo', 'x': 482, 'w': 72, 'max': 12},
            ],
            export_rows,
            [(0, 482, 'Total  ', 'text', 5), (482, 72, total_saldo, 'number', 1)],
        )

    if request.GET.get('export') == 'csv':
        csv_rows = [[index, row['bank'].nama_bank, row['bank'].no_rekening, row['bank'].atas_nama, row['akun'].kode if row['akun'] else '', row['saldo']] for index, row in enumerate(rows, start=1)]
        csv_rows.append(['', '', '', '', 'Total', total_saldo])
        return csv_response('saldo-bank.csv', ['No', 'Bank/Kas', 'No Rekening', 'Atas Nama', 'Kode Akun', 'Saldo'], csv_rows)

    return render(
        request,
        'reports/saldo_bank.html',
        {
            'title': 'Saldo Bank/Kas',
            'rows': rows,
            'total_saldo': total_saldo,
            'first_of_month': first_of_month,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def rekap_transaksi_kas(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Transaksi Kas harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_transaksi_kas(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        headers = ['No', 'Tanggal', 'Account & Keterangan', 'Keluar', 'Masuk', 'Pc']
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (f'{row.akun_transaksi.kode} {row.akun_transaksi.nama}' + (f',{row.armada.kendaraan}' if row.armada else ''), 'text'),
                (row.nominal_keluar, 'number'),
                (row.nominal_masuk, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'rekap-transaksi-kas.xls',
                'Rekap Transaksi Kas',
                request.tenant,
                period,
                headers,
                export_rows,
                [
                    ('Total', 'text', 3),
                    (sum((row.nominal_keluar for row in rows), ZERO), 'number', 1),
                    (sum((row.nominal_masuk for row in rows), ZERO), 'number', 1),
                    ('', 'text', 1),
                ],
                header_color='#b6d2e9',
            )
        return legacy_report_pdf_response(
            'rekap-transaksi-kas.pdf',
            'Rekap Transaksi Kas',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 32, 'max': 4},
                {'label': 'Tanggal', 'x': 32, 'w': 55, 'max': 8},
                {'label': 'Account & Keterangan', 'x': 95, 'w': 244, 'max': 42},
                {'label': 'Keluar', 'x': 322, 'w': 80, 'max': 14},
                {'label': 'Masuk', 'x': 402, 'w': 82, 'max': 14},
                {'label': 'Pc', 'x': 484, 'w': 70, 'max': 13},
            ],
            export_rows,
            [
                (0, 322, 'Total   ', 'text', 3),
                (322, 80, sum((row.nominal_keluar for row in rows), ZERO), 'number', 1),
                (402, 82, sum((row.nominal_masuk for row in rows), ZERO), 'number', 1),
                (484, 70, '', 'text', 1),
            ],
            header_rgb=(0.71, 0.82, 0.91),
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_keluar = sum((row.nominal_keluar for row in rows), ZERO)
    total_masuk = sum((row.nominal_masuk for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_transaksi_kas.html',
        {
            'title': 'Rekap Transaksi Kas',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_keluar': total_keluar,
            'total_masuk': total_masuk,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def riwayat_pembelian_bbm(request):
    require_tenant(request)
    filters = month_report_filters(request)
    armadas = Armada.objects.filter(tenant=request.tenant, is_deleted=False).select_related('driver').order_by('nopol')
    armada = None
    armada_id = request.GET.get('armada')
    if armada_id:
        armada = armadas.filter(pk=armada_id).first()
    rows = services.riwayat_pembelian_bbm(request.tenant, filters['start_date'], filters['end_date'], armada=armada)
    if request.GET.get('export') in {'excel', 'pdf'}:
        headers = ['No', 'Tanggal', 'Driver', 'Keterangan', 'KM Awal', 'KM Akhir', 'Jarak Tempuh (KM)', 'Pengisian', 'Pc']
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (row.driver.nama if row.driver else '', 'text'),
                (row.keterangan, 'text'),
                (row.km_terakhir, 'number'),
                (row.km_sekarang, 'number'),
                (row.km_sekarang - row.km_terakhir, 'number'),
                (row.nominal_bbm, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        title = 'Riwayat Pembelian BBM'
        extra_lines = []
        if armada:
            extra_lines = [
                f'No. Polisi : {armada.nopol} Driver : {armada.driver.nama if armada.driver else ""}',
                f'Kendaraan : {armada.kendaraan}',
            ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'riwayat-pembelian-bbm.xls',
                title,
                request.tenant,
                period,
                headers,
                export_rows,
                [
                    ('Total', 'text', 7),
                    (sum((row.nominal_bbm for row in rows), ZERO), 'number', 1),
                    ('', 'text', 1),
                ],
                extra_lines=extra_lines,
                header_color='#61fafa',
            )
        return legacy_report_pdf_response(
            'riwayat-pembelian-bbm.pdf',
            title,
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 20, 'max': 4, 'size': 8, 'header_size': 9},
                {'label': 'Tanggal', 'x': 20, 'w': 59, 'max': 8, 'size': 8, 'header_size': 9},
                {'label': 'Driver', 'x': 79, 'w': 80, 'max': 14, 'size': 8, 'header_size': 9},
                {'label': 'Keterangan', 'x': 159, 'w': 118, 'max': 22, 'size': 8, 'header_size': 9},
                {'label': 'KM\nAwal', 'x': 277, 'w': 50, 'max': 8, 'size': 8, 'header_size': 9},
                {'label': 'KM\nAkhir', 'x': 327, 'w': 50, 'max': 8, 'size': 8, 'header_size': 9},
                {'label': 'Jarak\nTempuh (KM)', 'x': 377, 'w': 55, 'max': 10, 'size': 8, 'header_size': 8},
                {'label': 'Pengisian', 'x': 432, 'w': 62, 'max': 10, 'size': 8, 'header_size': 9},
                {'label': 'Pc', 'x': 494, 'w': 60, 'max': 13, 'size': 8, 'header_size': 9},
            ],
            export_rows,
            [
                (0, 432, 'Total  ', 'text', 7),
                (432, 122, sum((row.nominal_bbm for row in rows), ZERO), 'number', 2),
            ],
            extra_lines=extra_lines,
            header_rgb=(0.38, 0.98, 0.98),
        )
    return render(
        request,
        'reports/riwayat_pembelian_bbm.html',
        {'title': 'Riwayat Pembelian BBM', 'rows': rows, 'armadas': armadas, 'selected_armada': armada, **filters},
    )

@login_required
def rekap_transaksi_bank(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Transaksi Bank harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_transaksi_bank(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (f'{row.bank_utama.nama_bank},{row.bank_utama.no_rekening},{row.uraian}', 'text'),
                (row.debet, 'number'),
                (row.kredit, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
                (row.jenis_transaksi.kode, 'center'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'rekap-transaksi-bank.xls',
                'Rekap Transaksi Bank',
                request.tenant,
                period,
                ['No', 'Tanggal', 'Bank & Keterangan', 'Debet', 'Kredit', 'Pc', 'Kode'],
                export_rows,
                [('Grand Total', 'text', 3), (sum((row.debet for row in rows), ZERO), 'number', 1), (sum((row.kredit for row in rows), ZERO), 'number', 1), ('', 'text', 2)],
            )
        return legacy_report_pdf_response(
            'rekap-transaksi-bank.pdf',
            'Rekap Transaksi Bank',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 32, 'max': 4},
                {'label': 'Tanggal', 'x': 32, 'w': 63, 'max': 8},
                {'label': 'Bank & Keterangan', 'x': 95, 'w': 225, 'max': 40},
                {'label': 'Debet', 'x': 320, 'w': 80, 'max': 14},
                {'label': 'Kredit', 'x': 400, 'w': 82, 'max': 14},
                {'label': 'Pc', 'x': 482, 'w': 32, 'max': 6},
                {'label': 'Kode', 'x': 514, 'w': 40, 'max': 8},
            ],
            export_rows,
            [(0, 320, 'Grand Total  ', 'text', 3), (320, 80, sum((row.debet for row in rows), ZERO), 'number', 1), (400, 82, sum((row.kredit for row in rows), ZERO), 'number', 1), (482, 72, '', 'text', 2)],
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_debet = sum((row.debet for row in rows), ZERO)
    total_kredit = sum((row.kredit for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_transaksi_bank.html',
        {
            'title': 'Rekap Transaksi Bank',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_debet': total_debet,
            'total_kredit': total_kredit,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def rekening_koran(request):
    require_tenant(request)
    filters = month_report_filters(request)
    banks = BankAccount.objects.filter(tenant=request.tenant, is_deleted=False).order_by('nama_bank', 'no_rekening')
    bank = None
    bank_id = request.GET.get('bank')
    if bank_id:
        bank = banks.filter(pk=bank_id).first()
    start = filters['start_date']
    end = filters['end_date']
    if start.year != end.year or start.month != end.month:
        return render(
            request,
            'reports/rekening_koran.html',
            {
                'title': 'Rekening Koran',
                'rows': [],
                'banks': banks,
                'selected_bank': bank,
                'saldo_awal': ZERO,
                'error_message': 'Tanggal awal dan akhir harus dalam bulan dan tahun yang sama.',
                **filters,
            },
        )
    rows = services.rekening_koran(request.tenant, filters['start_date'], filters['end_date'], bank=bank)
    saldo_awal = services.rekening_koran_saldo_awal(request.tenant, filters['start_date'], bank=bank)
    running = saldo_awal
    display_rows = []
    for row in rows:
        running += row['kredit'] - row['debet']
        display_rows.append({**row, 'saldo': running})
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        extra_lines = []
        if bank:
            extra_lines = [
                f'No Rekening : {bank.no_rekening}     Nama Bank : {bank.nama_bank}',
                f'Atas Nama : {bank.atas_nama}     Saldo Awal : {format_money(saldo_awal)}',
            ]
        export_rows = [
            [
                (index, 'number'),
                (row['tanggal'].strftime('%d/%m/%Y'), 'center'),
                (row['kode'], 'center'),
                (row['uraian'], 'text'),
                (row['debet'], 'number'),
                (row['kredit'], 'number'),
                (row['saldo'], 'number'),
                (row['user_create'], 'text'),
            ]
            for index, row in enumerate(display_rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'rekening-koran.xls',
                'Rekening Koran',
                request.tenant,
                period,
                ['No', 'Tanggal', 'Kode', 'Uraian', 'Debet', 'Kredit', 'Saldo', 'Pc'],
                export_rows,
                [],
                extra_lines=extra_lines,
            )
        return legacy_report_pdf_response(
            'rekening-koran.pdf',
            'Rekening Koran',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 30, 'max': 4},
                {'label': 'Tanggal', 'x': 30, 'w': 65, 'max': 8},
                {'label': 'Kode', 'x': 100, 'w': 50, 'max': 8},
                {'label': 'Uraian', 'x': 150, 'w': 344, 'max': 34},
                {'label': 'Debet', 'x': 494, 'w': 75, 'max': 12},
                {'label': 'Kredit', 'x': 584, 'w': 75, 'max': 12},
                {'label': 'Saldo', 'x': 674, 'w': 90, 'max': 12},
                {'label': 'Pc', 'x': 764, 'w': 60, 'max': 6},
            ],
            export_rows,
            [],
            extra_lines=extra_lines,
            landscape=True,
        )
    paginator = Paginator(display_rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_debet = sum((r['debet'] for r in rows), ZERO)
    total_kredit = sum((r['kredit'] for r in rows), ZERO)
    return render(
        request,
        'reports/rekening_koran.html',
        {
            'title': 'Rekening Koran',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_debet': total_debet,
            'total_kredit': total_kredit,
            'final_saldo': running,
            'banks': banks,
            'selected_bank': bank,
            'saldo_awal': saldo_awal,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def rekap_transaksi_kas_bon(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Transaksi Kas Bon harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_transaksi_kas_bon(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row['tanggal'].strftime('%d/%m/%y'), 'center'),
                (row['karyawan'], 'text'),
                (row['no_register'], 'text'),
                (row['akun_kas'], 'text'),
                (row['keterangan'], 'text'),
                (row['keluar'], 'number'),
                (row['masuk'], 'number'),
                (row['created_by'], 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'rekap-transaksi-kas-bon.xls',
                'Rekap Transaksi Kas Bon',
                request.tenant,
                period,
                ['No', 'Tanggal', 'Karyawan', 'No Register', 'Akun Kas', 'Keterangan', 'Keluar', 'Masuk', 'Pc'],
                export_rows,
                [('Grand Total', 'text', 6), (sum((row['keluar'] for row in rows), ZERO), 'number', 1), (sum((row['masuk'] for row in rows), ZERO), 'number', 1), ('', 'text', 1)],
            )
        return legacy_report_pdf_response(
            'rekap-transaksi-kas-bon.pdf',
            'Rekap Transaksi Kas Bon',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 25, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 25, 'w': 55, 'max': 8, 'size': 8},
                {'label': 'Karyawan', 'x': 80, 'w': 85, 'max': 16, 'size': 8},
                {'label': 'No Register', 'x': 165, 'w': 80, 'max': 15, 'size': 8},
                {'label': 'Keterangan', 'x': 245, 'w': 105, 'max': 20, 'size': 8},
                {'label': 'Keluar', 'x': 350, 'w': 90, 'max': 14, 'size': 8},
                {'label': 'Masuk', 'x': 440, 'w': 82, 'max': 14, 'size': 8},
                {'label': 'Pc', 'x': 522, 'w': 32, 'max': 6, 'size': 8},
            ],
            [
                [(row[0][0], row[0][1]), (row[1][0], row[1][1]), (row[2][0], row[2][1]), (row[3][0], row[3][1]), (row[5][0], row[5][1]), (row[6][0], row[6][1]), (row[7][0], row[7][1]), (row[8][0], row[8][1])]
                for row in export_rows
            ],
            [(0, 350, 'Grand Total', 'text', 5), (350, 90, sum((row['keluar'] for row in rows), ZERO), 'number', 1), (440, 82, sum((row['masuk'] for row in rows), ZERO), 'number', 1), (522, 32, '', 'text', 1)],
            header_rgb=(0.90, 0.95, 0.98),
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_keluar = sum((row['keluar'] for row in rows), ZERO)
    total_masuk = sum((row['masuk'] for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_transaksi_kas_bon.html',
        {
            'title': 'Rekap Transaksi Kas Bon',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_keluar': total_keluar,
            'total_masuk': total_masuk,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def saldo_kas_bon(request):
    require_tenant(request)
    filters = report_filters(request)
    end_date = filters['end_date'] or date.today()
    rows = services.saldo_kas_bon(request.tenant, end_date)
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = end_date.strftime('%d/%m/%Y')
        export_rows = [
            [
                (index, 'number'),
                (row['tanggal'].strftime('%d/%m/%y'), 'center'),
                (row['no_register'], 'text'),
                (row['nama_karyawan'], 'text'),
                (row['alamat_karyawan'], 'text'),
                (row['nominal'], 'number'),
                (row['pelunasan'], 'number'),
                (row['saldo'], 'number'),
                (row['created_by'], 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'saldo-kas-bon.xls',
                'Rekap Saldo Kas Bon',
                request.tenant,
                period,
                ['No', 'Tanggal', 'No Register', 'Karyawan', 'Alamat', 'Nominal', 'Pelunasan', 'Saldo', 'Pc'],
                export_rows,
                [('Grand Total', 'text', 7), (sum((row['saldo'] for row in rows), ZERO), 'number', 1), ('', 'text', 1)],
            )
        return legacy_report_pdf_response(
            'saldo-kas-bon.pdf',
            'Rekap Saldo Kas Bon',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 25, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 25, 'w': 55, 'max': 8, 'size': 8},
                {'label': 'No Register', 'x': 80, 'w': 80, 'max': 15, 'size': 8},
                {'label': 'Karyawan', 'x': 160, 'w': 105, 'max': 20, 'size': 8},
                {'label': 'Nominal', 'x': 265, 'w': 85, 'max': 13, 'size': 8},
                {'label': 'Pelunasan', 'x': 350, 'w': 90, 'max': 13, 'size': 8},
                {'label': 'Saldo', 'x': 440, 'w': 82, 'max': 13, 'size': 8},
                {'label': 'Pc', 'x': 522, 'w': 32, 'max': 6, 'size': 8},
            ],
            [
                [(row[0][0], row[0][1]), (row[1][0], row[1][1]), (row[2][0], row[2][1]), (row[3][0], row[3][1]), (row[5][0], row[5][1]), (row[6][0], row[6][1]), (row[7][0], row[7][1]), (row[8][0], row[8][1])]
                for row in export_rows
            ],
            [(0, 440, 'Grand Total', 'text', 6), (440, 82, sum((row['saldo'] for row in rows), ZERO), 'number', 1), (522, 32, '', 'text', 1)],
            header_rgb=(0.90, 0.95, 0.98),
        )
    return render(request, 'reports/saldo_kas_bon.html', {'title': 'Rekap Saldo Kas Bon', 'rows': rows, 'end_date': end_date})

@login_required
def rekap_invoice_customer(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Invoice Customer harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_invoice_customer(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (row.no_invoice, 'text'),
                (row.customer.nama, 'text'),
                (row.pekerjaan, 'text'),
                (row.nilai_pekerjaan, 'number'),
                (row.ppn, 'number'),
                (row.total, 'number'),
                (row.pelunasan, 'number'),
                (row.saldo, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        headers = ['No', 'Tanggal', 'No Invoice', 'Customer', 'Pekerjaan', 'DPP', 'PPN', 'Total', 'Pelunasan', 'Saldo', 'Pc']
        totals = [
            ('Grand Total', 'text', 5),
            (sum((row.nilai_pekerjaan for row in rows), ZERO), 'number', 1),
            (sum((row.ppn for row in rows), ZERO), 'number', 1),
            (sum((row.total for row in rows), ZERO), 'number', 1),
            (sum((row.pelunasan for row in rows), ZERO), 'number', 1),
            (sum((row.saldo for row in rows), ZERO), 'number', 1),
            ('', 'text', 1),
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response('rekap-invoice-customer.xls', 'Rekap Invoice Customer', request.tenant, period, headers, export_rows, totals)
        return legacy_report_pdf_response(
            'rekap-invoice-customer.pdf',
            'Rekap Invoice Customer',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 24, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 24, 'w': 52, 'max': 8, 'size': 8},
                {'label': 'No Invoice', 'x': 76, 'w': 74, 'max': 14, 'size': 8},
                {'label': 'Customer', 'x': 150, 'w': 92, 'max': 18, 'size': 8},
                {'label': 'Pekerjaan', 'x': 242, 'w': 94, 'max': 18, 'size': 8},
                {'label': 'DPP', 'x': 336, 'w': 54, 'max': 9, 'size': 8},
                {'label': 'PPN', 'x': 390, 'w': 50, 'max': 9, 'size': 8},
                {'label': 'Total', 'x': 440, 'w': 58, 'max': 10, 'size': 8},
                {'label': 'Saldo', 'x': 498, 'w': 58, 'max': 10, 'size': 8},
            ],
            [[*row[:8], row[9]] for row in export_rows],
            [(0, 336, 'Grand Total', 'text', 5), (336, 54, sum((row.nilai_pekerjaan for row in rows), ZERO), 'number', 1), (390, 50, sum((row.ppn for row in rows), ZERO), 'number', 1), (440, 58, sum((row.total for row in rows), ZERO), 'number', 1), (498, 58, sum((row.saldo for row in rows), ZERO), 'number', 1)],
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_dpp = sum((row.nilai_pekerjaan for row in rows), ZERO)
    total_ppn = sum((row.ppn for row in rows), ZERO)
    total_total = sum((row.total for row in rows), ZERO)
    total_pelunasan = sum((row.pelunasan for row in rows), ZERO)
    total_saldo = sum((row.saldo for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_invoice_customer.html',
        {
            'title': 'Rekap Invoice Customer',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_dpp': total_dpp,
            'total_ppn': total_ppn,
            'total_total': total_total,
            'total_pelunasan': total_pelunasan,
            'total_saldo': total_saldo,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def rekap_pembayaran_invoice_customer(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Pembayaran Invoice Customer harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_pembayaran_invoice_customer(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (row.no_register, 'text'),
                (row.tagihan_customer.no_invoice, 'text'),
                (row.tagihan_customer.customer.nama, 'text'),
                (row.sumber_dana, 'text'),
                (row.nominal_kas, 'number'),
                (row.pph, 'number'),
                (row.total_pembayaran, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        headers = ['No', 'Tanggal', 'No Register', 'No Invoice', 'Customer', 'Sumber Dana', 'Nominal Kas/Bank', 'PPH', 'Total', 'Pc']
        totals = [('Grand Total', 'text', 6), (sum((row.nominal_kas for row in rows), ZERO), 'number', 1), (sum((row.pph for row in rows), ZERO), 'number', 1), (sum((row.total_pembayaran for row in rows), ZERO), 'number', 1), ('', 'text', 1)]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response('rekap-pembayaran-invoice-customer.xls', 'Rekap Pembayaran Invoice Customer', request.tenant, period, headers, export_rows, totals)
        return legacy_report_pdf_response(
            'rekap-pembayaran-invoice-customer.pdf',
            'Rekap Pembayaran Invoice Customer',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 24, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 24, 'w': 52, 'max': 8, 'size': 8},
                {'label': 'No Register', 'x': 76, 'w': 72, 'max': 14, 'size': 8},
                {'label': 'No Invoice', 'x': 148, 'w': 72, 'max': 14, 'size': 8},
                {'label': 'Customer', 'x': 220, 'w': 92, 'max': 18, 'size': 8},
                {'label': 'Sumber Dana', 'x': 312, 'w': 84, 'max': 16, 'size': 8},
                {'label': 'Nominal', 'x': 396, 'w': 60, 'max': 10, 'size': 8},
                {'label': 'PPH', 'x': 456, 'w': 48, 'max': 9, 'size': 8},
                {'label': 'Total', 'x': 504, 'w': 52, 'max': 9, 'size': 8},
            ],
            [row[:9] for row in export_rows],
            [(0, 396, 'Grand Total', 'text', 6), (396, 60, sum((row.nominal_kas for row in rows), ZERO), 'number', 1), (456, 48, sum((row.pph for row in rows), ZERO), 'number', 1), (504, 52, sum((row.total_pembayaran for row in rows), ZERO), 'number', 1)],
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_nominal_kas = sum((row.nominal_kas for row in rows), ZERO)
    total_pph = sum((row.pph for row in rows), ZERO)
    total_pembayaran = sum((row.total_pembayaran for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_pembayaran_invoice_customer.html',
        {
            'title': 'Rekap Pembayaran Invoice Customer',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_nominal_kas': total_nominal_kas,
            'total_pph': total_pph,
            'total_pembayaran': total_pembayaran,
            'export_excel_pdf': True,
            **filters,
        },
    )

@login_required
def rekap_transaksi_hutang(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Transaksi Hutang harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_transaksi_hutang(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (row.no_register, 'text'),
                (row.pemberi_pinjaman.nama if row.pemberi_pinjaman else '', 'text'),
                (row.perkiraan_hutang.nama if row.perkiraan_hutang else '', 'text'),
                (row.sumber_dana, 'text'),
                (row.nominal, 'number'),
                (row.pelunasan, 'number'),
                (row.saldo, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        headers = ['No', 'Tanggal', 'No Register', 'Pemberi Pinjaman', 'Akun Hutang', 'Penerima Uang', 'Nominal', 'Pelunasan', 'Saldo', 'Pc']
        totals = [
            ('Grand Total', 'text', 6),
            (sum((row.nominal for row in rows), ZERO), 'number', 1),
            (sum((row.pelunasan for row in rows), ZERO), 'number', 1),
            (sum((row.saldo for row in rows), ZERO), 'number', 1),
            ('', 'text', 1),
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response('rekap-transaksi-hutang.xls', 'Rekap Transaksi Hutang', request.tenant, period, headers, export_rows, totals)
        return legacy_report_pdf_response(
            'rekap-transaksi-hutang.pdf',
            'Rekap Transaksi Hutang',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 25, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 25, 'w': 60, 'max': 8, 'size': 8},
                {'label': 'No Register', 'x': 85, 'w': 120, 'max': 25, 'size': 8},
                {'label': 'Pemberi Pinjaman', 'x': 205, 'w': 140, 'max': 25, 'size': 8},
                {'label': 'Akun Hutang', 'x': 345, 'w': 110, 'max': 20, 'size': 8},
                {'label': 'Penerima Uang', 'x': 455, 'w': 110, 'max': 20, 'size': 8},
                {'label': 'Nominal', 'x': 565, 'w': 75, 'max': 14, 'size': 8},
                {'label': 'Pelunasan', 'x': 640, 'w': 75, 'max': 14, 'size': 8},
                {'label': 'Saldo', 'x': 715, 'w': 75, 'max': 14, 'size': 8},
            ],
            [row[:9] for row in export_rows],
            [(0, 565, 'Grand Total', 'text', 6), (565, 75, sum((row.nominal for row in rows), ZERO), 'number', 1), (640, 75, sum((row.pelunasan for row in rows), ZERO), 'number', 1), (715, 75, sum((row.saldo for row in rows), ZERO), 'number', 1)],
            landscape=True,
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_nominal = sum((row.nominal for row in rows), ZERO)
    total_pelunasan = sum((row.pelunasan for row in rows), ZERO)
    total_saldo = sum((row.saldo for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_transaksi_hutang.html',
        {
            'title': 'Rekap Transaksi Hutang',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_nominal': total_nominal,
            'total_pelunasan': total_pelunasan,
            'total_saldo': total_saldo,
            'export_excel_pdf': True,
            **filters,
        },
    )


@login_required
def rekap_pembayaran_hutang(request):
    require_tenant(request)
    filters = month_report_filters(request)
    if filters['start_date'].year != filters['end_date'].year:
        from django.contrib import messages
        messages.warning(request, 'Periode Rekap Pembayaran Hutang harus berada pada tahun yang sama.')
        filters['end_date'] = date(filters['start_date'].year, 12, 31)
    rows = services.rekap_pembayaran_hutang(request.tenant, filters['start_date'], filters['end_date'])
    if request.GET.get('export') in {'excel', 'pdf'}:
        period = f"{filters['start_date'].strftime('%d/%m/%Y')} s.d. {filters['end_date'].strftime('%d/%m/%Y')}"
        export_rows = [
            [
                (index, 'number'),
                (row.tanggal.strftime('%d/%m/%y'), 'center'),
                (row.no_register, 'text'),
                (row.hutang_pinjaman.no_register, 'text'),
                (row.hutang_pinjaman.pemberi_pinjaman.nama if row.hutang_pinjaman.pemberi_pinjaman else '', 'text'),
                (row.sumber_dana, 'text'),
                (row.nominal, 'number'),
                (row.created_by.username if row.created_by else '', 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        headers = ['No', 'Tanggal', 'No Register', 'No Hutang', 'Pemberi Pinjaman', 'Sumber Uang', 'Pembayaran', 'Pc']
        totals = [('Grand Total', 'text', 6), (sum((row.nominal for row in rows), ZERO), 'number', 1), ('', 'text', 1)]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response('rekap-pembayaran-hutang.xls', 'Rekap Pembayaran Hutang', request.tenant, period, headers, export_rows, totals)
        return legacy_report_pdf_response(
            'rekap-pembayaran-hutang.pdf',
            'Rekap Pembayaran Hutang',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 25, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 25, 'w': 60, 'max': 8, 'size': 8},
                {'label': 'No Register', 'x': 85, 'w': 125, 'max': 25, 'size': 8},
                {'label': 'No Hutang', 'x': 210, 'w': 125, 'max': 25, 'size': 8},
                {'label': 'Pemberi Pinjaman', 'x': 335, 'w': 140, 'max': 25, 'size': 8},
                {'label': 'Sumber Uang', 'x': 475, 'w': 120, 'max': 20, 'size': 8},
                {'label': 'Pembayaran', 'x': 595, 'w': 85, 'max': 14, 'size': 8},
                {'label': 'Pc', 'x': 680, 'w': 50, 'max': 10, 'size': 8},
            ],
            [row[:8] for row in export_rows],
            [(0, 595, 'Grand Total', 'text', 6), (595, 85, sum((row.nominal for row in rows), ZERO), 'number', 1)],
            landscape=True,
        )
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    total_nominal = sum((row.nominal for row in rows), ZERO)
    return render(
        request,
        'reports/rekap_pembayaran_hutang.html',
        {
            'title': 'Rekap Pembayaran Hutang',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_nominal': total_nominal,
            'export_excel_pdf': True,
            **filters,
        },
    )


@login_required
def saldo_hutang(request):
    require_tenant(request)
    filters = report_filters(request)
    end_date = filters['end_date'] or date.today()
    filters['end_date'] = end_date
    rows = services.saldo_hutang(request.tenant, end_date)
    total_nominal = sum((row['nominal'] for row in rows), ZERO)
    total_pelunasan = sum((row['pelunasan'] for row in rows), ZERO)
    total_saldo = sum((row['saldo'] for row in rows), ZERO)

    if request.GET.get('export') in {'excel', 'pdf'}:
        period = end_date.strftime('%d/%m/%Y')
        export_rows = [
            [
                (index, 'number'),
                (row['tanggal'].strftime('%d/%m/%y'), 'center'),
                (row['no_register'], 'text'),
                (row['pemberi_pinjaman'], 'text'),
                (row['alamat_pemberi_pinjaman'], 'text'),
                (row['nominal'], 'number'),
                (row['pelunasan'], 'number'),
                (row['saldo'], 'number'),
                (row['created_by'], 'text'),
            ]
            for index, row in enumerate(rows, start=1)
        ]
        if request.GET.get('export') == 'excel':
            return legacy_report_excel_response(
                'saldo-hutang.xls',
                'Rekap Saldo Hutang',
                request.tenant,
                period,
                ['No', 'Tanggal', 'No Register', 'Pemberi Pinjaman', 'Alamat', 'Nominal', 'Pelunasan', 'Saldo', 'Pc'],
                export_rows,
                [('Grand Total', 'text', 7), (total_saldo, 'number', 1), ('', 'text', 1)],
            )
        return legacy_report_pdf_response(
            'saldo-hutang.pdf',
            'Rekap Saldo Hutang',
            request.tenant,
            period,
            [
                {'label': 'No', 'x': 0, 'w': 25, 'max': 4, 'size': 8},
                {'label': 'Tanggal', 'x': 25, 'w': 60, 'max': 8, 'size': 8},
                {'label': 'No Register', 'x': 85, 'w': 130, 'max': 25, 'size': 8},
                {'label': 'Pemberi Pinjaman', 'x': 215, 'w': 140, 'max': 25, 'size': 8},
                {'label': 'Alamat', 'x': 355, 'w': 130, 'max': 25, 'size': 8},
                {'label': 'Nominal', 'x': 485, 'w': 80, 'max': 14, 'size': 8},
                {'label': 'Pelunasan', 'x': 565, 'w': 80, 'max': 14, 'size': 8},
                {'label': 'Saldo', 'x': 645, 'w': 80, 'max': 14, 'size': 8},
                {'label': 'Pc', 'x': 725, 'w': 40, 'max': 8, 'size': 8},
            ],
            [
                [(row[0][0], row[0][1]), (row[1][0], row[1][1]), (row[2][0], row[2][1]), (row[3][0], row[3][1]), (row[4][0], row[4][1]), (row[5][0], row[5][1]), (row[6][0], row[6][1]), (row[7][0], row[7][1]), (row[8][0], row[8][1])]
                for row in export_rows
            ],
            [(0, 645, 'Grand Total', 'text', 8), (645, 80, total_saldo, 'number', 1), (725, 40, '', 'text', 1)],
            header_rgb=(0.90, 0.95, 0.98),
            landscape=True,
        )

    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'reports/saldo_hutang.html',
        {
            'title': 'Rekap Saldo Hutang',
            'rows': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'total_nominal': total_nominal,
            'total_pelunasan': total_pelunasan,
            'total_saldo': total_saldo,
            'export_excel_pdf': True,
            **filters,
        },
    )
