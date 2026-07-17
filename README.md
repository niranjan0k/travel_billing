# Travel Billing (Sona Travel Agency)

Local Flask desktop billing app that generates PDF invoices matching the
Sona Travel Agency format.

## Setup

```bash
cd travel_billing
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

On first run the PostgreSQL tables are created and one default
"SONA TRAVEL AGENCY" profile is seeded.

## Features

- Agency profiles (logo + stamp upload, default agency)
- Customer database with search
- Invoice creation with dynamic passenger rows
- Auto GST (SGST+CGST for same-state, IGST 18% otherwise)
- Auto invoice number: `STA\YY-YY\N` (fiscal year aware)
- "Rupees in Words" via num2words
- PDF invoice pixel-close to the Sona Travel layout (ReportLab)
- Invoice history with filters

## Notes

- Upload agency logo/stamp from the Agencies page for them to appear on PDFs.
- UPI QR is auto-generated from the agency `upi_id` field.

## Database (PostgreSQL)

Set `DATABASE_URL` before running, or copy `.env.example`:

```
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/travel_billing"
createdb travel_billing   # once
pip install -r requirements.txt
python app.py
```

Tables are auto-created on first run. The UPI QR code in the invoice footer is
generated on the fly from the agency's `upi_id` (encodes `upi://pay?pa=<upi_id>&pn=<agency>`).
## Login

The admin portal is protected by a login page. By default, local credentials are:

```
Username: admin
Password: admin123
```

Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in your environment to change them. After logout, dashboard and admin pages redirect back to `/login` until you sign in again.

