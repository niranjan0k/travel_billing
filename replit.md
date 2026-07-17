# Sona Travel Agency — Billing Portal

Flask-based billing and invoice management app for Sona Travel Agency.

## How to run

The workflow `Start application` installs dependencies and starts the server on port 5000:

```
pip install -r requirements.txt -q && python app.py
```

## Default login

- **Username:** `admin`
- **Password:** `admin123`

Override via environment variables: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, or `ADMIN_PASSWORD_HASH` (Werkzeug hash).

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (auto-provided by Replit) |
| `SESSION_SECRET` | Flask session secret key (set as Replit Secret) |
| `ADMIN_USERNAME` | Fallback admin username (default: `admin`) |
| `ADMIN_PASSWORD` | Fallback admin password (default: `admin123`) |
| `ADMIN_PASSWORD_HASH` | Werkzeug hash for admin password (optional, overrides `ADMIN_PASSWORD`) |

## Stack

- **Backend:** Python 3.12, Flask 3.1, SQLAlchemy 2.0
- **Database:** PostgreSQL (Replit built-in)
- **PDF generation:** ReportLab
- **Frontend:** Bootstrap 5.3, Bootstrap Icons

## Key files

| File | Purpose |
|---|---|
| `app.py` | Routes and application logic |
| `models.py` | SQLAlchemy models (Agency, Customer, Invoice, Passenger, User) |
| `pdf_generator.py` | Invoice PDF generation |
| `utils.py` | Invoice numbering, GST computation |
| `templates/base.html` | Shared layout — top header, expandable sidebar |
| `templates/users.html` | User management page |
| `templates/reports_*.html` | Report pages |
| `static/css/style.css` | Custom styles |

## User preferences

- Keep existing Flask + SQLAlchemy + ReportLab stack
- Do not restructure project layout
