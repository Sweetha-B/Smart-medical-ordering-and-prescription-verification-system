# init_db.py - Complete Database Initialization for Smart Medical System
from app import app, mongo
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def init_database():
    with app.app_context():
        # Clear existing data
        print("Clearing existing data...")
        mongo.db.users.drop()
        mongo.db.medicines.drop()
        mongo.db.appointments.drop()
        mongo.db.prescriptions.drop()
        mongo.db.bills.drop()
        mongo.db.balance_orders.drop()
        mongo.db.inventory_transactions.drop()
        
        # Create indexes
        print("Creating indexes...")
        mongo.db.users.create_index('email', unique=True)
        mongo.db.users.create_index('role')
        mongo.db.prescriptions.create_index('prescription_id', unique=True)
        mongo.db.medicines.create_index('name')
        mongo.db.appointments.create_index([('doctor_id', 1), ('datetime', 1)])
        
        # ============ CREATE ADMIN ============
        print("Creating admin...")
        admin = {
            'email': 'admin@meditrace.com',
            'password': generate_password_hash('admin123'),
            'name': 'System Administrator',
            'role': 'admin',
            'phone': '+91 98765 43299',
            'created_at': datetime.utcnow(),
            'is_active': True
        }
        admin_id = mongo.db.users.insert_one(admin).inserted_id
        print(f"  Created: Admin - {admin['email']}")
        
        # ============ CREATE 15 DOCTORS ============
        print("\nCreating 15 doctors...")
        
        doctor_data = [
            {'name': 'Dr. Selvam K', 'specialization': 'Cardiologist', 'experience': 15, 'fee': 800, 'phone': '98765 43200'},
            {'name': 'Dr. Meena R', 'specialization': 'Cardiologist', 'experience': 12, 'fee': 600, 'phone': '98765 43201'},
            {'name': 'Dr. Senthil Kumar', 'specialization': 'Cardiologist', 'experience': 10, 'fee': 700, 'phone': '98765 43202'},
            {'name': 'Dr. Priya S', 'specialization': 'General Physician', 'experience': 8, 'fee': 750, 'phone': '98765 43203'},
            {'name': 'Dr. Rajesh M', 'specialization': 'General Physician', 'experience': 14, 'fee': 900, 'phone': '98765 43204'},
            {'name': 'Dr. Kavitha K', 'specialization': 'General Physician', 'experience': 9, 'fee': 650, 'phone': '98765 43205'},
            {'name': 'Dr. Murugan A', 'specialization': 'Pediatrician', 'experience': 11, 'fee': 750, 'phone': '98765 43206'},
            {'name': 'Dr. Lakshmi N', 'specialization': 'Pediatrician', 'experience': 7, 'fee': 700, 'phone': '98765 43207'},
            {'name': 'Dr. Arjun P', 'specialization': 'Dermatologist', 'experience': 13, 'fee': 850, 'phone': '98765 43208'},
            {'name': 'Dr. Divya S', 'specialization': 'Dermatologist', 'experience': 6, 'fee': 600, 'phone': '98765 43209'},
            {'name': 'Dr. Karthik R', 'specialization': 'Orthopedic', 'experience': 10, 'fee': 800, 'phone': '98765 43210'},
            {'name': 'Dr. Anitha M', 'specialization': 'Orthopedic', 'experience': 8, 'fee': 700, 'phone': '98765 43211'},
            {'name': 'Dr. Vikram S', 'specialization': 'Neurologist', 'experience': 12, 'fee': 900, 'phone': '98765 43212'},
            {'name': 'Dr. Shalini B', 'specialization': 'Gynecologist', 'experience': 5, 'fee': 750, 'phone': '98765 43213'},
            {'name': 'Dr. Harish K', 'specialization': 'ENT Specialist', 'experience': 9, 'fee': 650, 'phone': '98765 43214'}
        ]
        
        doctor_ids = []
        for i, doc in enumerate(doctor_data):
            # Create email: dr.[name]@meditrace.com (remove Dr. and spaces, lowercase)
            email_name = doc['name'].replace('Dr. ', '').lower().replace(' ', '')
            email = f"dr.{email_name}@meditrace.com"
            
            doctor = {
                'email': email,
                'password': generate_password_hash('doctor123'),
                'name': doc['name'],
                'role': 'doctor',
                'phone': f"+91 {doc['phone']}",
                'specialization': doc['specialization'],
                'experience': doc['experience'],
                'consultation_fee': doc['fee'],
                'license_number': f'MED-2024-{100 + i}',
                'created_at': datetime.utcnow(),
                'is_active': True
            }
            result = mongo.db.users.insert_one(doctor)
            doctor_ids.append(result.inserted_id)
            print(f"  Created: {doc['name']} - {email}")
        
        # ============ CREATE PHARMACY ============
        print("\nCreating pharmacy...")
        pharmacy = {
            'email': 'pharmacy@meditrace.com',
            'password': generate_password_hash('pharmacy123'),
            'name': 'Rajesh M',
            'role': 'pharmacy',
            'phone': '+91 98765 43215',
            'pharmacy_name': 'MediTrace Pharmacy',
            'license_number': 'PHARMA-2024-001',
            'created_at': datetime.utcnow(),
            'is_active': True
        }
        pharmacy_id = mongo.db.users.insert_one(pharmacy).inserted_id
        print(f"  Created: Pharmacy - {pharmacy['email']}")
        
        # ============ CREATE 20 PATIENTS ============
        print("\nCreating 20 patients...")
        
        patient_data = [
            {'name': 'Selvam M', 'age': 45, 'blood': 'O+', 'allergies': ['Penicillin'], 'conditions': ['Diabetes', 'Hypertension']},
            {'name': 'Kavitha S', 'age': 32, 'blood': 'A+', 'allergies': ['Aspirin'], 'conditions': ['Sinusitis']},
            {'name': 'Murugan R', 'age': 52, 'blood': 'B+', 'allergies': [], 'conditions': ['High Cholesterol', 'Hypertension', 'Diabetes']},
            {'name': 'Lakshmi P', 'age': 28, 'blood': 'AB+', 'allergies': ['Sulfa'], 'conditions': ['Infection', 'Fever']},
            {'name': 'Senthil K', 'age': 35, 'blood': 'O-', 'allergies': [], 'conditions': ['Mild Hypertension']},
            {'name': 'Priya D', 'age': 30, 'blood': 'A-', 'allergies': [], 'conditions': ['Hypothyroidism', 'Vitamin D Deficiency']},
            {'name': 'Rajesh K', 'age': 40, 'blood': 'B-', 'allergies': ['Penicillin'], 'conditions': ['Asthma', 'Allergies']},
            {'name': 'Meena S', 'age': 38, 'blood': 'AB-', 'allergies': ['NSAIDs'], 'conditions': ['Arthritis', 'Gastric Issues']},
            {'name': 'Arun K', 'age': 42, 'blood': 'O+', 'allergies': ['Codeine'], 'conditions': ['Diabetes']},
            {'name': 'Divya R', 'age': 29, 'blood': 'A+', 'allergies': ['Sulfa'], 'conditions': ['Hypertension']},
            {'name': 'Vijay M', 'age': 50, 'blood': 'B+', 'allergies': [], 'conditions': ['High Cholesterol']},
            {'name': 'Anu S', 'age': 33, 'blood': 'AB+', 'allergies': [], 'conditions': ['Asthma']},
            {'name': 'Kumar R', 'age': 47, 'blood': 'O-', 'allergies': ['Penicillin'], 'conditions': ['Diabetes', 'High Cholesterol']},
            {'name': 'Geetha P', 'age': 26, 'blood': 'A-', 'allergies': [], 'conditions': ['Allergies']},
            {'name': 'Suresh K', 'age': 55, 'blood': 'B-', 'allergies': ['Aspirin'], 'conditions': ['Hypertension']},
            {'name': 'Rekha S', 'age': 31, 'blood': 'AB-', 'allergies': [], 'conditions': ['Arthritis']},
            {'name': 'Prakash M', 'age': 44, 'blood': 'O+', 'allergies': [], 'conditions': ['Diabetes']},
            {'name': 'Vanitha R', 'age': 36, 'blood': 'A+', 'allergies': [], 'conditions': ['Hypothyroidism']},
            {'name': 'Ganesh K', 'age': 48, 'blood': 'B+', 'allergies': [], 'conditions': ['High Cholesterol']},
            {'name': 'Deepa S', 'age': 27, 'blood': 'AB+', 'allergies': [], 'conditions': ['Hypertension', 'Diabetes']}
        ]
        
        patient_ids = []
        for i, pat in enumerate(patient_data):
            # Create email: firstname.lastinitial@meditrace.com
            name_parts = pat['name'].lower().split()
            first_name = name_parts[0]
            last_initial = name_parts[1][0] if len(name_parts) > 1 else 'x'
            email = f"{first_name}.{last_initial}@meditrace.com"
            
            patient = {
                'email': email,
                'password': generate_password_hash('patient123'),
                'name': pat['name'],
                'role': 'patient',
                'phone': f"+91 98765 {43220 + i}",
                'age': pat['age'],
                'blood_group': pat['blood'],
                'allergies': pat['allergies'],
                'medical_history': pat['conditions'],
                'created_at': datetime.utcnow(),
                'is_active': True
            }
            result = mongo.db.users.insert_one(patient)
            patient_ids.append(result.inserted_id)
            print(f"  Created: {pat['name']} ({pat['age']} yrs) - {email}")
        
        # ============ CREATE MEDICINES ============
        print("\nCreating medicines...")
        medicines = [
            {'name': 'Paracetamol 500mg', 'generic_name': 'Acetaminophen', 'manufacturer': 'Cipla', 'stock': 100, 'price': 50, 'expiry_date': datetime(2027, 12, 31), 'rack': 'A-01', 'category': 'Pain Relief'},
            {'name': 'Amoxicillin 250mg', 'generic_name': 'Amoxicillin', 'manufacturer': 'GSK', 'stock': 45, 'price': 120, 'expiry_date': datetime(2026, 12, 31), 'rack': 'B-03', 'category': 'Antibiotic'},
            {'name': 'Atorvastatin 10mg', 'generic_name': 'Atorvastatin', 'manufacturer': 'Pfizer', 'stock': 80, 'price': 80, 'expiry_date': datetime(2027, 3, 15), 'rack': 'C-02', 'category': 'Cholesterol'},
            {'name': 'Metformin 500mg', 'generic_name': 'Metformin', 'manufacturer': 'USV', 'stock': 95, 'price': 45, 'expiry_date': datetime(2027, 8, 20), 'rack': 'D-01', 'category': 'Diabetes'},
            {'name': 'Losartan 50mg', 'generic_name': 'Losartan', 'manufacturer': 'Sun Pharma', 'stock': 25, 'price': 95, 'expiry_date': datetime(2026, 11, 10), 'rack': 'E-04', 'category': 'BP Medication'},
            {'name': 'Azithromycin 500mg', 'generic_name': 'Azithromycin', 'manufacturer': 'Abbott', 'stock': 60, 'price': 180, 'expiry_date': datetime(2027, 1, 5), 'rack': 'F-02', 'category': 'Antibiotic'},
            {'name': 'Cetirizine 10mg', 'generic_name': 'Cetirizine', 'manufacturer': 'Cipla', 'stock': 120, 'price': 25, 'expiry_date': datetime(2027, 7, 22), 'rack': 'G-01', 'category': 'Antihistamine'},
            {'name': 'Amlodipine 5mg', 'generic_name': 'Amlodipine', 'manufacturer': 'USV', 'stock': 70, 'price': 35, 'expiry_date': datetime(2027, 9, 10), 'rack': 'H-02', 'category': 'BP Medication'},
            {'name': 'Aspirin 75mg', 'generic_name': 'Aspirin', 'manufacturer': 'Bayer', 'stock': 90, 'price': 25, 'expiry_date': datetime(2027, 6, 15), 'rack': 'I-03', 'category': 'Blood Thinner'},
            {'name': 'Omeprazole 20mg', 'generic_name': 'Omeprazole', 'manufacturer': 'Dr Reddy\'s', 'stock': 110, 'price': 45, 'expiry_date': datetime(2027, 5, 20), 'rack': 'J-04', 'category': 'Antacid'},
            {'name': 'Insulin Glargine', 'generic_name': 'Insulin', 'manufacturer': 'Sanofi', 'stock': 30, 'price': 450, 'expiry_date': datetime(2026, 10, 30), 'rack': 'K-05', 'category': 'Diabetes'},
            {'name': 'Vitamin D3 60K', 'generic_name': 'Cholecalciferol', 'manufacturer': 'Abbott', 'stock': 150, 'price': 120, 'expiry_date': datetime(2028, 1, 15), 'rack': 'L-06', 'category': 'Supplements'},
            {'name': 'Calcium 500mg', 'generic_name': 'Calcium Carbonate', 'manufacturer': 'Cipla', 'stock': 200, 'price': 80, 'expiry_date': datetime(2028, 3, 20), 'rack': 'M-07', 'category': 'Supplements'},
            {'name': 'Dolo 650mg', 'generic_name': 'Paracetamol', 'manufacturer': 'Micro Labs', 'stock': 85, 'price': 35, 'expiry_date': datetime(2027, 11, 25), 'rack': 'N-08', 'category': 'Pain Relief'},
            {'name': 'Crocin 500mg', 'generic_name': 'Paracetamol', 'manufacturer': 'GSK', 'stock': 75, 'price': 40, 'expiry_date': datetime(2027, 9, 18), 'rack': 'O-09', 'category': 'Pain Relief'}
        ]
        
        for med in medicines:
            med['created_at'] = datetime.utcnow()
            med['updated_at'] = med['created_at']
            mongo.db.medicines.insert_one(med)
        print(f"  Created: {len(medicines)} medicines")
        
        # ============ CREATE APPOINTMENTS ============
        print("\nCreating appointments...")
        statuses = ['pending', 'approved', 'completed', 'cancelled']
        appointment_types = ['normal', 'emergency']
        
        for i in range(50):
            appointment = {
                'patient_id': patient_ids[i % 20],
                'doctor_id': doctor_ids[i % 15],
                'datetime': datetime.utcnow() + timedelta(days=i % 30, hours=9 + (i % 8)),
                'type': appointment_types[i % 2],
                'status': statuses[i % 4],
                'reason': f'Consultation for health issue {i+1}',
                'created_at': datetime.utcnow() - timedelta(days=i % 10),
                'priority': 1 if appointment_types[i % 2] == 'emergency' else 0
            }
            mongo.db.appointments.insert_one(appointment)
        print(f"  Created: 50 appointments")
        
        # ============ CREATE PRESCRIPTIONS ============
        print("\nCreating prescriptions...")
        medicines_list = list(mongo.db.medicines.find())
        status_list = ['active', 'dispensed', 'expired', 'active']
        
        for i in range(40):
            prescription = {
                'prescription_id': f'PX-{2024}{1000 + i}',
                'patient_id': patient_ids[i % 20],
                'doctor_id': doctor_ids[i % 15],
                'medicines': [
                    {
                        'name': medicines_list[i % len(medicines_list)]['name'],
                        'dosage': '1 tablet ' + ('twice daily' if i % 2 == 0 else 'once daily'),
                        'quantity': 30 + (i % 20),
                        'duration': '30 days'
                    }
                ],
                'diagnosis': f'Diagnosis for patient {i+1}',
                'instructions': 'Take with food. Complete full course.',
                'status': status_list[i % 4],
                'created_at': datetime.utcnow() - timedelta(days=i),
                'total_quantity': 60,
                'dispensed_quantity': 20 + (i % 40) if status_list[i % 4] == 'dispensed' else 0
            }
            mongo.db.prescriptions.insert_one(prescription)
        print(f"  Created: 40 prescriptions")
        
        # ============ CREATE INVENTORY TRANSACTIONS ============
        print("\nCreating inventory transactions...")
        for i in range(30):
            transaction = {
                'medicine_id': medicines_list[i % len(medicines_list)]['_id'],
                'medicine_name': medicines_list[i % len(medicines_list)]['name'],
                'quantity': 10 + (i % 50),
                'type': 'purchase' if i % 3 == 0 else 'dispense',
                'timestamp': datetime.utcnow() - timedelta(days=i),
                'user_id': pharmacy_id,
                'notes': f'Transaction {i+1}'
            }
            mongo.db.inventory_transactions.insert_one(transaction)
        print(f"  Created: 30 inventory transactions")
        
        # ============ PRINT SUMMARY ============
        print("\n" + "="*70)
        print("✅ DATABASE INITIALIZED SUCCESSFULLY!")
        print("="*70)
        print(f"\n📊 DATABASE SUMMARY:")
        print(f"   👑 Admin: 1")
        print(f"   👨‍⚕️ Doctors: {len(doctor_ids)}")
        print(f"   💊 Pharmacy: 1")
        print(f"   👤 Patients: {len(patient_ids)}")
        print(f"   💊 Medicines: {len(medicines)}")
        print(f"   📅 Appointments: 50")
        print(f"   📋 Prescriptions: 40")
        print(f"   📦 Inventory Transactions: 30")
        
        print("\n🔑 LOGIN CREDENTIALS (all @meditrace.com domain):")
        print("-"*50)
        print("\n👑 ADMIN:")
        print("   admin@meditrace.com / admin123")
        
        print("\n👨‍⚕️ DOCTORS (Password: doctor123):")
        for i, doc in enumerate(doctor_data[:5]):
            email_name = doc['name'].replace('Dr. ', '').lower().replace(' ', '')
            print(f"   dr.{email_name}@meditrace.com - {doc['name']} ({doc['specialization']})")
        print("   ... and 10 more doctors")
        
        print("\n👤 PATIENTS (Password: patient123):")
        for i, pat in enumerate(patient_data[:5]):
            name_parts = pat['name'].lower().split()
            first_name = name_parts[0]
            last_initial = name_parts[1][0] if len(name_parts) > 1 else 'x'
            print(f"   {first_name}.{last_initial}@meditrace.com - {pat['name']}")
        print("   ... and 15 more patients")
        
        print("\n💊 PHARMACY:")
        print("   pharmacy@meditrace.com / pharmacy123")
        
        print("\n📋 SAMPLE PRESCRIPTION IDs:")
        for i in range(3):
            print(f"   PX-2024{1000 + i}")
        
        print("\n💊 LOW STOCK ALERTS:")
        low_stock_meds = mongo.db.medicines.find({'stock': {'$lt': 50}})
        for med in low_stock_meds:
            print(f"   {med['name']}: {med['stock']} units remaining")
        
        print("\n" + "="*70)
        print("🎯 SYSTEM READY FOR USE!")
        print("="*70)
# ==================== CREATE BILLS ====================
print("\nCreating bills...")
prescriptions_list = list(mongo.db.prescriptions.find())
medicines_list = list(mongo.db.medicines.find())

if prescriptions_list and medicines_list:
    for i, pres in enumerate(prescriptions_list[:10]):  # Create bills for first 10 prescriptions
        # Calculate bill amount
        subtotal = 0
        items = []
        
        for med in pres['medicines']:
            medicine = next((m for m in medicines_list if m['name'].lower() == med['name'].lower()), None)
            if medicine:
                item_total = medicine['price'] * med['quantity']
                subtotal += item_total
                items.append({
                    'medicine_name': med['name'],
                    'quantity': med['quantity'],
                    'unit_price': medicine['price'],
                    'total': item_total
                })
        
        if items:  # Only create bill if items exist
            gst_amount = subtotal * 0.12
            grand_total = subtotal + gst_amount
            
            bill_number = f"BILL-{datetime.utcnow().strftime('%Y%m%d')}-{pres['prescription_id'][-6:]}"
            
            bill = {
                'bill_number': bill_number,
                'patient_id': pres['patient_id'],
                'prescription_id': pres['_id'],
                'prescription_code': pres['prescription_id'],
                'items': items,
                'subtotal': round(subtotal, 2),
                'gst_rate': 0.12,
                'gst_amount': round(gst_amount, 2),
                'total': round(grand_total, 2),
                'status': 'paid' if i % 2 == 0 else 'pending',
                'payment_method': 'cash' if i % 2 == 0 else None,
                'payment_date': datetime.utcnow() - timedelta(days=i) if i % 2 == 0 else None,
                'created_at': datetime.utcnow() - timedelta(days=i)
            }
            
            mongo.db.bills.insert_one(bill)
    
    print(f"  Created: {mongo.db.bills.count_documents({})} bills")
else:
    print("  No prescriptions or medicines found, skipping bills creation")
if __name__ == '__main__':
    init_database()