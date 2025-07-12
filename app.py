from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import json
import os
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a strong random key

USER_DB = "db/users.json"
QUEUE_DB = "db/queue.json"
PASSWORD_RESETS_DB = "db/password_resets.json"

# Ensure data files exist
os.makedirs("db", exist_ok=True)
if not os.path.exists(USER_DB):
    with open(USER_DB, "w") as f:
        json.dump([], f)
if not os.path.exists(QUEUE_DB):
    with open(QUEUE_DB, "w") as f:
        json.dump({}, f)  # Changed to dictionary for business separation
if not os.path.exists(PASSWORD_RESETS_DB):
    with open(PASSWORD_RESETS_DB, "w") as f:
        json.dump([], f)

# Load & save functions
def load_users():
    with open(USER_DB) as f:
        return json.load(f)

def save_users(data):
    with open(USER_DB, "w") as f:
        json.dump(data, f, indent=2)

def load_queue():
    try:
        with open(QUEUE_DB) as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        return {}

def save_queue(data):
    with open(QUEUE_DB, "w") as f:
        json.dump(data, f, indent=2)

def load_password_resets():
    try:
        with open(PASSWORD_RESETS_DB) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError, FileNotFoundError):
        return []

def save_password_resets(data):
    with open(PASSWORD_RESETS_DB, "w") as f:
        json.dump(data, f, indent=2)

# Generate unique token ID per business per day
def generate_token_id(business_id):
    print("Generating token ID for business:", business_id)
    today = datetime.now().strftime("%Y-%m-%d")
    queue_data = load_queue()
    
    # Initialize business data if not exists
    if business_id not in queue_data:
        queue_data[business_id] = {}
    
    # Initialize today's queue if not exists
    if today not in queue_data[business_id]:
        queue_data[business_id][today] = []
    
    # Find the next token number
    if queue_data[business_id][today]:
        last_token = max(token['id'] for token in queue_data[business_id][today])
        token_id = last_token + 1
    else:
        token_id = 1
    
    return token_id

# Routes
@app.route('/')
def home():
    return redirect('/login')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        users = load_users()
        data = request.form.to_dict()
        
        # Check if mobile already registered
        if any(user['mobile'] == data['mobile'] for user in users):
            return render_template('signup_form.html', error="Mobile number already registered. Please log in.")
        
        # Hash password before storing
        data['password'] = generate_password_hash(data['password'])
        data['business_id'] = str(uuid.uuid4())  # Generate unique business ID
        
        users.append(data)
        save_users(users)
        return redirect('/login')
    
    return render_template('signup_form.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Login route accessed")
    if request.method == 'POST':
        print("Login attempt")
        print("Form data:", request.form)
        users = load_users()
        data = request.form
        
        # Find user in database
        user = next((u for u in users if u['mobile'] == data['mobile']), None)
        if user and check_password_hash(user['password'], data['password']):
            # Set session variables
            session['user_id'] = user['mobile']
            session['business_id'] = user['business_id']
            session['role'] = user.get('role', 'professional')
            
            print("User authenticated:", session['user_id'])
            print("Business ID:", session['business_id'])
            
            print("Redirecting to:", f"/{session['role']}_dashboard?business_id={session['business_id']}")
            return redirect(url_for(f"{session['role']}_dashboard", business_id=session['business_id']))
        
        # Show error message
        return render_template('login_form.html', error="Invalid credentials. Please try again.")
    
    return render_template('login_form.html')


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        mobile = request.form['mobile']
        print("Forgot password request for mobile:", mobile)
        users = load_users()
        
        # Check if mobile exists
        if any(user['mobile'] == mobile for user in users):
            # Generate reset token (in real app, send via SMS/email)
            reset_token = str(uuid.uuid4())
            expires = (datetime.now() + timedelta(hours=1)).isoformat()
            
            # Save reset token
            resets = load_password_resets()
            resets.append({
                'mobile': mobile,
                'token': reset_token,
                'expires': expires
            })
            save_password_resets(resets)
            
            # Show reset token to user (in production, send via SMS/email)
            return render_template('reset_password.html', mobile=mobile, token=reset_token)
        
        return render_template('forgot_password.html', error="Mobile number not found")
    
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        mobile = request.form['mobile']
        token = request.form['token']
        new_password = request.form['password']
        
        # Validate token
        resets = load_password_resets()
        valid_reset = None
        
        for reset in resets:
            if reset['mobile'] == mobile and reset['token'] == token:
                if datetime.fromisoformat(reset['expires']) > datetime.now():
                    valid_reset = reset
                break
        
        if valid_reset:
            # Update password
            users = load_users()
            for user in users:
                if user['mobile'] == mobile:
                    user['password'] = generate_password_hash(new_password)
                    save_users(users)
                    
                    # Remove used reset token
                    resets.remove(valid_reset)
                    save_password_resets(resets)
                    
                    return redirect('/login')
        
        return render_template('reset_password.html', error="Invalid or expired reset token")
    
    return render_template('reset_password.html')

@app.route('/customer_dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html')

@app.route('/professional_dashboard')
def professional_dashboard():
    if 'business_id' not in session:
        return redirect('/login')
    return render_template('professional_dashboard.html', business_id=session['business_id'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# API to get queue data for a business
@app.route('/api/queue')
def get_queue():    
    business_id = request.args.get('business_id')
    if not business_id:
        print("Business ID not provided")
        print("Full URL:", request.url)
        print("Args:", request.args)
        return jsonify({"error": "Business ID required"}), 400
    
    queue_data = load_queue()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Return today's queue for the business
    if business_id in queue_data and today in queue_data[business_id]:
        return jsonify(queue_data[business_id][today])
    
    return jsonify([])

# API to add new customer in queue
@app.route('/api/queue/add', methods=['POST'])
def add_to_queue():
    data = request.get_json()
    business_id = request.args.get('business_id')    
    if not business_id:
        return jsonify({"error": "Business ID required"}), 400
    
    # Generate token ID
    token_id = generate_token_id(business_id)
    
    # Add to queue
    queue_data = load_queue()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if business_id not in queue_data:
        queue_data[business_id] = {} 
    
    if today not in queue_data[business_id]:
        queue_data[business_id][today] = []
    
    customer_data = {
        'id': token_id,
        'name': data['name'],
        'phone': data['phone'],
        'service': data['service'],
        'status': 'waiting',
        'timestamp': datetime.now().isoformat()
    }
    
    queue_data[business_id][today].append(customer_data)
    save_queue(queue_data)
    
    return jsonify({"success": True, "id": token_id}), 201

# API to update queue token (mark complete or skip)
@app.route('/api/queue/update', methods=['POST'])
def update_queue():
    data = request.get_json()
    business_id = request.args.get('business_id')
    
    if not business_id:
        return jsonify({"error": "Business ID required"}), 400
    
    queue_data = load_queue()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if business_id in queue_data and today in queue_data[business_id]:
        for customer in queue_data[business_id][today]:
            if customer['id'] == data['id']:
                customer['status'] = data['status']
                break
        save_queue(queue_data)
        return jsonify(success=True)
    
    return jsonify({"error": "Customer not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)