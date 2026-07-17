from datetime import date
from num2words import num2words


def fiscal_year_label(d: date) -> str:
    """Indian fiscal year label, e.g. 2026-04-05 -> '26-27'."""
    y = d.year
    if d.month < 4:
        start = y - 1
    else:
        start = y
    return f"{str(start)[-2:]}-{str(start + 1)[-2:]}"


def next_invoice_number(existing_numbers, today: date, prefix: str = "STA") -> str:
    """Generate STA\\YY-YY\\N where N is 1 + max seq in current fiscal year."""
    label = fiscal_year_label(today)
    token = f"{prefix}\\{label}\\"
    max_n = 0
    for num in existing_numbers:
        if num and num.startswith(token):
            tail = num[len(token):]
            try:
                n = int(tail)
                if n > max_n:
                    max_n = n
            except ValueError:
                pass
    return f"{token}{max_n + 1}"


def rupees_in_words(amount: float) -> str:
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    words = num2words(rupees, lang="en_IN").title()
    text = f"{words} Rupees"
    if paise:
        text += f" and {num2words(paise, lang='en_IN').title()} Paise"
    return text + " only"


def compute_totals(ticket_fare, service_charge, same_state):
    ticket_fare = float(ticket_fare or 0)
    service_charge = float(service_charge or 0)
    if same_state:
        sgst = round(service_charge * 0.09, 2)
        cgst = round(service_charge * 0.09, 2)
        igst = 0.0
    else:
        sgst = 0.0
        cgst = 0.0
        igst = round(service_charge * 0.18, 2)
    raw_total = ticket_fare + service_charge + sgst + cgst + igst
    rounded = round(raw_total)
    round_off = round(rounded - raw_total, 2)
    return {
        "sgst": sgst,
        "cgst": cgst,
        "igst": igst,
        "round_off": round_off,
        "total": float(rounded),
    }
