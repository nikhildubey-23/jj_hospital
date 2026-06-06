import os
import csv
import io
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, Response, jsonify
)
from flask_cors import CORS
from config import Config
from models import db, Admin, Booking, Staff, Attendance, Referral, LabTest

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
db.init_app(app)

# ─── Helpers ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please login first', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('admin_role') not in allowed_roles:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('admin_dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

def send_booking_email(booking):
    smtp_server = app.config.get('MAIL_USERNAME') or session.get('mail_username', '')
    smtp_password = app.config.get('MAIL_PASSWORD') or session.get('mail_password', '')
    recipient = app.config.get('MAIL_RECIPIENT') or session.get('mail_recipient', '')

    if not smtp_server or not smtp_password or not recipient:
        return False

    subject = f"New Booking - {booking.patient_name}"
    body = f"""
    New Appointment Booking
    ====================
    Patient Name: {booking.patient_name}
    Phone: {booking.phone}
    Email: {booking.email or 'N/A'}
    Address: {booking.address or 'N/A'}
    Department: {booking.department or 'N/A'}
    Doctor: {booking.doctor or 'N/A'}
    Date: {booking.booking_date or 'N/A'}
    Message: {booking.message or 'N/A'}
    Booking Time: {booking.created_at}
    """

    msg = MIMEMultipart()
    msg['From'] = smtp_server
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls(context=context)
            server.login(smtp_server, smtp_password)
            server.sendmail(smtp_server, recipient, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

# ─── Public Routes ──────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/booking')
def booking_page():
    return render_template('booking.html')

@app.route('/booking/submit', methods=['POST'])
def submit_booking():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    department = request.form.get('department')
    doctor = request.form.get('doctor')
    bdate = request.form.get('booking_date')
    message = request.form.get('message')

    if not name or not phone:
        flash('Name and phone number are required', 'danger')
        return redirect(url_for('booking_page'))

    try:
        bdate_parsed = datetime.strptime(bdate, '%Y-%m-%d').date() if bdate else None
    except:
        bdate_parsed = None

    booking = Booking(
        patient_name=name, phone=phone, email=email,
        address=address, department=department, doctor=doctor,
        booking_date=bdate_parsed, message=message
    )
    db.session.add(booking)
    db.session.commit()

    send_booking_email(booking)

    flash('Your appointment has been booked successfully! We will contact you soon.', 'success')
    return redirect(url_for('booking_page'))


@app.route('/api/booking', methods=['POST'])
def api_submit_booking():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()

    if not name or not phone:
        return jsonify({'error': 'Name and phone are required'}), 400

    bdate = data.get('booking_date')
    try:
        bdate_parsed = datetime.strptime(bdate, '%Y-%m-%d').date() if bdate else None
    except:
        bdate_parsed = None

    booking = Booking(
        patient_name=name, phone=phone, email=data.get('email'),
        address=data.get('address'), department=data.get('department'),
        doctor=data.get('doctor'), booking_date=bdate_parsed,
        message=data.get('message')
    )
    db.session.add(booking)
    db.session.commit()

    send_booking_email(booking)

    return jsonify({'message': 'Booking successful'}), 200

# ─── Admin Auth ─────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_role'] = admin.role
            flash('Welcome, ' + username + '!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('admin_login'))

# ─── Admin Dashboard ────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_dashboard():
    today = date.today()
    role = session.get('admin_role', 'main_admin')

    total_bookings = Booking.query.count()
    total_staff = Staff.query.count()
    total_referrals = Referral.query.count()
    today_bookings = Booking.query.filter(
        db.func.date(Booking.created_at) == today
    ).count()
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()

    total_lab_tests = LabTest.query.count()
    total_lab_amount = db.session.query(db.func.sum(LabTest.amount)).scalar() or 0.0
    today_lab_tests = LabTest.query.filter(
        db.func.date(LabTest.created_at) == today
    ).count()
    pending_lab_tests = LabTest.query.filter_by(status='Pending').count()
    recent_lab_tests = LabTest.query.order_by(LabTest.created_at.desc()).limit(5).all()

    lab_income = db.session.query(db.func.sum(Referral.charge)).filter(
        Referral.referral_type == 'Lab'
    ).scalar() or 0.0

    total_income = total_lab_amount + lab_income

    today_present = Attendance.query.filter(
        Attendance.date == today, Attendance.status == 'Present'
    ).count()
    today_absent = Attendance.query.filter(
        Attendance.date == today, Attendance.status == 'Absent'
    ).count()

    return render_template('admin/dashboard.html',
        total_bookings=total_bookings,
        total_staff=total_staff,
        total_referrals=total_referrals,
        today_bookings=today_bookings,
        recent_bookings=recent_bookings,
        role=role,
        lab_income=lab_income,
        total_income=total_income,
        total_lab_tests=total_lab_tests,
        total_lab_amount=total_lab_amount,
        today_lab_tests=today_lab_tests,
        pending_lab_tests=pending_lab_tests,
        recent_lab_tests=recent_lab_tests,
        today_present=today_present,
        today_absent=today_absent)

# ─── Bookings ───────────────────────────────────────────────────────────────

@app.route('/admin/bookings')
@login_required
@role_required('main_admin', 'lab')
def admin_bookings():
    search = request.args.get('search', '')
    query = Booking.query
    if search:
        query = query.filter(
            db.or_(
                Booking.patient_name.contains(search),
                Booking.phone.contains(search),
                Booking.email.contains(search)
            )
        )
    bookings = query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings, search=search)

@app.route('/admin/bookings/delete/<int:id>', methods=['POST'])
@login_required
def delete_booking(id):
    booking = Booking.query.get_or_404(id)
    db.session.delete(booking)
    db.session.commit()
    flash('Booking deleted successfully', 'success')
    return redirect(url_for('admin_bookings'))

@app.route('/admin/bookings/export')
@login_required
@role_required('main_admin', 'lab')
def export_bookings_csv():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Patient Name', 'Phone', 'Email', 'Address', 'Department', 'Doctor', 'Appointment Date', 'Message', 'Booking Time'])
    for b in bookings:
        writer.writerow([b.id, b.patient_name, b.phone, b.email, b.address,
                        b.department, b.doctor, b.booking_date, b.message, b.created_at])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=bookings.csv'})

# ─── Staff ──────────────────────────────────────────────────────────────────

@app.route('/admin/staff')
@login_required
@role_required('main_admin', 'hr')
def admin_staff():
    staff_list = Staff.query.order_by(Staff.name).all()
    return render_template('admin/staff.html', staff_list=staff_list)

@app.route('/admin/staff/add', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'hr')
def add_staff():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        position = request.form.get('position')
        department = request.form.get('department')
        jdate = request.form.get('joining_date')
        address = request.form.get('address')

        if not name:
            flash('Name is required', 'danger')
            return render_template('admin/staff_form.html', staff=None)

        try:
            jdate_parsed = datetime.strptime(jdate, '%Y-%m-%d').date() if jdate else None
        except:
            jdate_parsed = None

        staff = Staff(name=name, phone=phone, email=email, position=position,
                     department=department, joining_date=jdate_parsed, address=address)
        db.session.add(staff)
        db.session.commit()
        flash('Staff member added successfully', 'success')
        return redirect(url_for('admin_staff'))
    return render_template('admin/staff_form.html', staff=None)

@app.route('/admin/staff/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'hr')
def edit_staff(id):
    staff = Staff.query.get_or_404(id)
    if request.method == 'POST':
        staff.name = request.form.get('name')
        staff.phone = request.form.get('phone')
        staff.email = request.form.get('email')
        staff.position = request.form.get('position')
        staff.department = request.form.get('department')
        jdate = request.form.get('joining_date')
        try:
            staff.joining_date = datetime.strptime(jdate, '%Y-%m-%d').date() if jdate else None
        except:
            pass
        staff.address = request.form.get('address')
        db.session.commit()
        flash('Staff information updated successfully', 'success')
        return redirect(url_for('admin_staff'))
    return render_template('admin/staff_form.html', staff=staff)

@app.route('/admin/staff/delete/<int:id>', methods=['POST'])
@login_required
@role_required('main_admin', 'hr')
def delete_staff(id):
    staff = Staff.query.get_or_404(id)
    Attendance.query.filter_by(staff_id=id).delete()
    db.session.delete(staff)
    db.session.commit()
    flash('Staff member deleted successfully', 'success')
    return redirect(url_for('admin_staff'))

@app.route('/admin/staff/export')
@login_required
@role_required('main_admin', 'hr')
def export_staff_csv():
    staff_list = Staff.query.order_by(Staff.name).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Email', 'Position', 'Department', 'Joining Date', 'Address'])
    for s in staff_list:
        writer.writerow([s.id, s.name, s.phone, s.email, s.position, s.department, s.joining_date, s.address])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=staff.csv'})

# ─── Attendance ─────────────────────────────────────────────────────────────

@app.route('/admin/attendance')
@login_required
@role_required('main_admin', 'hr')
def admin_attendance():
    staff_list = Staff.query.order_by(Staff.name).all()
    filter_date = request.args.get('filter_date', date.today().isoformat())
    try:
        fdate = datetime.strptime(filter_date, '%Y-%m-%d').date()
    except:
        fdate = date.today()

    attendance_records = {}
    for s in staff_list:
        att = Attendance.query.filter_by(staff_id=s.id, date=fdate).first()
        attendance_records[s.id] = att.status if att else None

    return render_template('admin/attendance.html',
        staff_list=staff_list, attendance_records=attendance_records,
        filter_date=filter_date)

@app.route('/admin/attendance/mark', methods=['POST'])
@login_required
@role_required('main_admin', 'hr')
def mark_attendance():
    staff_id = request.form.get('staff_id')
    att_date = request.form.get('date')
    status = request.form.get('status')

    if not staff_id or not att_date or not status:
        flash('Please fill all fields', 'danger')
        return redirect(url_for('admin_attendance'))

    try:
        adate = datetime.strptime(att_date, '%Y-%m-%d').date()
    except:
        flash('Invalid date', 'danger')
        return redirect(url_for('admin_attendance'))

    existing = Attendance.query.filter_by(staff_id=staff_id, date=adate).first()
    if existing:
        existing.status = status
    else:
        att = Attendance(staff_id=staff_id, date=adate, status=status)
        db.session.add(att)

    db.session.commit()
    flash('Attendance marked successfully', 'success')
    return redirect(url_for('admin_attendance', filter_date=att_date))

@app.route('/admin/attendance/report')
@login_required
@role_required('main_admin', 'hr')
def attendance_report():
    staff_id = request.args.get('staff_id')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    query = Attendance.query

    staff_list = Staff.query.order_by(Staff.name).all()

    if staff_id and staff_id.isdigit():
        query = query.filter_by(staff_id=int(staff_id))
    if from_date:
        try:
            query = query.filter(Attendance.date >= datetime.strptime(from_date, '%Y-%m-%d').date())
        except:
            pass
    if to_date:
        try:
            query = query.filter(Attendance.date <= datetime.strptime(to_date, '%Y-%m-%d').date())
        except:
            pass

    records = query.order_by(Attendance.date.desc()).all()

    if 'export' in request.args:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Employee', 'Date', 'Status'])
        for r in records:
            writer.writerow([r.id, r.staff.name, r.date, r.status])
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition': 'attachment;filename=attendance_report.csv'})

    return render_template('admin/attendance_report.html',
        records=records, staff_list=staff_list,
        staff_id=staff_id, from_date=from_date, to_date=to_date)

# ─── Referrals ──────────────────────────────────────────────────────────────

REFERRAL_TYPES = ['MRI', 'CT Scan', 'Sonography', 'Lab', 'X-Ray']

@app.route('/admin/referrals')
@login_required
@role_required('main_admin', 'referral')
def admin_referrals():
    search = request.args.get('search', '')
    rtype = request.args.get('type', '')
    query = Referral.query
    if search:
        query = query.filter(
            db.or_(
                Referral.patient_name.contains(search),
                Referral.phone.contains(search),
                Referral.doctor_name.contains(search)
            )
        )
    if rtype:
        query = query.filter_by(referral_type=rtype)
    referrals = query.order_by(Referral.created_at.desc()).all()
    return render_template('admin/referrals.html',
        referrals=referrals, search=search, rtype=rtype, types=REFERRAL_TYPES)

@app.route('/admin/referrals/add', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'referral')
def add_referral():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        phone = request.form.get('phone')
        referral_type = request.form.get('referral_type')
        charge = request.form.get('charge', 0)
        doctor_name = request.form.get('doctor_name')
        rdate = request.form.get('referral_date')
        notes = request.form.get('notes')

        if not patient_name or not referral_type:
            flash('Patient name and referral type are required', 'danger')
            return render_template('admin/referral_form.html', referral=None, types=REFERRAL_TYPES)

        try:
            rdate_parsed = datetime.strptime(rdate, '%Y-%m-%d').date() if rdate else None
        except:
            rdate_parsed = None

        try:
            charge_val = float(charge) if charge else 0.0
        except:
            charge_val = 0.0

        referral = Referral(
            patient_name=patient_name, phone=phone,
            referral_type=referral_type, charge=charge_val,
            doctor_name=doctor_name, referral_date=rdate_parsed, notes=notes
        )
        db.session.add(referral)
        db.session.commit()
        flash('Referral record added successfully', 'success')
        return redirect(url_for('admin_referrals'))
    return render_template('admin/referral_form.html', referral=None, types=REFERRAL_TYPES)

@app.route('/admin/referrals/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'referral')
def edit_referral(id):
    referral = Referral.query.get_or_404(id)
    if request.method == 'POST':
        referral.patient_name = request.form.get('patient_name')
        referral.phone = request.form.get('phone')
        referral.referral_type = request.form.get('referral_type')
        charge = request.form.get('charge', 0)
        try:
            referral.charge = float(charge) if charge else 0.0
        except:
            referral.charge = 0.0
        referral.doctor_name = request.form.get('doctor_name')
        rdate = request.form.get('referral_date')
        try:
            referral.referral_date = datetime.strptime(rdate, '%Y-%m-%d').date() if rdate else None
        except:
            pass
        referral.notes = request.form.get('notes')
        db.session.commit()
        flash('Referral record updated successfully', 'success')
        return redirect(url_for('admin_referrals'))
    return render_template('admin/referral_form.html', referral=referral, types=REFERRAL_TYPES)

@app.route('/admin/referrals/delete/<int:id>', methods=['POST'])
@login_required
@role_required('main_admin', 'referral')
def delete_referral(id):
    referral = Referral.query.get_or_404(id)
    db.session.delete(referral)
    db.session.commit()
    flash('Referral record deleted successfully', 'success')
    return redirect(url_for('admin_referrals'))

@app.route('/admin/referrals/export')
@login_required
@role_required('main_admin', 'referral')
def export_referrals_csv():
    rtype = request.args.get('type', '')
    query = Referral.query
    if rtype:
        query = query.filter_by(referral_type=rtype)
    referrals = query.order_by(Referral.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Patient Name', 'Phone', 'Referral Type', 'Charge (₹)', 'Doctor Name', 'Date', 'Notes', 'Created At'])
    for r in referrals:
        writer.writerow([r.id, r.patient_name, r.phone, r.referral_type,
                        r.charge, r.doctor_name, r.referral_date, r.notes, r.created_at])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=referrals.csv'})

# ─── Lab Tests ──────────────────────────────────────────────────────────────

LAB_TEST_STATUSES = ['Pending', 'Completed', 'Cancelled']

@app.route('/admin/lab-tests')
@login_required
@role_required('main_admin', 'lab')
def admin_lab_tests():
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    query = LabTest.query
    if search:
        query = query.filter(
            db.or_(
                LabTest.patient_name.contains(search),
                LabTest.test_name.contains(search),
                LabTest.phone.contains(search)
            )
        )
    if status_filter:
        query = query.filter_by(status=status_filter)
    tests = query.order_by(LabTest.created_at.desc()).all()
    return render_template('admin/lab_tests.html',
        tests=tests, search=search, status_filter=status_filter, statuses=LAB_TEST_STATUSES)

@app.route('/admin/lab-tests/add', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'lab')
def add_lab_test():
    if request.method == 'POST':
        patient_name = request.form.get('patient_name')
        phone = request.form.get('phone')
        test_name = request.form.get('test_name')
        amount = request.form.get('amount', 0)
        test_date = request.form.get('test_date')
        notes = request.form.get('notes')
        status = request.form.get('status', 'Pending')

        if not patient_name or not test_name:
            flash('Patient name and test name are required', 'danger')
            return render_template('admin/lab_test_form.html', test=None, statuses=LAB_TEST_STATUSES)

        try:
            test_date_parsed = datetime.strptime(test_date, '%Y-%m-%d').date() if test_date else date.today()
        except:
            test_date_parsed = date.today()

        try:
            amount_val = float(amount) if amount else 0.0
        except:
            amount_val = 0.0

        lab_test = LabTest(
            patient_name=patient_name, phone=phone,
            test_name=test_name, amount=amount_val,
            test_date=test_date_parsed, notes=notes,
            status=status
        )
        db.session.add(lab_test)
        db.session.commit()
        flash('Lab test record added successfully', 'success')
        return redirect(url_for('admin_lab_tests'))
    return render_template('admin/lab_test_form.html', test=None, statuses=LAB_TEST_STATUSES)

@app.route('/admin/lab-tests/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'lab')
def edit_lab_test(id):
    lab_test = LabTest.query.get_or_404(id)
    if request.method == 'POST':
        lab_test.patient_name = request.form.get('patient_name')
        lab_test.phone = request.form.get('phone')
        lab_test.test_name = request.form.get('test_name')
        amount = request.form.get('amount', 0)
        try:
            lab_test.amount = float(amount) if amount else 0.0
        except:
            lab_test.amount = 0.0
        test_date = request.form.get('test_date')
        try:
            lab_test.test_date = datetime.strptime(test_date, '%Y-%m-%d').date() if test_date else date.today()
        except:
            pass
        lab_test.notes = request.form.get('notes')
        lab_test.status = request.form.get('status', 'Pending')
        db.session.commit()
        flash('Lab test record updated successfully', 'success')
        return redirect(url_for('admin_lab_tests'))
    return render_template('admin/lab_test_form.html', test=lab_test, statuses=LAB_TEST_STATUSES)

@app.route('/admin/lab-tests/delete/<int:id>', methods=['POST'])
@login_required
@role_required('main_admin', 'lab')
def delete_lab_test(id):
    lab_test = LabTest.query.get_or_404(id)
    db.session.delete(lab_test)
    db.session.commit()
    flash('Lab test record deleted successfully', 'success')
    return redirect(url_for('admin_lab_tests'))

@app.route('/admin/lab-tests/export')
@login_required
@role_required('main_admin', 'lab')
def export_lab_tests_csv():
    status_filter = request.args.get('status', '')
    query = LabTest.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    tests = query.order_by(LabTest.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Patient Name', 'Phone', 'Test Name', 'Amount (₹)', 'Test Date', 'Status', 'Notes', 'Created At'])
    for t in tests:
        writer.writerow([t.id, t.patient_name, t.phone, t.test_name,
                        t.amount, t.test_date, t.status, t.notes, t.created_at])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=lab_tests.csv'})

# ─── Admin Management ───────────────────────────────────────────────────────

@app.route('/admin/admins')
@login_required
@role_required('main_admin')
def admin_management():
    admins = Admin.query.order_by(Admin.role, Admin.username).all()
    return render_template('admin/admin_management.html', admins=admins)

@app.route('/admin/admins/reset-password/<int:id>', methods=['POST'])
@login_required
@role_required('main_admin')
def reset_admin_password(id):
    admin = Admin.query.get_or_404(id)
    new_password = request.form.get('new_password', '').strip()
    if not new_password or len(new_password) < 4:
        flash('Password must be at least 4 characters', 'danger')
        return redirect(url_for('admin_management'))
    admin.set_password(new_password)
    db.session.commit()
    flash(f'Password reset successfully for {admin.username}', 'success')
    return redirect(url_for('admin_management'))

# ─── Settings ───────────────────────────────────────────────────────────────

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@role_required('main_admin', 'lab', 'referral', 'hr')
def admin_settings():
    if request.method == 'POST':
        session['mail_username'] = request.form.get('mail_username', '')
        session['mail_password'] = request.form.get('mail_password', '')
        session['mail_recipient'] = request.form.get('mail_recipient', '')
        flash('Email settings saved successfully', 'success')
        return redirect(url_for('admin_settings'))
    return render_template('admin/settings.html')

@app.route('/admin/settings/test-email')
@login_required
@role_required('main_admin', 'lab', 'referral', 'hr')
def test_email():
    smtp_server = session.get('mail_username', '')
    smtp_password = session.get('mail_password', '')
    recipient = session.get('mail_recipient', '')

    if not smtp_server or not smtp_password or not recipient:
        flash('Please configure email settings first', 'danger')
        return redirect(url_for('admin_settings'))

    msg = MIMEMultipart()
    msg['From'] = smtp_server
    msg['To'] = recipient
    msg['Subject'] = 'JJ Hospital - Test Email'
    body = 'This is a test email from JJ Hospital Admin Panel. Your email settings are working correctly.'
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls(context=context)
            server.login(smtp_server, smtp_password)
            server.sendmail(smtp_server, recipient, msg.as_string())
        flash('Test email sent successfully!', 'success')
    except Exception as e:
        flash(f'Email sending error: {str(e)}', 'danger')

    return redirect(url_for('admin_settings'))

# ─── Init DB & Create Admin ─────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    if not Admin.query.first():
        seed_admins = [
            ('main_admin', 'admin123', 'main_admin'),
            ('lab_admin', 'admin123', 'lab'),
            ('referral_admin', 'admin123', 'referral'),
            ('hr_admin', 'admin123', 'hr'),
        ]
        for username, password, role in seed_admins:
            a = Admin(username=username, role=role)
            a.set_password(password)
            db.session.add(a)
        db.session.commit()
        print('Admin accounts created:')
        print('  main_admin / admin123 (main_admin)')
        print('  lab_admin / admin123 (lab)')
        print('  referral_admin / admin123 (referral)')
        print('  hr_admin / admin123 (hr)')

# ─── Run ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port)
