from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Agency(db.Model):
    __tablename__ = "agencies"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(20))
    mobile1 = db.Column(db.String(30))
    mobile2 = db.Column(db.String(30))
    gst_no = db.Column(db.String(50))
    msme_no = db.Column(db.String(100))
    bank_name = db.Column(db.String(200))
    account_no = db.Column(db.String(50))
    ifsc = db.Column(db.String(30))
    branch = db.Column(db.String(200))
    logo_path = db.Column(db.String(300))
    stamp_path = db.Column(db.String(300))
    upi_id = db.Column(db.String(100))
    is_default = db.Column(db.Boolean, default=False)


class Customer(db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500))
    gst_no = db.Column(db.String(50))
    state = db.Column(db.String(100))
    state_code = db.Column(db.String(10))
    contact_person = db.Column(db.String(100))
    mobile = db.Column(db.String(30))
    email = db.Column(db.String(120))
    invoices = db.relationship("Invoice", backref="customer", lazy=True)


class Invoice(db.Model):
    __tablename__ = "invoices"
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(60), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    order_number = db.Column(db.String(60))
    order_date = db.Column(db.Date)
    journey_date = db.Column(db.Date)
    pnr_no = db.Column(db.String(30))
    travel_from = db.Column(db.String(100))
    travel_to = db.Column(db.String(100))
    train_number = db.Column(db.String(30))
    travel_class = db.Column(db.String(50))
    travel_type = db.Column(db.String(20), default="TATKAL")  # TATKAL / NORMAL
    description = db.Column(db.String(500))

    ticket_fare = db.Column(db.Float, default=0)
    service_charge = db.Column(db.Float, default=0)
    sgst_amount = db.Column(db.Float, default=0)
    cgst_amount = db.Column(db.Float, default=0)
    igst_amount = db.Column(db.Float, default=0)
    round_off = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)

    agency_id = db.Column(db.Integer, db.ForeignKey("agencies.id"))
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    agency = db.relationship("Agency", foreign_keys=[agency_id])

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    passengers = db.relationship(
        "Passenger", backref="invoice", cascade="all,delete-orphan", lazy=True
    )


class Passenger(db.Model):
    __tablename__ = "passengers"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    sequence = db.Column(db.Integer, default=0)
