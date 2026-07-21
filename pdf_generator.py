import io
import os
from decimal import Decimal, ROUND_HALF_UP

import qrcode
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from PIL import Image
from utils import rupees_in_words

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
IMG_DIR = os.path.join(BASE_DIR, "static", "img")

PAGE_W, PAGE_H = 595.91998, 842.88
PAGE_SIZE = (PAGE_W, PAGE_H)
BLACK = colors.black
GRID = colors.HexColor("#dddddd")
BORDER = colors.HexColor("#303030")
GREY_BAR = colors.HexColor("#808080")
RED_CINNABAR = colors.HexColor("#c7241d")
TEXT_LIFT = 2.1


def _register_fonts():
    fonts = {
        "Arial": r"C:\Windows\Fonts\arial.ttf",
        "Arial-Bold": r"C:\Windows\Fonts\arialbd.ttf",
    }
    for name, filename in fonts.items():
        if name not in pdfmetrics.getRegisteredFontNames() and os.path.exists(filename):
            pdfmetrics.registerFont(TTFont(name, filename))


_register_fonts()
FONT = "Arial" if "Arial" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
FONT_BOLD = "Arial-Bold" if "Arial-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"


def _y(top):
    return PAGE_H - top


def _rect(c, x0, top, x1, bottom, stroke=BORDER, fill=None, width=0.75):
    c.saveState()
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(width)
    if fill:
        c.setFillColor(fill)
    c.rect(x0, _y(bottom), x1 - x0, bottom - top, stroke=1 if stroke else 0, fill=1 if fill else 0)
    c.restoreState()


def _line(c, x0, top, x1, stroke=BORDER, width=0.75):
    c.saveState()
    c.setStrokeColor(stroke)
    c.setLineWidth(width)
    c.line(x0, _y(top), x1, _y(top))
    c.restoreState()


def _vline(c, x, top, bottom, stroke=GRID, width=0.75):
    c.saveState()
    c.setStrokeColor(stroke)
    c.setLineWidth(width)
    c.line(x, _y(top), x, _y(bottom))
    c.restoreState()


def _text(c, text, x, top, size=9, bold=False, align="left", color=BLACK):
    font = FONT_BOLD if bold else FONT
    c.saveState()
    c.setFillColor(color)
    c.setFont(font, size)
    y = _y(top + size - TEXT_LIFT)
    value = "" if text is None else str(text)
    if align == "center":
        c.drawCentredString(x, y, value)
    elif align == "right":
        c.drawRightString(x, y, value)
    else:
        c.drawString(x, y, value)
    c.restoreState()


def _para(text, size=9, bold=False, align="left", leading=None, color=BLACK):
    return Paragraph(
        str(text or "").replace("\n", "<br/>") or "",
        ParagraphStyle(
            "invoice-text",
            fontName=FONT_BOLD if bold else FONT,
            fontSize=size,
            leading=leading or size + 3,
            textColor=color,
            alignment={"left": 0, "center": 1, "right": 2}[align],
            spaceAfter=0,
            spaceBefore=0,
        ),
    )


def _draw_para(c, text, x, top, width, height, size=9, bold=False, align="left", leading=None, color=BLACK):
    p = _para(text, size=size, bold=bold, align=align, leading=leading, color=color)
    _, used_h = p.wrap(width, height)
    p.drawOn(c, x, _y(top) - used_h + TEXT_LIFT)


def _draw_image(c, path, x, top, width, height, preserve=True):
    if not path:
        _rect(c, x, top, x + width, top + height, stroke=GRID)
        return
    try:
        source = ImageReader(path) if hasattr(path, "read") else path
        if not hasattr(path, "read") and not os.path.exists(path):
            _rect(c, x, top, x + width, top + height, stroke=GRID)
            return
        c.drawImage(source, x, _y(top + height), width=width, height=height, preserveAspectRatio=preserve, anchor="c", mask="auto")
    except Exception:
        _rect(c, x, top, x + width, top + height, stroke=GRID)


def _money(value):
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == amount.to_integral():
        return str(int(amount))
    return f"{amount:.2f}"


def _date(value):
    return value.strftime("%d/%m/%Y") if value else ""


def _qr_image(upi_id, amount: float | str = None):
    static_qr = os.path.join(IMG_DIR, "upi-qr.jpg")
    # if os.path.exists(static_qr):
    #     return static_qr
    if not upi_id:
        return None

    # Build UPI payment URL with amount if provided
    upi_url = f"upi://pay?pa={upi_id}&pn=Agency"

    if amount is not None:
        # Convert to string and clean it
        amount_str = str(amount).strip()
        try:
            # Validate and format amount (UPI accepts up to 2 decimal places)
            amount_float = float(amount_str)
            amount_str = f"{amount_float:.2f}"
            upi_url += f"&am={amount_str}"
        except ValueError:
            print(f"Warning: Invalid amount '{amount}' - ignoring amount")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # H = highest correction, needed to survive logo overlay
        box_size=10,
        border=2,  # small quiet zone kept for scannability; 0 can break scanning
    )
    qr.add_data(upi_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Overlay logo if one exists
    logo_path = os.path.join(IMG_DIR, "firm-logo.jpg")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")

        qr_width, qr_height = img.size
        logo_size = qr_width // 5  # logo ~20% of QR width

        logo = logo.resize((logo_size, logo_size))

        # White padded background so logo stands out against QR modules
        pad = 10
        logo_bg = Image.new("RGB", (logo_size + pad * 2, logo_size + pad * 2), "white")
        logo_bg.paste(logo, (pad, pad), mask=logo if logo.mode == "RGBA" else None)

        pos = (
            (qr_width - logo_bg.size[0]) // 2,
            (qr_height - logo_bg.size[1]) // 2,
        )
        img.paste(logo_bg, pos)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def _split_address(address: str, max_len: int = 45) -> tuple[str, str, str]:
    """
    Splits address into up to 3 lines of max_len characters.
    Splits at word boundaries to avoid breaking words.
    """
    if not address:
        return "", "", ""
    
    address = address.strip()
    if len(address) <= max_len:
        return address, "", ""
    
    words = address.split()
    lines = ["", "", ""]
    current_line = 0
    current_len = 0
    
    for word in words:
        # Calculate length if we add this word (+1 for space)
        add_len = len(word)
        if lines[current_line]:  # not first word in line
            add_len += 1
        
        # If word doesn't fit in current line, move to next line
        if current_len + add_len > max_len and current_line < 2:
            current_line += 1
            current_len = 0
            add_len = len(word)  # reset for new line
        
        # Add word to current line
        if lines[current_line]:
            lines[current_line] += " " + word
        else:
            lines[current_line] = word
        
        current_len += add_len
    
    return lines[0], lines[1], lines[2]



def _agency_lines(agency):
    city = agency.city or ""
    pincode = agency.pincode or ""
    state = agency.state or ""
    city_line = f"{city} - {pincode} ({state})".strip(" -")
    address = [a for a in _split_address(agency.address) if a]
    return [
        agency.name or "",
        *address,
        city_line,
        f"Mobile No.: {agency.mobile1 or ''}{', ' + agency.mobile2 if agency.mobile2 else ''}",
        f"GST No.: {agency.gst_no or ''}",
    ]


def _customer_lines(customer):
    lines = [customer.company_name or ""]
    if customer.address:
        address = "".join([p.strip() for p in customer.address.replace("\r", "").split("\n") if p.strip()])
        address_list = [a for a in _split_address(address) if a]
        print("address_list", address_list)
        lines.extend([a for a in _split_address(address) if a])
    lines.extend([
        f"GST No.: {customer.gst_no or ''}",
        f"State: {customer.state or ''}",
        f"State Code: {customer.state_code or ''}",
    ])
    return lines


def _draw_multiline(c, lines, x, top, size=9.5, gap=13.4, bold_first=True, max_width=230):
    y = top
    for i, line in enumerate(lines):
        _draw_para(c, line, x, y, max_width, gap + 4, size=size, bold=(bold_first and i == 0), leading=size + 2)
        y += gap


def generate_invoice_pdf(invoice, agency, customer, passengers, output_path=None):
    buf = io.BytesIO() if output_path is None else None
    c = canvas.Canvas(output_path or buf, pagesize=PAGE_SIZE)
    c.setTitle("SONA TRAVEL AGENCY")

    logo_path = agency.logo_path if getattr(agency, "logo_path", None) else os.path.join(IMG_DIR, "firm-logo.jpg")
    authority_path = os.path.join(IMG_DIR, "authority-logo.jpg")
    stamp_path = agency.stamp_path if getattr(agency, "stamp_path", None) else os.path.join(IMG_DIR, "stamp.jpg")

    # Page frame and header.
    _rect(c, 37.1, 29.7, 558.9, 807.4, stroke=BORDER, width=1.47)
    _draw_image(c, logo_path, 48.8, 45.2, 73.5, 45.5, preserve=False)
    _draw_image(c, authority_path, 488.4, 45.2, 58.8, 54.4, preserve=False)
    _text(c, (agency.name or "").upper(), PAGE_W / 2, 41.4, size=23.2, bold=True, align="center")
    _text(c, "ISO 9001:2015 (QMS)", PAGE_W / 2, 74.0, size=14, bold=True, align="center", color=RED_CINNABAR)
    _text(c, f"{agency.msme_no or ''} & Authorized IRCTC Railway agent", PAGE_W / 2, 99.8, size=9.3, align="center")
    _rect(c, 37.8, 120.1, 558.2, 121.6, stroke=None, fill=GREY_BAR)

    # Top information panels.
    _rect(c, 38.2, 122.0, 296.9, 338.1, stroke=GRID)
    _rect(c, 45.9, 129.7, 289.2, 147.3, stroke=None, fill=BLACK)
    _text(c, "Invoice From:", 49.6, 131.5, size=10.2, bold=True, color=colors.white)
    _draw_multiline(c, _agency_lines(agency), 45.9, 152.5, size=8.8, gap=12.9, max_width=235)

    _rect(c, 45.9, 217.2, 289.2, 234.8, stroke=None, fill=BLACK)
    _text(c, "Invoice To:", 49.6, 219.0, size=10.2, bold=True, color=colors.white)
    _draw_multiline(c, _customer_lines(customer), 45.9, 243.0, max_width=238, size=8.8, gap=12.0)

    _rect(c, 297.6, 122.0, 557.1, 338.1, stroke=GRID)
    details = [
        ("Invoice Number", invoice.invoice_number or ""),
        ("Invoice Date", _date(invoice.invoice_date)),
        ("Order Number", invoice.order_number or ""),
        ("Order Date", _date(invoice.order_date)),
        ("Date of Journey", _date(invoice.journey_date)),
        ("PNR No", invoice.pnr_no or ""),
        ("Travel from:", invoice.travel_from or ""),
        ("Travel to:", invoice.travel_to or ""),
        ("Travel Type", f"Train - No. {invoice.train_number or ''}"),
        ("Type of Class", invoice.travel_class or ""),
        ("No of Passengers", str(len(passengers))),
    ]
    y = 129
    for label, value in details:
        _text(c, label, 305.4, y, size=8.8)
        _draw_para(c, value, 390.0, y - 0.5, 155, 12, size=8.8, leading=10.5)
        y += 14.0 if label != "Travel Type" else 13.9

    # Passenger and totals table, using original grid coordinates.
    cols = [49.6, 209.8, 262.0, 389.9, 475.1, 547.2]
    for i in range(len(cols) - 1):
        _rect(c, cols[i], 350.2, cols[i + 1], 387.7, stroke=GRID, fill=BLACK)
    _rect(c, 49.6, 387.7, 209.8, 489.8, stroke=GRID)
    for i in range(1, len(cols) - 1):
        _rect(c, cols[i], 387.7, cols[i + 1], 489.8, stroke=GRID)
    _rect(c, 49.6, 489.8, 389.9, 506.0, stroke=GRID)
    _rect(c, 389.9, 489.8, 475.1, 506.0, stroke=GRID, fill=BLACK)
    _rect(c, 475.1, 489.8, 547.2, 506.0, stroke=GRID, fill=BLACK)
    _rect(c, 49.6, 506.0, 389.9, 585.4, stroke=GRID)
    _rect(c, 389.9, 506.0, 475.1, 585.4, stroke=GRID)
    _rect(c, 475.1, 506.0, 547.2, 585.4, stroke=GRID)
    _rect(c, 49.6, 585.4, 389.9, 601.6, stroke=GRID)
    _rect(c, 389.9, 585.4, 475.1, 601.6, stroke=GRID, fill=BLACK)
    _rect(c, 475.1, 585.4, 547.2, 601.6, stroke=GRID, fill=BLACK)
    _rect(c, 49.6, 601.6, 209.8, 617.7, stroke=GRID)
    _rect(c, 209.8, 601.6, 547.2, 617.7, stroke=GRID)

    headers = ["Passenger name", "Fare", "Service Charges", "Total Service\nCharge", "Taxable\nAmount"]
    for i, header in enumerate(headers):
        align = "center" if i >= 3 else "left"
        _draw_para(c, header, cols[i] + 4, 356.9 if i >= 3 else 369.4, cols[i + 1] - cols[i] - 8, 24, size=8.8, bold=True, align=align, leading=11, color=colors.white)

    fare = invoice.ticket_fare or 0
    service = invoice.service_charge or 0
    taxable = service
    pax_text = "\n".join(getattr(p, "name", "") for p in passengers if getattr(p, "name", "")) or "-"
    _draw_para(c, pax_text, 54.0, 390.7, 145, 92, size=9, leading=13)
    per_passenger_service = service / len(passengers) if passengers else service
    for x, value in [(213.8, fare), (266.0, per_passenger_service), (393.9, service), (479.3, taxable)]:
        _text(c, _money(value), x, 390.0, size=9)

    _text(c, "HSN / SAC CODE : 996429    ( GST @18 )", 53.3, 492.2, size=8.8)
    _text(c, "Ticket Fare", 393.7, 492.2, size=8.8, color=colors.white)
    _text(c, _money(fare), 479.3, 492.2, size=8.8, color=colors.white)

    description = invoice.description or ""
    if not description:
        description = f"{invoice.travel_type or ''} TICKET BOOKED FROM {invoice.travel_from or ''} TO {invoice.travel_to or ''} IN {invoice.travel_class or ''} CLASS"
    _draw_para(c, description.upper(), 53.3, 508.3, 325, 72, size=8.8, leading=13)

    _text(c, "Net Service", 393.7, 508.3, size=8.8)
    _text(c, _money(service), 479.3, 508.3, size=8.8)
    _text(c, "Amount", 393.7, 521.6, size=8.8)
    for label, value, row_top in [
        ("SGST @ 9%", invoice.sgst_amount or 0, 534.9),
        ("CGST @ 9%", invoice.cgst_amount or 0, 548.2),
        ("IGST @ 18%", invoice.igst_amount or 0, 561.5),
        ("Round off Amount", invoice.round_off or 0, 574.8),
    ]:
        _text(c, label, 393.7, row_top, size=8.8)
        if "Round" in label:
            shown = f"{float(value):.2f}"
        else:
            shown = "-" if not value else _money(value)
        _text(c, shown, 479.3, row_top, size=8.8)

    _text(c, "Total Net Amount", 393.7, 587.7, size=8.8, bold=True, color=colors.white)
    _text(c, _money(invoice.total_amount or 0), 479.3, 587.7, size=8.8, bold=True, color=colors.white)
    _text(c, "Rupees in Words", 53.3, 603.9, size=8.8, bold=True)
    words = rupees_in_words(invoice.total_amount or 0).replace(",", "").replace(" And ", " and ")
    _draw_para(c, words, 209.8, 603.9, 330, 14, size=8.8, leading=10)

    # Footer bank, QR and signature panel.
    _rect(c, 49.2, 633.5, 238.3, 764.4, stroke=GRID)
    _rect(c, 56.9, 641.3, 226.7, 664.0, stroke=GRID, fill=BLACK)
    _text(c, "Bank Details", 62.1, 646.0, size=10.2, bold=True, color=colors.white)
    bank_lines = [
        agency.name or "",
        agency.bank_name or "",
        f"A/c No. {agency.account_no or ''}",
        f"IFSC Code : {agency.ifsc or ''}",
        f"Branch : {agency.branch or ''}",
    ]
    _draw_multiline(c, bank_lines, 62.1, 669.4, size=10.5, gap=14.0, bold_first=False, max_width=165)
    _rect(c, 238.2, 633.5, 388.3, 764.4, stroke=GRID)
    _draw_image(c, _qr_image(agency.upi_id, invoice.total_amount or 0), 226.7, 641.3, 172, 115.3)

    _rect(c, 388.4, 633.5, 546.8, 764.3, stroke=GRID)
    _draw_image(c, stamp_path, 409.9, 643.9, 118, 75, preserve=False)
    _text(c, "Authorized Signatory", 471.5, 729.0, size=9.8, bold=True, align="center")
    _text(c, f"For {agency.name or ''}", 471.5, 742.4, size=9.8, bold=True, align="center")

    _rect(c, 37.8, 775.8, 558.2, 777.2, stroke=None, fill=BLACK)
    _text(c, "Subject to Ranchi Juridictions", PAGE_W / 2, 786.2, size=10, bold=True, align="center")

    c.showPage()
    c.save()
    if buf is not None:
        buf.seek(0)
        return buf.getvalue()
    return None
