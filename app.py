from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os

app = Flask(__name__)

USER_DB = "db/users.json"
QUEUE_DB = "db/queue.json"

# Ensure data files exist
os.makedirs("db", exist_ok=True)
if not os.path.exists(USER_DB):
    with open(USER_DB, "w") as f:
        json.dump([], f)
if not os.path.exists(QUEUE_DB):
    with open(QUEUE_DB, "w") as f:
        json.dump([], f)

# Load & save functions
def load_users():
    with open(USER_DB) as f:
        return json.load(f)

def save_users(data):
    with open(USER_DB, "w") as f:
        json.dump(data, f, indent=2)

def load_queue():
    with open(QUEUE_DB) as f:
        return json.load(f)

def save_queue(data):
    with open(QUEUE_DB, "w") as f:
        json.dump(data, f, indent=2)

# Routes
@app.route('/')
def home():
    return redirect('/signup')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        users = load_users()
        user = request.form.to_dict()
        users.append(user)
        save_users(users)
        return redirect('/login')
    return render_template('signup_form.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        data = request.form
        for user in users:
            if user['mobile'] == data['mobile'] and user['password'] == data['password']:
                role = user.get('role', 'customer')
                return redirect(url_for(f"{role}_dashboard"))
        return "Invalid credentials", 401
    return render_template('login_form.html')

@app.route('/customer_dashboard')
def customer_dashboard():
    return render_template('customer_dashboard.html')

@app.route('/professional_dashboard')
def professional_dashboard():
    return render_template('professional_dashboard.html')

# API to get queue data
@app.route('/api/queue')
def get_queue():
    return jsonify(load_queue())

# API to add new customer in queue
@app.route('/api/queue/add', methods=['POST'])
def add_to_queue():
    queue = load_queue()
    data = request.get_json()
    data['id'] = queue[-1]['id'] + 1 if queue else 1
    data['status'] = 'waiting'
    queue.append(data)
    save_queue(queue)
    return jsonify({"success": True, "id": data['id']}), 201

# API to update queue token (mark complete or skip)
@app.route('/api/queue/update', methods=['POST'])
def update_queue():
    queue = load_queue()
    data = request.get_json()
    for customer in queue:
        if customer['id'] == data['id']:
            customer['status'] = data['status']
            break
    save_queue(queue)
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True)
