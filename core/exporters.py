import base64
import os
import struct
import zlib
from decimal import Decimal
from html import escape
from io import BytesIO

from django.http import HttpResponse

def _tenant_logo_path(tenant):
    logo = getattr(tenant, 'logo', None)
    if not logo:
        return ''
    try:
        path = logo.path
    except Exception:
        return ''
    return path if os.path.exists(path) else ''

def _tenant_logo_data_uri(tenant):
    path = _tenant_logo_path(tenant)
    if not path:
        return ''
    mime = 'image/png' if path.lower().endswith('.png') else 'image/jpeg'
    with open(path, 'rb') as image_file:
        data = base64.b64encode(image_file.read()).decode('ascii')
    return f'data:{mime};base64,{data}'

def _png_rgb_data(path):
    with open(path, 'rb') as image_file:
        data = image_file.read()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        return None
    pos = 8
    width = height = color_type = None
    compressed = b''
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], 'big')
        chunk_type = data[pos + 4:pos + 8]
        chunk_data = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type, _, _, _ = struct.unpack('>IIBBBBB', chunk_data)
            if bit_depth != 8 or color_type not in (2, 6):
                return None
        elif chunk_type == b'IDAT':
            compressed += chunk_data
        elif chunk_type == b'IEND':
            break
    if not width or not height or not compressed:
        return None
    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(compressed)
    rows = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        row = bytearray(raw[offset:offset + stride])
        offset += stride
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = prev[i]
            up_left = prev[i - channels] if i >= channels else 0
            if filter_type == 1:
                row[i] = (row[i] + left) & 0xFF
            elif filter_type == 2:
                row[i] = (row[i] + up) & 0xFF
            elif filter_type == 3:
                row[i] = (row[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                row[i] = (row[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else up_left)) & 0xFF
        prev = row
        if channels == 3:
            rows.append(bytes(row))
        else:
            rgb = bytearray()
            for i in range(0, len(row), 4):
                alpha = row[i + 3] / 255
                rgb.extend(int(row[i + channel] * alpha + 255 * (1 - alpha)) for channel in range(3))
            rows.append(bytes(rgb))
    return width, height, b''.join(rows)

def _jpeg_size(path):
    with open(path, 'rb') as image_file:
        data = image_file.read()
    index = 2
    while index < len(data) - 9:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in (0xC0, 0xC1, 0xC2):
            height = int.from_bytes(data[index + 3:index + 5], 'big')
            width = int.from_bytes(data[index + 5:index + 7], 'big')
            return width, height, data
        length = int.from_bytes(data[index:index + 2], 'big')
        index += length
    return None, None, data

def _text(value):
    if value is None:
        return ''
    return str(value)

def excel_response(filename, title, headers, rows, tenant=None):
    logo = _tenant_logo_data_uri(tenant)
    html = [
        '<html><head><meta charset="utf-8">',
        '<style>body{font-family:Arial,sans-serif} table{border-collapse:collapse} th{background:#e5e7eb;font-weight:bold} th,td{border:1px solid #94a3b8;padding:6px} .num{text-align:right}</style>',
        '</head><body>',
    ]
    if logo:
        html.append(f'<img src="{logo}" style="height:56px;max-width:120px">')
    html.extend([f'<h2>{escape(title)}</h2>', '<table><thead><tr>'])
    for header in headers:
        html.append(f'<th>{escape(_text(header))}</th>')
    html.append('</tr></thead><tbody>')
    for row in rows:
        html.append('<tr>')
        for value in row:
            css = ' class="num"' if isinstance(value, (int, float, Decimal)) else ''
            html.append(f'<td{css}>{escape(_text(value))}</td>')
        html.append('</tr>')
    html.append('</tbody></table></body></html>')
    response = HttpResponse(''.join(html), content_type='application/vnd.ms-excel; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _pdf_escape(value):
    return _text(value).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

def _pdf_stream(lines):
    return ('\n'.join(lines)).encode('latin-1', errors='replace')

def _pdf_object(number, body):
    if isinstance(body, bytes):
        return f'{number} 0 obj\n'.encode('latin-1') + body + b'\nendobj\n'
    return f'{number} 0 obj\n{body}\nendobj\n'.encode('latin-1', errors='replace')

def _pdf_logo_object(tenant, number):
    path = _tenant_logo_path(tenant)
    if not path:
        return None, None
    try:
        if path.lower().endswith('.png'):
            png_data = _png_rgb_data(path)
            if not png_data:
                return None, None
            width, height, data = png_data
            compressed = zlib.compress(data)
            body = (
                f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} '
                f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n'
            ).encode('latin-1') + compressed + b'\nendstream'
        else:
            width, height, data = _jpeg_size(path)
            if not width or not height:
                return None, None
            body = (
                f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} '
                f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(data)} >>\nstream\n'
            ).encode('latin-1') + data + b'\nendstream'
    except Exception:
        return None, None
    return _pdf_object(number, body), {'number': number, 'width': width, 'height': height}

def _pdf_draw_logo(meta, x, y, max_w=55, max_h=55):
    if not meta:
        return ''
    scale = min(max_w / meta['width'], max_h / meta['height'])
    width = meta['width'] * scale
    height = meta['height'] * scale
    return f'q {width:.2f} 0 0 {height:.2f} {x:.2f} {y:.2f} cm /Logo Do Q'

def pdf_response(filename, title, headers, rows, landscape=True, tenant=None):
    width, height = (842, 595) if landscape else (595, 842)
    margin = 28
    font_size = 8
    title_size = 14
    line_height = 16
    table_width = width - (margin * 2)
    col_width = table_width / max(len(headers), 1)
    rows_per_page = max(int((height - 115) / line_height), 1)
    chunks = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [[]]

    objects = []
    page_numbers = []
    content_numbers = []
    logo_object, logo_meta = _pdf_logo_object(tenant, 3)
    next_number = 4 if logo_object else 3

    for page_index, chunk in enumerate(chunks, start=1):
        page_no = next_number
        content_no = next_number + 1
        next_number += 2
        page_numbers.append(page_no)
        content_numbers.append(content_no)
        y = height - margin
        lines = [
            'BT',
            f'/F1 {title_size} Tf {margin} {y} Td ({_pdf_escape(title)}) Tj',
            'ET',
        ]
        logo_cmd = _pdf_draw_logo(logo_meta, margin, y - 60, max_w=50, max_h=50)
        if logo_cmd:
            lines.append(logo_cmd)
        y -= 26
        lines.extend(['BT', f'/F1 {font_size} Tf'])
        x = margin
        for header in headers:
            lines.append(f'1 0 0 1 {x + 2:.2f} {y:.2f} Tm ({_pdf_escape(_text(header)[:22])}) Tj')
            x += col_width
        lines.append('ET')
        y -= line_height
        for row in chunk:
            lines.extend(['BT', f'/F1 {font_size} Tf'])
            x = margin
            for value in row:
                value_text = _text(value).replace('\r', ' ').replace('\n', ' ')
                max_chars = max(int(col_width / 4.1), 6)
                if len(value_text) > max_chars:
                    value_text = value_text[:max_chars - 1] + '…'
                lines.append(f'1 0 0 1 {x + 2:.2f} {y:.2f} Tm ({_pdf_escape(value_text)}) Tj')
                x += col_width
            lines.append('ET')
            y -= line_height
        lines.extend(['BT', f'/F1 8 Tf {width - margin - 70} {margin / 2:.2f} Td (Halaman {page_index}) Tj', 'ET'])
        content = _pdf_stream(lines)
        objects.append((content_no, _pdf_object(content_no, f'<< /Length {len(content)} >>\nstream\n' + content.decode('latin-1') + '\nendstream')))
        xobjects = f'/XObject << /Logo {logo_meta["number"]} 0 R >> ' if logo_meta else ''
        objects.append((page_no, _pdf_object(page_no, f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 1 0 R >> {xobjects}>> /Contents {content_no} 0 R >>')))

    pages_kids = ' '.join(f'{page_no} 0 R' for page_no in page_numbers)
    base_objects = [
        (1, _pdf_object(1, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')),
        (2, _pdf_object(2, f'<< /Type /Pages /Kids [{pages_kids}] /Count {len(page_numbers)} >>')),
    ]
    if logo_object:
        base_objects.append((3, logo_object))
    catalog_number = next_number
    all_objects = base_objects + sorted(objects) + [(catalog_number, _pdf_object(catalog_number, '<< /Type /Catalog /Pages 2 0 R >>'))]
    output = BytesIO()
    output.write(b'%PDF-1.4\n')
    offsets = [0]
    for _, obj in sorted(all_objects):
        offsets.append(output.tell())
        output.write(obj)
    xref = output.tell()
    output.write(f'xref\n0 {catalog_number + 1}\n0000000000 65535 f \n'.encode('latin-1'))
    for offset in offsets[1:]:
        output.write(f'{offset:010d} 00000 n \n'.encode('latin-1'))
    output.write(f'trailer\n<< /Size {catalog_number + 1} /Root {catalog_number} 0 R >>\nstartxref\n{xref}\n%%EOF'.encode('latin-1'))
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _money(value):
    if value in (None, ''):
        return ''
    try:
        amount = Decimal(value)
    except Exception:
        return _text(value)
    formatted = f'{amount:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    return formatted[:-3] if formatted.endswith(',00') else formatted

def _date_id(value):
    return value.strftime('%d/%m/%Y') if hasattr(value, 'strftime') else _text(value)

def legacy_report_excel_response(filename, title, tenant, period, headers, rows, totals, extra_lines=None, header_color='#b6d2e9'):
    extra_lines = extra_lines or []
    col_count = len(headers)
    logo = _tenant_logo_data_uri(tenant)
    logo_html = f'<img src="{logo}" style="height:56px;max-width:65px">' if logo else ''
    html = [
        '<html><head><meta charset="utf-8">',
        '<style>',
        'body{font-family:Arial,sans-serif;font-size:12px;color:#000}',
        'table{border-collapse:collapse}',
        'td,th{border:1px solid #000;padding:4px;vertical-align:middle}',
        '.no-border td{border:0}',
        '.title{font-size:16px;font-weight:bold;text-align:center;border:0}',
        '.company{font-size:19px;font-weight:bold;border:0}',
        '.center{text-align:center}.right{text-align:right}.bold{font-weight:bold}',
        f'.head{{background:{header_color};font-weight:bold;text-align:center}}',
        '</style></head><body>',
        '<table class="no-border">',
        '<tr>',
        f'<td style="width:65px;border:0">{logo_html}</td>',
        f'<td class="company" colspan="{col_count - 2}">{escape(_text(tenant.name))}</td>',
        f'<td class="right" style="border:0">Date: {escape(_date_id(__import__("datetime").date.today()))}</td>',
        '</tr>',
        f'<tr><td style="border:0"></td><td style="border:0" colspan="{col_count - 1}">Office : {escape(_text(tenant.address))}, Kabupaten {escape(_text(tenant.city))}</td></tr>',
        f'<tr><td style="border:0"></td><td style="border:0" colspan="{col_count - 1}">{escape(_text(tenant.postal_code))}, {escape(_text(tenant.province))}</td></tr>',
        f'<tr><td class="title" colspan="{col_count}">{escape(title)}</td></tr>',
    ]
    for line in extra_lines:
        html.append(f'<tr><td class="center" style="border:0" colspan="{col_count}">{escape(line)}</td></tr>')
    html.extend([
        f'<tr><td class="center" style="border:0" colspan="{col_count}">Periode : {escape(period)}</td></tr>',
        '</table><br><table>',
        '<tr>',
    ])
    for header in headers:
        html.append(f'<th class="head">{escape(header)}</th>')
    html.append('</tr>')
    for row in rows:
        html.append('<tr>')
        for value, kind in row:
            css = 'right' if kind == 'number' else 'center' if kind == 'center' else ''
            display = _money(value) if kind == 'number' else _date_id(value) if kind == 'date' else _text(value)
            html.append(f'<td class="{css}">{escape(display)}</td>')
        html.append('</tr>')
    html.append('<tr>')
    for value, kind, span in totals:
        css = 'right bold' if kind == 'number' else 'right bold'
        display = _money(value) if kind == 'number' else _text(value)
        html.append(f'<td class="{css}" colspan="{span}">{escape(display)}</td>')
    html.extend([
        '</tr></table><br>',
        '<table class="no-border" style="width:556px">',
        f'<tr><td class="right" colspan="4">Kab. Sukoharjo, {escape(_date_id(__import__("datetime").date.today()))}</td></tr>',
        '<tr><td></td><td class="center">Mengetahui,</td><td></td><td class="center">Yang membuat</td></tr>',
        '<tr><td colspan="4" style="height:40px"></td></tr>',
        '<tr><td></td><td class="center" style="border-bottom:1px solid #000">-</td><td></td><td class="center" style="border-bottom:1px solid #000">LIA WAHYUNINGSIH</td></tr>',
        '<tr><td></td><td class="center bold">Manager Operasional</td><td></td><td class="center bold">Admin</td></tr>',
        '</table></body></html>',
    ])
    response = HttpResponse(''.join(html), content_type='application/vnd.ms-excel; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def legacy_report_pdf_response(filename, title, tenant, period, columns, rows, totals, extra_lines=None, header_rgb=(0.71, 0.82, 0.91), title_italic=False):
    extra_lines = extra_lines or []
    width, height = 595, 842
    margin_x = 20
    top = height - 20
    content_width = 556
    row_h = 20
    header_h = 40 if any('\n' in col['label'] for col in columns) else 20
    title_h = 186 if extra_lines else 149
    rows_per_page = max(int((height - title_h - header_h - 210) / row_h), 1)
    chunks = [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)] or [[]]
    objects = []
    page_numbers = []
    logo_object, logo_meta = _pdf_logo_object(tenant, 4)
    next_number = 5 if logo_object else 4

    def cmd_text(x, y, text, size=9, bold=False, center=False, right=False):
        font = '/F2' if bold else '/F1'
        safe = _pdf_escape(text)
        if center:
            x = x - (len(text) * size * 0.25)
        elif right:
            x = x - (len(text) * size * 0.5)
        return f'BT {font} {size} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({safe}) Tj ET'

    def rect(x, y, w, h, fill=False):
        return f'{x:.2f} {y:.2f} {w:.2f} {h:.2f} re ' + ('f' if fill else 'S')

    def wrap_label(label, width, size):
        lines = []
        max_chars = max(int(width / (size * 0.55)), 1)
        for part in label.split('\n'):
            current = ''
            for word in part.split():
                candidate = f'{current} {word}'.strip()
                if len(candidate) <= max_chars:
                    current = candidate
                    continue
                if current:
                    lines.append(current)
                current = word
            if current:
                lines.append(current)
        return lines or ['']

    for page_index, chunk in enumerate(chunks, start=1):
        page_no = next_number
        content_no = next_number + 1
        next_number += 2
        page_numbers.append(page_no)
        lines = []
        y = top
        if page_index == 1:
            logo_cmd = _pdf_draw_logo(logo_meta, margin_x, y - 68, max_w=55, max_h=55)
            if logo_cmd:
                lines.append(logo_cmd)
            lines.append(cmd_text(margin_x + 420, y - 12, 'Date:', 9, right=True))
            lines.append(cmd_text(margin_x + 554, y - 12, _date_id(__import__('datetime').date.today()), 9, right=True))
            lines.append(cmd_text(margin_x + 67, y - 18, _text(tenant.name), 19, bold=True))
            lines.append(cmd_text(margin_x + 67, y - 33, f'Office : {_text(tenant.address)}, Kabupaten {_text(tenant.city)}', 9))
            lines.append(cmd_text(margin_x + 67, y - 48, f'{_text(tenant.postal_code)}, {_text(tenant.province)}', 9))
            lines.append(f'{margin_x} {y - 80:.2f} m {margin_x + content_width} {y - 80:.2f} l S')
            lines.append(cmd_text(margin_x + content_width / 2, y - 108, title, 16, bold=True, center=True))
            line_y = y - 130
            for line in extra_lines:
                lines.append(cmd_text(margin_x + content_width / 2, line_y, line, 9, center=True))
                line_y -= 15
            lines.append(cmd_text(margin_x + content_width / 2, line_y, f'Periode : {period}', 9, center=True))
            y = top - title_h
        else:
            lines.append(cmd_text(margin_x + content_width / 2, y - 18, title, 12, bold=True, center=True))
            y -= 50
        lines.append(f'{header_rgb[0]} {header_rgb[1]} {header_rgb[2]} rg')
        for col in columns:
            lines.append(rect(margin_x + col['x'], y - header_h, col['w'], header_h, fill=True))
        lines.append('0 0 0 RG 0 0 0 rg')
        for col in columns:
            lines.append(rect(margin_x + col['x'], y - header_h, col['w'], header_h))
            label_lines = wrap_label(col['label'], col['w'], col.get('header_size', 9))
            base_y = y - 14 if len(label_lines) == 1 else y - 12
            for idx, label in enumerate(label_lines):
                lines.append(cmd_text(margin_x + col['x'] + col['w'] / 2, base_y - (idx * 10), label, col.get('header_size', 9), bold=True, center=True))
        y -= header_h
        for row_index, row in enumerate(chunk, start=1 + (page_index - 1) * rows_per_page):
            for col, (value, kind) in zip(columns, row):
                lines.append(rect(margin_x + col['x'], y - row_h, col['w'], row_h))
                display = _money(value) if kind == 'number' else _date_id(value) if kind == 'date' else _text(value)
                display = display.replace('\n', ' ')
                if len(display) > col.get('max', 28):
                    display = display[:col.get('max', 28) - 1] + '.'
                text_x = margin_x + col['x'] + col['w'] - 3 if kind == 'number' else margin_x + col['x'] + 3
                lines.append(cmd_text(text_x, y - 14, display, col.get('size', 9), right=(kind == 'number')))
            y -= row_h
        if page_index == len(chunks):
            for x, w, value, kind, span_label in totals:
                lines.append(rect(margin_x + x, y - row_h, w, row_h))
                display = _money(value) if kind == 'number' else _text(value)
                lines.append(cmd_text(margin_x + x + w - 3, y - 14, display, 9, bold=True, right=True))
            y -= 58
            lines.append(cmd_text(margin_x + content_width, y, f'Kab. Sukoharjo, {_date_id(__import__("datetime").date.today())}', 9, right=True))
            y -= 22
            lines.append(cmd_text(margin_x + 250, y, 'Mengetahui,', 9, center=True))
            lines.append(cmd_text(margin_x + 476, y, 'Yang membuat', 9, center=True))
            y -= 60
            lines.append(cmd_text(margin_x + 250, y, '-', 9, center=True))
            lines.append(f'{margin_x + 200} {y - 3:.2f} m {margin_x + 300} {y - 3:.2f} l S')
            lines.append(cmd_text(margin_x + 476, y, 'LIA WAHYUNINGSIH', 9, center=True))
            lines.append(f'{margin_x + 426} {y - 3:.2f} m {margin_x + 526} {y - 3:.2f} l S')
            y -= 20
            lines.append(cmd_text(margin_x + 250, y, 'Manager Operasional', 9, bold=True, center=True))
            lines.append(cmd_text(margin_x + 476, y, 'Admin', 9, bold=True, center=True))
        content = _pdf_stream(lines)
        objects.append((content_no, _pdf_object(content_no, f'<< /Length {len(content)} >>\nstream\n' + content.decode('latin-1') + '\nendstream')))
        xobjects = f'/XObject << /Logo {logo_meta["number"]} 0 R >> ' if logo_meta else ''
        objects.append((page_no, _pdf_object(page_no, f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Resources << /Font << /F1 1 0 R /F2 3 0 R >> {xobjects}>> /Contents {content_no} 0 R >>')))

    pages_kids = ' '.join(f'{page_no} 0 R' for page_no in page_numbers)
    catalog_number = next_number
    all_objects = [
        (1, _pdf_object(1, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')),
        (2, _pdf_object(2, f'<< /Type /Pages /Kids [{pages_kids}] /Count {len(page_numbers)} >>')),
        (3, _pdf_object(3, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')),
    ]
    if logo_object:
        all_objects.append((4, logo_object))
    all_objects = all_objects + sorted(objects) + [(catalog_number, _pdf_object(catalog_number, '<< /Type /Catalog /Pages 2 0 R >>'))]
    output = BytesIO()
    output.write(b'%PDF-1.4\n')
    offsets = [0]
    for _, obj in sorted(all_objects):
        offsets.append(output.tell())
        output.write(obj)
    xref = output.tell()
    output.write(f'xref\n0 {catalog_number + 1}\n0000000000 65535 f \n'.encode('latin-1'))
    for offset in offsets[1:]:
        output.write(f'{offset:010d} 00000 n \n'.encode('latin-1'))
    output.write(f'trailer\n<< /Size {catalog_number + 1} /Root {catalog_number} 0 R >>\nstartxref\n{xref}\n%%EOF'.encode('latin-1'))
    response = HttpResponse(output.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
