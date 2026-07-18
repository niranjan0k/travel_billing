import os
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    abort, Response, session,
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from sqlalchemy import or_

from models import db, Agency, Customer, Invoice, Passenger, User
from utils import next_invoice_number, compute_totals
from pdf_generator import generate_invoice_pdf, BASE_DIR
from dotenv import load_dotenv

load_dotenv()

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# PostgreSQL connection. Configure via DATABASE_URL env var.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Please configure it before starting the app."
    )
# SQLAlchemy expects the "postgresql://" or "postgresql+psycopg2://" scheme.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", os.environ.get("SECRET_KEY", "change-me-in-prod"))
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["ADMIN_USERNAME"] = os.environ.get("ADMIN_USERNAME", "admin")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin123")
app.config["ADMIN_PASSWORD_HASH"] = os.environ.get("ADMIN_PASSWORD_HASH", "")

# create a default username and password for admin 



db.init_app(app)


ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_IMG


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_safe_next(target):
    return target and target.startswith("/") and not target.startswith("//")


def _valid_login(username, password):
    # Check DB users first
    user = User.query.filter_by(username=username, is_active=True).first()
    if user:
        return user.check_password(password)

    # Fall back to env-var admin credentials
    expected_username = app.config["ADMIN_USERNAME"]
    if username != expected_username:
        return False
    password_hash = app.config["ADMIN_PASSWORD_HASH"]
    if password_hash:
        return check_password_hash(password_hash, password)
    return password == app.config["ADMIN_PASSWORD"]


@app.before_request
def require_login():
    public_endpoints = {"login", "static"}
    if request.endpoint in public_endpoints:
        return None
    if not session.get("admin_logged_in"):
        flash("Please login to access the admin portal.", "warning")
        return redirect(url_for("login", next=request.full_path.rstrip("?")))
    return None


@app.after_request
def prevent_admin_cache(response):
    if session.get("admin_logged_in") or request.endpoint not in {"login", "static"}:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def create_default_admin():
    admin = User.query.filter_by(username="admin").first()
    if not admin:
        admin = User(
            username="admin",
            display_name="Administrator",
            email="admin@example.com",
            role="admin",
            is_active=True,
        )
        admin.set_password("admin123")  # set a real password here
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created.")
    else:
        print("Admin user already exists, skipping creation.")



def seed_default_agency():
    if Agency.query.count() == 0:
        a = Agency(
            name="SONA TRAVEL AGENCY",
            address="Main Road, Near Railway Station",
            city="Ranchi",
            state="Jharkhand",
            pincode="834001",
            mobile1="9876543210",
            mobile2="9123456780",
            gst_no="20ABCDE1234F1Z5",
            msme_no="MSME No. UDYAM-JH-20-0000259",
            bank_name="State Bank of India",
            account_no="1234567890",
            ifsc="SBIN0001234",
            branch="Ranchi Main",
            upi_id="sonatravel@sbi",
            is_default=True,
        )
        db.session.add(a)
        db.session.commit()


with app.app_context():
    db.create_all()
    create_default_admin()
    seed_default_agency()


# ---------------- AUTH ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = request.form.get("next") or url_for("dashboard")

        if _valid_login(username, password):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            flash("Login successful.", "success")
            return redirect(next_url if _is_safe_next(next_url) else url_for("dashboard"))

        flash("Invalid username or password.", "danger")

    next_url = request.args.get("next", url_for("dashboard"))
    return render_template("login.html", next_url=next_url if _is_safe_next(next_url) else url_for("dashboard"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------- DASHBOARD ----------------
@app.route("/")
def dashboard():
    total = Invoice.query.count()
    now = datetime.utcnow()
    month_start = date(now.year, now.month, 1)
    monthly = db.session.query(db.func.coalesce(db.func.sum(Invoice.total_amount), 0)) \
        .filter(Invoice.invoice_date >= month_start).scalar()
    recent = Invoice.query.order_by(Invoice.id.desc()).limit(10).all()
    customer_count = Customer.query.count()
    return render_template("dashboard.html",
                           total=total, monthly=monthly, recent=recent,
                           customer_count=customer_count)


# ---------------- AGENCIES ----------------
@app.route("/agencies")
def agencies():
    return render_template("agencies.html", agencies=Agency.query.all())


@app.route("/agencies/save", methods=["POST"])
def save_agency():
    f = request.form
    aid = f.get("id")
    a = Agency.query.get(int(aid)) if aid else Agency()
    for field in ["name", "address", "city", "state", "pincode", "mobile1",
                  "mobile2", "gst_no", "msme_no", "bank_name", "account_no",
                  "ifsc", "branch", "upi_id"]:
        setattr(a, field, f.get(field, "").strip())
    a.is_default = bool(f.get("is_default"))
    if a.is_default:
        Agency.query.update({Agency.is_default: False})
        a.is_default = True

    for file_field, attr in [("logo", "logo_path"), ("stamp", "stamp_path")]:
        file = request.files.get(file_field)
        if file and file.filename and _allowed(file.filename):
            fn = secure_filename(f"{file_field}_{int(datetime.utcnow().timestamp())}_{file.filename}")
            path = os.path.join(UPLOAD_DIR, fn)
            file.save(path)
            setattr(a, attr, fn)

    if not aid:
        db.session.add(a)
    db.session.commit()
    flash("Agency saved.", "success")
    return redirect(url_for("agencies"))


@app.route("/agencies/<int:aid>/delete", methods=["POST"])
def delete_agency(aid):
    a = Agency.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash("Agency deleted.", "success")
    return redirect(url_for("agencies"))


# ---------------- CUSTOMERS ----------------
@app.route("/customers")
def customers():
    q = request.args.get("q", "").strip()
    qry = Customer.query
    if q:
        like = f"%{q}%"
        qry = qry.filter(or_(
            Customer.company_name.ilike(like),
            Customer.gst_no.ilike(like),
            Customer.state.ilike(like),
        ))
    return render_template("customers.html",
                           customers=qry.order_by(Customer.company_name).all(),
                           q=q)


@app.route("/customers/save", methods=["POST"])
def save_customer():
    f = request.form
    cid = f.get("id")
    c = Customer.query.get(int(cid)) if cid else Customer()
    for field in ["company_name", "address", "gst_no", "state", "state_code",
                  "contact_person", "mobile", "email"]:
        setattr(c, field, f.get(field, "").strip())
    if not cid:
        db.session.add(c)
    db.session.commit()
    flash("Customer saved.", "success")
    return redirect(url_for("customers"))


@app.route("/customers/<int:cid>/delete", methods=["POST"])
def delete_customer(cid):
    c = Customer.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash("Customer deleted.", "success")
    return redirect(url_for("customers"))


# ---------------- INVOICES ----------------
@app.route("/invoices")
def invoices():
    q = request.args.get("q", "").strip()
    cid = request.args.get("customer_id", type=int)
    date_from = _parse_date(request.args.get("from"))
    date_to = _parse_date(request.args.get("to"))
    qry = Invoice.query
    if q:
        qry = qry.filter(Invoice.invoice_number.ilike(f"%{q}%"))
    if cid:
        qry = qry.filter(Invoice.customer_id == cid)
    if date_from:
        qry = qry.filter(Invoice.invoice_date >= date_from)
    if date_to:
        qry = qry.filter(Invoice.invoice_date <= date_to)
    rows = qry.order_by(Invoice.id.desc()).all()
    return render_template("invoice_list.html", invoices=rows,
                           customers=Customer.query.order_by(Customer.company_name).all(),
                           q=q, cid=cid,
                           date_from=request.args.get("from", ""),
                           date_to=request.args.get("to", ""))


@app.route("/invoice/new", methods=["GET"])
def new_invoice():
    existing = [n[0] for n in db.session.query(Invoice.invoice_number).all()]
    proposed = next_invoice_number(existing, date.today())
    return render_template("invoice_form.html",
                           invoice=None,
                           passengers=[],
                           proposed_number=proposed,
                           agencies=Agency.query.all(),
                           default_agency=Agency.query.filter_by(is_default=True).first(),
                           customers=Customer.query.order_by(Customer.company_name).all(),
                           today=date.today().isoformat())


@app.route("/invoice/<int:iid>/edit", methods=["GET"])
def edit_invoice(iid):
    inv = Invoice.query.get_or_404(iid)
    return render_template("invoice_form.html",
                           invoice=inv,
                           passengers=inv.passengers,
                           proposed_number=inv.invoice_number,
                           agencies=Agency.query.all(),
                           default_agency=inv.agency,
                           customers=Customer.query.order_by(Customer.company_name).all(),
                           today=date.today().isoformat())


@app.route("/invoice/save", methods=["POST"])
def save_invoice():
    f = request.form
    iid = f.get("id")
    inv = Invoice.query.get(int(iid)) if iid else Invoice()

    customer_id = f.get("customer_id")
    if customer_id:
        customer = Customer.query.get(int(customer_id))
    else:
        customer = Customer(
            company_name=f.get("cust_name", "").strip(),
            address=f.get("cust_address", "").strip(),
            gst_no=f.get("cust_gst", "").strip(),
            state=f.get("cust_state", "").strip(),
            state_code=f.get("cust_state_code", "").strip(),
        )
        db.session.add(customer)
        db.session.flush()

    agency = Agency.query.get(int(f.get("agency_id")))
    same_state = (agency.state or "").strip().lower() == (customer.state or "").strip().lower()

    ticket_fare = float(f.get("ticket_fare") or 0)
    service_charge = float(f.get("service_charge") or 0)
    totals = compute_totals(ticket_fare, service_charge, same_state)

    inv.invoice_number = f.get("invoice_number", "").strip()
    inv.invoice_date = _parse_date(f.get("invoice_date")) or date.today()
    inv.order_number = f.get("order_number", "").strip()
    inv.order_date = _parse_date(f.get("order_date"))
    inv.journey_date = _parse_date(f.get("journey_date"))
    inv.pnr_no = f.get("pnr_no", "").strip()
    inv.travel_from = f.get("travel_from", "").strip()
    inv.travel_to = f.get("travel_to", "").strip()
    inv.train_number = f.get("train_number", "").strip()
    inv.travel_class = f.get("travel_class", "").strip()
    inv.travel_type = f.get("travel_type", "TATKAL").strip()
    inv.description = f.get("description", "").strip() or (
        f"{inv.travel_type} TICKET BOOKED FROM {inv.travel_from} TO {inv.travel_to} "
        f"IN {inv.travel_class} CLASS"
    ).upper()
    inv.ticket_fare = ticket_fare
    inv.service_charge = service_charge
    inv.sgst_amount = totals["sgst"]
    inv.cgst_amount = totals["cgst"]
    inv.igst_amount = totals["igst"]
    inv.round_off = totals["round_off"]
    inv.total_amount = totals["total"]
    inv.agency_id = agency.id
    inv.customer_id = customer.id

    if not iid:
        db.session.add(inv)
    db.session.flush()

    for p in list(inv.passengers):
        db.session.delete(p)
    names = request.form.getlist("passenger_name")
    for i, name in enumerate(names):
        name = (name or "").strip()
        if name:
            db.session.add(Passenger(invoice_id=inv.id, name=name, sequence=i))

    db.session.commit()
    flash("Invoice saved.", "success")

    if f.get("action") == "download":
        return redirect(url_for("invoice_pdf", iid=inv.id))
    return redirect(url_for("invoices"))


@app.route("/invoice/<int:iid>/delete", methods=["POST"])
def delete_invoice(iid):
    inv = Invoice.query.get_or_404(iid)
    db.session.delete(inv)
    db.session.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices"))


@app.route("/invoice/<int:iid>/pdf")
def invoice_pdf(iid):
    inv = Invoice.query.get_or_404(iid)
    agency = Agency.query.get(inv.agency_id)
    customer = Customer.query.get(inv.customer_id)
    if not agency or not customer:
        abort(400, "Missing agency or customer")
    pdf_bytes = generate_invoice_pdf(inv, agency, customer, inv.passengers)
    safe_cust = "".join(ch for ch in customer.company_name if ch.isalnum() or ch in "_-") or "customer"
    safe_num = inv.invoice_number.replace("\\", "-").replace("/", "-")
    filename = f"{safe_num}_{safe_cust}.pdf"
    return Response(
        pdf_bytes, mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@app.route("/invoice/<int:iid>/download")
def invoice_download(iid):
    inv = Invoice.query.get_or_404(iid)
    agency = Agency.query.get(inv.agency_id)
    customer = Customer.query.get(inv.customer_id)
    pdf_bytes = generate_invoice_pdf(inv, agency, customer, inv.passengers)
    safe_cust = "".join(ch for ch in customer.company_name if ch.isalnum() or ch in "_-") or "customer"
    safe_num = inv.invoice_number.replace("\\", "-").replace("/", "-")
    filename = f"{safe_num}_{safe_cust}.pdf"
    return Response(
        pdf_bytes, mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------- USER MANAGEMENT ----------------
@app.route("/users")
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template("users.html", users=all_users)


@app.route("/users/save", methods=["POST"])
def save_user():
    f = request.form
    uid = f.get("id")
    username = f.get("username", "").strip().lower()
    display_name = f.get("display_name", "").strip()
    email = f.get("email", "").strip()
    role = f.get("role", "staff")
    is_active = bool(f.get("is_active"))
    password = f.get("password", "")

    if uid:
        u = User.query.get_or_404(int(uid))
        # Don't allow changing the last active admin to inactive
        if u.role == "admin" and role != "admin":
            admin_count = User.query.filter_by(role="admin", is_active=True).count()
            if admin_count <= 1:
                flash("Cannot remove the last admin user.", "danger")
                return redirect(url_for("users"))
        u.username = username
        u.display_name = display_name
        u.email = email
        u.role = role
        u.is_active = is_active
        if password:
            u.set_password(password)
    else:
        if not password:
            flash("Password is required for a new user.", "danger")
            return redirect(url_for("users"))
        if User.query.filter_by(username=username).first():
            flash(f"Username '{username}' is already taken.", "danger")
            return redirect(url_for("users"))
        u = User(username=username, display_name=display_name,
                 email=email, role=role, is_active=is_active)
        u.set_password(password)
        db.session.add(u)

    db.session.commit()
    flash("User saved.", "success")
    return redirect(url_for("users"))


@app.route("/users/<int:uid>/delete", methods=["POST"])
def delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.role == "admin":
        admin_count = User.query.filter_by(role="admin", is_active=True).count()
        if admin_count <= 1:
            flash("Cannot delete the last admin user.", "danger")
            return redirect(url_for("users"))
    db.session.delete(u)
    db.session.commit()
    flash("User deleted.", "success")
    return redirect(url_for("users"))


# ---------------- REPORTS ----------------
@app.route("/reports")
@app.route("/reports/summary")
def reports_summary():
    # Overall totals
    total_invoices = Invoice.query.count()
    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
    ).scalar()
    total_customers = Customer.query.count()

    # This month
    now = datetime.utcnow()
    month_start = date(now.year, now.month, 1)
    month_invoices = Invoice.query.filter(Invoice.invoice_date >= month_start).count()
    month_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Invoice.total_amount), 0)
    ).filter(Invoice.invoice_date >= month_start).scalar()

    # Top 10 recent invoices
    recent = Invoice.query.order_by(Invoice.id.desc()).limit(10).all()

    return render_template("reports_summary.html",
                           total_invoices=total_invoices,
                           total_revenue=total_revenue,
                           total_customers=total_customers,
                           month_invoices=month_invoices,
                           month_revenue=month_revenue,
                           recent=recent)


@app.route("/reports/monthly")
def reports_monthly():
    # Group by year-month
    rows = db.session.execute(db.text("""
        SELECT
            TO_CHAR(invoice_date, 'YYYY-MM') AS ym,
            TO_CHAR(invoice_date, 'Mon YYYY') AS label,
            COUNT(*) AS cnt,
            COALESCE(SUM(total_amount), 0) AS revenue
        FROM invoices
        GROUP BY ym, label
        ORDER BY ym DESC
        LIMIT 24
    """)).fetchall()
    return render_template("reports_monthly.html", rows=rows)


@app.route("/reports/customers")
def reports_customers():
    rows = db.session.execute(db.text("""
        SELECT
            c.id,
            c.company_name,
            c.state,
            COUNT(i.id) AS invoice_count,
            COALESCE(SUM(i.total_amount), 0) AS total_spent
        FROM customers c
        LEFT JOIN invoices i ON i.customer_id = c.id
        GROUP BY c.id, c.company_name, c.state
        ORDER BY total_spent DESC
    """)).fetchall()
    return render_template("reports_customers.html", rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
