from flask import Flask, render_template, jsonify, request, redirect, url_for, make_response
from flask_cors import CORS
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import qrcode
import io
import base64
from bson import ObjectId
import json
import secrets
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['MONGO_URI'] = os.getenv('MONGO_URI', 'mongodb://localhost:27017/medismart_db')
app.config['JWT_EXPIRATION'] = 86400

mongo = PyMongo(app)
CORS(app)

# ==================== Helper Functions ====================

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = JSONEncoder

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token missing'}), 401
        try:
            token = token.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
            request.current_user = current_user
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.current_user['role'] not in roles:
                return jsonify({'error': 'Access denied'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def generate_qr_code(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(json.dumps(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return base64.b64encode(img_io.getvalue()).decode()

# ==================== Authentication Routes ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    
    user = mongo.db.users.find_one({'email': email, 'role': role})
    if not user or not check_password_hash(user['password'], password):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    token = jwt.encode({
        'user_id': str(user['_id']),
        'role': user['role'],
        'exp': datetime.utcnow() + timedelta(seconds=app.config['JWT_EXPIRATION'])
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    response = make_response(jsonify({
        'token': token,
        'user': {
            '_id': str(user['_id']),
            'name': user['name'],
            'email': user['email'],
            'role': user['role']
        }
    }))
    response.set_cookie('token', token, httponly=False, max_age=86400, path='/')
    return response, 200

# ==================== Payment Routes ====================

@app.route('/api/patient/payments/status', methods=['GET'])
@token_required
@role_required(['patient'])
def get_payment_status():
    user_id = request.current_user['_id']
    
    # Find or create payment status for this user
    payment = mongo.db.payments.find_one({'patient_id': user_id})
    
    if not payment:
        # Default payment status
        default_status = {
            'patient_id': user_id,
            'medicines': [
                {'id': 1, 'name': 'Metformin 500mg', 'amount': 2700, 'status': 'pending'},
                {'id': 2, 'name': 'Losartan 50mg', 'amount': 1560, 'status': 'pending'},
                {'id': 3, 'name': 'Amoxicillin 250mg', 'amount': 1800, 'status': 'pending'}
            ],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        result = mongo.db.payments.insert_one(default_status)
        default_status['_id'] = str(result.inserted_id)
        return jsonify(default_status['medicines']), 200
    
    return jsonify(payment['medicines']), 200

@app.route('/api/patient/payments/pay', methods=['POST'])
@token_required
@role_required(['patient'])
def make_payment():
    user_id = request.current_user['_id']
    data = request.json
    medicine_id = data.get('medicine_id')
    amount_paid = data.get('amount_paid', 0)
    payment_method = data.get('payment_method', 'cash')
    
    # First, find which medicine this is
    payment_record = mongo.db.payments.find_one({'patient_id': user_id})
    medicine_name = ""
    medicine_quantity = 1
    
    if payment_record and 'medicines' in payment_record:
        for med in payment_record['medicines']:
            if med['id'] == medicine_id:
                medicine_name = med['name']
                medicine_quantity = med.get('quantity', 1)
                break
    
    # Update medicine payment status
    result = mongo.db.payments.update_one(
        {'patient_id': user_id, 'medicines.id': medicine_id},
        {'$set': {
            'medicines.$.status': 'paid',
            'medicines.$.amount_paid': amount_paid,
            'medicines.$.payment_method': payment_method,
            'medicines.$.paid_date': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow()
        }}
    )
    
    if result.modified_count > 0:
        # IMPORTANT: UPDATE existing bill instead of creating new one
        # Find the bill for this medicine
        existing_bill = mongo.db.bills.find_one({
            'patient_id': user_id,
            'items.medicine_name': medicine_name,
            'status': 'pending'
        })
        
        if existing_bill:
            # Update existing bill to paid
            gst_amount = amount_paid * 0.12
            total_with_gst = amount_paid + gst_amount
            
            mongo.db.bills.update_one(
                {'_id': existing_bill['_id']},
                {
                    '$set': {
                        'status': 'paid',
                        'payment_method': payment_method,
                        'payment_date': datetime.utcnow(),
                        'subtotal': round(amount_paid, 2),
                        'gst_amount': round(gst_amount, 2),
                        'total': round(total_with_gst, 2),
                        'items.0.unit_price': amount_paid,
                        'items.0.total': amount_paid
                    }
                }
            )
            print(f"Updated existing bill for {medicine_name} to PAID")
        else:
            # Create new bill only if no existing bill found
            gst_amount = amount_paid * 0.12
            total_with_gst = amount_paid + gst_amount
            
            bill = {
                'bill_number': f"BILL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                'patient_id': user_id,
                'items': [{
                    'medicine_name': medicine_name,
                    'quantity': medicine_quantity,
                    'unit_price': amount_paid,
                    'total': amount_paid
                }],
                'subtotal': round(amount_paid, 2),
                'gst_rate': 0.12,
                'gst_amount': round(gst_amount, 2),
                'total': round(total_with_gst, 2),
                'status': 'paid',
                'payment_method': payment_method,
                'payment_date': datetime.utcnow(),
                'created_at': datetime.utcnow()
            }
            mongo.db.bills.insert_one(bill)
            print(f"Created new bill for {medicine_name}")
        
        return jsonify({'message': 'Payment successful', 'amount': amount_paid}), 200
    else:
        return jsonify({'error': 'Payment failed'}), 400
# ==================== Frontend Routes ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/patient/dashboard')
def patient_dashboard():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/dashboard.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/dashboard')
def doctor_dashboard():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/dashboard.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/dashboard')
def pharmacy_dashboard():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/dashboard.html', current_user=user)
    except:
        return redirect('/')
@app.route('/pharmacy/dispensed-history')
def pharmacy_dispensed_history_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/dispensed_history.html', current_user=user)
    except:
        return redirect('/')

@app.route('/logout')
def logout():
    response = redirect('/')
    response.delete_cookie('token')
    return response

# ==================== API Routes ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.json
    
    # Only patients can self-register
    if data.get('role') != 'patient':
        return jsonify({'error': 'Only patients can self-register. Doctors and Pharmacy must be added by admin.'}), 403
    
    # Check if email already exists
    existing = mongo.db.users.find_one({'email': data['email']})
    if existing:
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create new patient
    user = {
        'email': data['email'],
        'password': generate_password_hash(data['password']),
        'name': data['name'],
        'role': 'patient',
        'phone': data.get('phone'),
        'date_of_birth': data.get('date_of_birth'),
        'allergies': data.get('allergies', []),
        'created_at': datetime.utcnow(),
        'is_active': True
    }
    
    result = mongo.db.users.insert_one(user)
    user['_id'] = str(result.inserted_id)
    del user['password']
    
    return jsonify({'message': 'Registration successful', 'user': user}), 201

@app.route('/api/patient/dashboard', methods=['GET'])
@token_required
@role_required(['patient'])
def get_patient_stats():
    user_id = request.current_user['_id']
    stats = {
        'totalAppointments': mongo.db.appointments.count_documents({'patient_id': user_id}),
        'activePrescriptions': mongo.db.prescriptions.count_documents({'patient_id': user_id, 'status': 'active'}),
        'pendingPayments': 0
    }
    return jsonify(stats), 200

@app.route('/api/doctor/appointments', methods=['GET'])
@token_required
@role_required(['doctor'])
def get_doctor_appointments():
    appointments = list(mongo.db.appointments.find({'doctor_id': request.current_user['_id']}))
    for apt in appointments:
        apt['_id'] = str(apt['_id'])
        patient = mongo.db.users.find_one({'_id': apt['patient_id']})
        apt['patient_name'] = patient['name'] if patient else 'Unknown'
    return jsonify(appointments), 200

@app.route('/api/doctor/appointment/<appointment_id>/status', methods=['PUT'])
@token_required
@role_required(['doctor'])
def update_appointment_status(appointment_id):
    data = request.json
    status = data.get('status')
    mongo.db.appointments.update_one(
        {'_id': ObjectId(appointment_id)},
        {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
    )
    return jsonify({'message': f'Appointment {status}'}), 200

@app.route('/api/doctor/prescription', methods=['POST'])
@token_required
@role_required(['doctor'])
def create_prescription():
    data = request.json
    prescription_id = secrets.token_hex(8).upper()
    
    prescription = {
        'prescription_id': prescription_id,
        'patient_id': ObjectId(data['patient_id']),
        'doctor_id': request.current_user['_id'],
        'medicines': data['medicines'],
        'diagnosis': data['diagnosis'],
        'instructions': data.get('instructions', ''),
        'total_quantity': sum(m['quantity'] for m in data['medicines']),
        'dispensed_quantity': 0,
        'status': 'active',
        'created_at': datetime.utcnow()
    }
    
    qr_data = {'prescription_id': prescription_id, 'patient_id': data['patient_id']}
    prescription['qr_code'] = generate_qr_code(qr_data)
    
    mongo.db.prescriptions.insert_one(prescription)
    return jsonify({'message': 'Prescription created', 'prescription_id': prescription_id, 'qr_code': prescription['qr_code']}), 201

@app.route('/api/pharmacy/medicines', methods=['GET'])
@token_required
@role_required(['pharmacy'])
def get_medicines():
    medicines = list(mongo.db.medicines.find())
    current_date = datetime.utcnow()
    
    for med in medicines:
        med['_id'] = str(med['_id'])
        expiry_date = med.get('expiry_date')
        
        # Check if expired
        is_expired = expiry_date and expiry_date < current_date
        
        if is_expired:
            med['status'] = 'Expired'
        elif med['stock'] == 0:
            med['status'] = 'Out of Stock'
        elif med['stock'] < 5:
            med['status'] = 'Low Stock'
        else:
            med['status'] = 'Available'
        
        # Format date for display
        if expiry_date:
            med['expiry_date_display'] = expiry_date.strftime('%d/%m/%Y')
        else:
            med['expiry_date_display'] = 'N/A'
    
    return jsonify(medicines), 200

@app.route('/api/pharmacy/medicine/<medicine_id>', methods=['DELETE'])
@token_required
@role_required(['pharmacy'])
def delete_medicine(medicine_id):
    mongo.db.medicines.delete_one({'_id': ObjectId(medicine_id)})
    return jsonify({'message': 'Medicine deleted'}), 200

@app.route('/api/pharmacy/verify-prescription', methods=['POST'])
@token_required
@role_required(['pharmacy'])
def verify_prescription():
    data = request.json
    prescription_id = data.get('prescription_id')
    
    prescription = mongo.db.prescriptions.find_one({'prescription_id': prescription_id})
    if not prescription:
        return jsonify({'error': 'Prescription not found'}), 404
    
    patient = mongo.db.users.find_one({'_id': prescription['patient_id']})
    doctor = mongo.db.users.find_one({'_id': prescription['doctor_id']})
    
    # Check stock
    stock_status = []
    for med in prescription['medicines']:
        inventory = mongo.db.medicines.find_one({'name': {'$regex': f"^{med['name']}$", '$options': 'i'}})
        stock_status.append({
            'name': med['name'],
            'requested': med['quantity'],
            'available': inventory['stock'] if inventory else 0,
            'sufficient': (inventory['stock'] if inventory else 0) >= med['quantity']
        })
    
    return jsonify({
        'prescription': {
            '_id': str(prescription['_id']),
            'prescription_id': prescription['prescription_id'],
            'medicines': prescription['medicines'],
            'diagnosis': prescription['diagnosis']
        },
        'patient': {'name': patient['name'], 'phone': patient.get('phone', '')},
        'doctor': {'name': doctor['name']},
        'stock_status': stock_status
    }), 200

@app.route('/api/pharmacy/dispense', methods=['POST'])
@token_required
@role_required(['pharmacy'])
def dispense_prescription():
    data = request.json
    prescription_id = data.get('prescription_id')
    
    prescription = mongo.db.prescriptions.find_one({'_id': ObjectId(prescription_id)})
    if not prescription:
        return jsonify({'error': 'Prescription not found'}), 404
    
    current_date = datetime.utcnow()
    
    # Check each medicine for expiry and stock
    for med in prescription['medicines']:
        medicine = mongo.db.medicines.find_one({'name': {'$regex': f"^{med['name']}$", '$options': 'i'}})
        
        if not medicine:
            return jsonify({'error': f'Medicine {med["name"]} not found in inventory'}), 404
        
        # Check if medicine is expired
        expiry_date = medicine.get('expiry_date')
        if expiry_date:
            if isinstance(expiry_date, str):
                expiry_date = datetime.fromisoformat(expiry_date)
            
            if expiry_date < current_date:
                return jsonify({'error': f'Cannot dispense {med["name"]} - Medicine has EXPIRED on {expiry_date.strftime("%d/%m/%Y")}'}), 400
        
        # Check stock
        if medicine['stock'] < med['quantity']:
            return jsonify({'error': f'Insufficient stock for {med["name"]}. Available: {medicine["stock"]}'}), 400
    
    # Update stock and prescription status
    for med in prescription['medicines']:
        mongo.db.medicines.update_one(
            {'name': {'$regex': f"^{med['name']}$", '$options': 'i'}},
            {'$inc': {'stock': -med['quantity']}}
        )
    
    mongo.db.prescriptions.update_one(
        {'_id': ObjectId(prescription_id)},
        {'$set': {'status': 'dispensed', 'dispensed_at': datetime.utcnow()}}
    )
    
    return jsonify({'message': 'Prescription dispensed successfully'}), 200


# ==================== Admin API Routes ====================

@app.route('/api/admin/stats', methods=['GET'])
@token_required
@role_required(['admin'])
def admin_stats_api():
    total_patients = mongo.db.users.count_documents({'role': 'patient'})
    total_doctors = mongo.db.users.count_documents({'role': 'doctor'})
    total_appointments = mongo.db.appointments.count_documents({})
    total_prescriptions = mongo.db.prescriptions.count_documents({})
    
    return jsonify({
        'totalPatients': total_patients,
        'totalDoctors': total_doctors,
        'totalAppointments': total_appointments,
        'totalPrescriptions': total_prescriptions
    }), 200


@app.route('/api/admin/doctors/recent', methods=['GET'])
@token_required
@role_required(['admin'])
def admin_recent_doctors_api():
    doctors = list(mongo.db.users.find(
        {'role': 'doctor'},
        {'password': 0}
    ).sort('created_at', -1).limit(5))
    
    for doctor in doctors:
        doctor['_id'] = str(doctor['_id'])
    
    return jsonify(doctors), 200

@app.route('/api/admin/patients/recent', methods=['GET'])
@token_required
@role_required(['admin'])
def admin_recent_patients_api():
    patients = list(mongo.db.users.find(
        {'role': 'patient'},
        {'password': 0}
    ).sort('created_at', -1).limit(5))
    
    for patient in patients:
        patient['_id'] = str(patient['_id'])
    
    return jsonify(patients), 200

# ==================== Patient Page Routes ====================

@app.route('/patient/book-appointment')
def patient_book_appointment():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/book_appointment.html', current_user=user)
    except:
        return redirect('/')

@app.route('/patient/prescriptions')
def patient_prescriptions():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/prescriptions.html', current_user=user)
    except:
        return redirect('/')

@app.route('/patient/balance-orders')
def patient_balance_orders():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/balance_orders.html', current_user=user)
    except:
        return redirect('/')

@app.route('/patient/payments')
def patient_payments():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/payments.html', current_user=user)
    except:
        return redirect('/')

@app.route('/patient/profile')
def patient_profile():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/profile.html', current_user=user)
    except:
        return redirect('/')

@app.route('/patient/support')
def patient_support():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/support.html', current_user=user)
    except:
        return redirect('/')

        # ==================== Doctor Page Routes ====================

@app.route('/doctor/dashboard')
def doctor_dashboard_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/dashboard.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/appointments')
def doctor_appointments_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/appointments.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/patients')
def doctor_patients_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/patients.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/write-prescription')
def doctor_write_prescription_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/write_prescription.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/prescriptions')
def doctor_prescriptions_history_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/prescriptions.html', current_user=user)
    except:
        return redirect('/')

@app.route('/doctor/profile')
def doctor_profile_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'doctor':
            return redirect('/')
        return render_template('doctor/profile.html', current_user=user)
    except:
        return redirect('/')
    

# ==================== BILLING ROUTES FOR PATIENT ====================

# 1. Get all bills for a patient
@app.route('/api/patient/bills', methods=['GET'])
@token_required
@role_required(['patient'])
def get_patient_bills():
    """Get all bills for the logged-in patient"""
    patient_id = request.current_user['_id']
    
    bills = list(mongo.db.bills.find({'patient_id': patient_id}).sort('created_at', -1))
    
    for bill in bills:
        bill['_id'] = str(bill['_id'])
        bill['patient_id'] = str(bill['patient_id'])
        if 'prescription_id' in bill:
            bill['prescription_id'] = str(bill['prescription_id'])
    
    return jsonify(bills), 200
@app.route('/patient/billing')
def patient_billing_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'patient':
            return redirect('/')
        return render_template('patient/billing.html', current_user=user)
    except:
        return redirect('/')

# 2. Get single bill details
@app.route('/api/patient/bill/<bill_id>', methods=['GET'])
@token_required
@role_required(['patient'])
def get_bill_details(bill_id):
    """Get detailed bill information"""
    patient_id = request.current_user['_id']
    
    bill = mongo.db.bills.find_one({
        '_id': ObjectId(bill_id),
        'patient_id': patient_id
    })
    
    if not bill:
        return jsonify({'error': 'Bill not found'}), 404
    
    bill['_id'] = str(bill['_id'])
    bill['patient_id'] = str(bill['patient_id'])
    
    # Get prescription details if available
    if 'prescription_id' in bill:
        prescription = mongo.db.prescriptions.find_one({'_id': bill['prescription_id']})
        if prescription:
            doctor = mongo.db.users.find_one({'_id': prescription['doctor_id']})
            bill['doctor_name'] = doctor['name'] if doctor else 'Unknown'
            bill['diagnosis'] = prescription.get('diagnosis', '')
    
    return jsonify(bill), 200


# 3. Generate bill after dispensing (Called by pharmacy when dispensing)
@app.route('/api/pharmacy/generate-bill', methods=['POST'])
@token_required
@role_required(['pharmacy'])
def generate_bill():
    """Generate bill when pharmacy dispenses medicine"""
    data = request.json
    prescription_id = data.get('prescription_id')
    
    # Get prescription details
    prescription = mongo.db.prescriptions.find_one({'_id': ObjectId(prescription_id)})
    if not prescription:
        return jsonify({'error': 'Prescription not found'}), 404
    
    # Calculate bill amount
    subtotal = 0
    items = []
    
    for med in prescription['medicines']:
        medicine = mongo.db.medicines.find_one({'name': {'$regex': f"^{med['name']}$", '$options': 'i'}})
        if medicine:
            item_total = medicine['price'] * med['quantity']
            subtotal += item_total
            items.append({
                'medicine_name': med['name'],
                'quantity': med['quantity'],
                'unit_price': medicine['price'],
                'total': item_total
            })
    
    # Calculate GST (12%)
    gst_rate = 0.12
    gst_amount = subtotal * gst_rate
    grand_total = subtotal + gst_amount
    
    # Create bill number
    bill_number = f"BILL-{datetime.utcnow().strftime('%Y%m%d')}-{prescription['prescription_id'][-6:]}"
    
    bill = {
        'bill_number': bill_number,
        'patient_id': prescription['patient_id'],
        'prescription_id': prescription['_id'],
        'prescription_code': prescription['prescription_id'],
        'items': items,
        'subtotal': round(subtotal, 2),
        'gst_rate': gst_rate,
        'gst_amount': round(gst_amount, 2),
        'total': round(grand_total, 2),
        'status': 'pending',  # pending, paid
        'payment_method': None,
        'payment_date': None,
        'created_at': datetime.utcnow(),
        'dispensed_by': request.current_user['_id'],
        'dispensed_by_name': request.current_user['name']
    }
    
    result = mongo.db.bills.insert_one(bill)
    bill['_id'] = str(result.inserted_id)
    
    return jsonify({'message': 'Bill generated', 'bill': bill}), 201


# 4. Patient makes payment for bill
@app.route('/api/patient/pay-bill/<bill_id>', methods=['POST'])
@token_required
@role_required(['patient'])
def pay_bill(bill_id):
    """Patient pays the bill"""
    data = request.json
    payment_method = data.get('payment_method', 'cash')
    
    bill = mongo.db.bills.find_one({
        '_id': ObjectId(bill_id),
        'patient_id': request.current_user['_id']
    })
    
    if not bill:
        return jsonify({'error': 'Bill not found'}), 404
    
    if bill['status'] == 'paid':
        return jsonify({'error': 'Bill already paid'}), 400
    
    # Update bill status
    mongo.db.bills.update_one(
        {'_id': ObjectId(bill_id)},
        {
            '$set': {
                'status': 'paid',
                'payment_method': payment_method,
                'payment_date': datetime.utcnow()
            }
        }
    )
    
    # Record payment transaction
    payment = {
        'bill_id': ObjectId(bill_id),
        'bill_number': bill['bill_number'],
        'patient_id': request.current_user['_id'],
        'amount': bill['total'],
        'payment_method': payment_method,
        'status': 'completed',
        'payment_date': datetime.utcnow()
    }
    mongo.db.payments.insert_one(payment)
    
    # Update prescription status to paid
    if 'prescription_id' in bill:
        mongo.db.prescriptions.update_one(
            {'_id': bill['prescription_id']},
            {'$set': {'payment_status': 'paid'}}
        )
    
    return jsonify({'message': 'Payment successful', 'amount': bill['total']}), 200


# 5. Get billing summary/stats for patient dashboard
@app.route('/api/patient/billing-stats', methods=['GET'])
@token_required
@role_required(['patient'])
def get_billing_stats():
    """Get billing statistics for patient dashboard"""
    patient_id = request.current_user['_id']
    
    bills = list(mongo.db.bills.find({'patient_id': patient_id}))
    
    total_bills = len(bills)
    pending_bills = len([b for b in bills if b['status'] == 'pending'])
    paid_bills = len([b for b in bills if b['status'] == 'paid'])
    
    total_amount = sum(b['total'] for b in bills)
    pending_amount = sum(b['total'] for b in bills if b['status'] == 'pending')
    paid_amount = sum(b['total'] for b in bills if b['status'] == 'paid')
    
    return jsonify({
        'total_bills': total_bills,
        'pending_bills': pending_bills,
        'paid_bills': paid_bills,
        'total_amount': round(total_amount, 2),
        'pending_amount': round(pending_amount, 2),
        'paid_amount': round(paid_amount, 2)
    }), 200


# 6. Download bill as PDF (HTML version for print)
@app.route('/api/patient/bill/<bill_id>/print', methods=['GET'])
@token_required
@role_required(['patient'])
def print_bill(bill_id):
    """Get bill in printable format"""
    patient_id = request.current_user['_id']
    
    bill = mongo.db.bills.find_one({
        '_id': ObjectId(bill_id),
        'patient_id': patient_id
    })
    
    if not bill:
        return jsonify({'error': 'Bill not found'}), 404
    
    # Get patient details
    patient = mongo.db.users.find_one({'_id': patient_id})
    
    # Get prescription for doctor details
    prescription = None
    doctor = None
    if 'prescription_id' in bill:
        prescription = mongo.db.prescriptions.find_one({'_id': bill['prescription_id']})
        if prescription:
            doctor = mongo.db.users.find_one({'_id': prescription['doctor_id']})
    
    bill['_id'] = str(bill['_id'])
    bill['patient'] = {
        'name': patient['name'],
        'email': patient['email'],
        'phone': patient.get('phone', '')
    }
    if doctor:
        bill['doctor'] = {
            'name': doctor['name'],
            'specialization': doctor.get('specialization', '')
        }
    
    return jsonify(bill), 200


    # ==================== Pharmacy Page Routes ====================

@app.route('/pharmacy/dashboard')
def pharmacy_dashboard_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/dashboard.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/verify-prescription')
def pharmacy_verify_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/verify_prescription.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/inventory')
def pharmacy_inventory_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/inventory.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/billing')
def pharmacy_billing_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/billing.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/profile')
def pharmacy_profile_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/profile.html', current_user=user)
    except:
        return redirect('/')
    
    # ==================== Pharmacy Additional Routes ====================

@app.route('/pharmacy/orders')
def pharmacy_orders_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/orders.html', current_user=user)
    except:
        return redirect('/')

@app.route('/pharmacy/reports')
def pharmacy_reports_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/reports.html', current_user=user)
    except:
        return redirect('/')
    # ==================== Admin Page Routes ====================

@app.route('/admin/dashboard')
def admin_dashboard_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/dashboard.html', current_user=user)
    except:
        return redirect('/')

@app.route('/admin/doctors')
def admin_doctors_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/doctors.html', current_user=user)
    except:
        return redirect('/')

@app.route('/admin/patients')
def admin_patients_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/patients.html', current_user=user)
    except:
        return redirect('/')

@app.route('/admin/pharmacy')
def admin_pharmacy_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/pharmacy.html', current_user=user)
    except:
        return redirect('/')

@app.route('/admin/appointments')
def admin_appointments_page():
    token = request.cookies.get('token')
    print(f"Appointments page - Token: {token[:50] if token else 'None'}...")
    
    if not token:
        print("No token, redirecting to /")
        return redirect('/')
    
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        print(f"Decoded token user_id: {data['user_id']}")
        
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        print(f"Found user: {user['email'] if user else 'None'} - Role: {user['role'] if user else 'None'}")
        
        if not user or user['role'] != 'admin':
            print(f"User role mismatch or not found. Role: {user['role'] if user else 'None'}")
            return redirect('/')
        
        print("Rendering admin appointments template")
        return render_template('admin/appointments.html', current_user=user)
        
    except jwt.ExpiredSignatureError:
        print("Token expired")
        return redirect('/')
    except Exception as e:
        print(f"Error in admin appointments: {e}")
        return redirect('/')
@app.route('/admin/reports')
def admin_reports_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/reports.html', current_user=user)
    except:
        return redirect('/')

@app.route('/admin/settings')
def admin_settings_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'admin':
            return redirect('/')
        return render_template('admin/settings.html', current_user=user)
    except:
        return redirect('/')
@app.route('/pharmacy/balance-orders')
def pharmacy_balance_orders_page():
    token = request.cookies.get('token')
    if not token:
        return redirect('/')
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user = mongo.db.users.find_one({'_id': ObjectId(data['user_id'])})
        if not user or user['role'] != 'pharmacy':
            return redirect('/')
        return render_template('pharmacy/balance_orders.html', current_user=user)
    except Exception as e:
        print(f"Error in pharmacy balance orders: {e}")
        return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)