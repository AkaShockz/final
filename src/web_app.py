from flask import Flask, render_template_string, request, send_file, redirect, url_for, session, abort, flash
import io
import csv
from datetime import datetime, timedelta
import os
import sys
import pandas as pd
import holidays
import json
import bcrypt
from functools import wraps
import re
from werkzeug.security import generate_password_hash, check_password_hash

# Import parser classes
sys.path.append(os.path.dirname(__file__))
from job_parser_core import JobParser, BC04Parser

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB upload limit

# Delivery date calculation logic
uk_holidays = holidays.UK()

HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'job_history.json')
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
SECRET_KEY = 'REPLACE_THIS_WITH_A_RANDOM_SECRET_KEY'
app.secret_key = SECRET_KEY

def load_job_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_job_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session or not session.get('username') or not users.get(session['username'], {}).get('enabled', False):
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated

job_history = load_job_history()
users = load_users()

# Ensure at least one user exists
if not users:
    # Create a default user
    users = {
        'bradlakin1': {
            'password': hash_password('301103'),
            'enabled': True
        }
    }
    save_users(users)

def calculate_delivery_date_ac01(collection_date_str):
    collection_date = datetime.strptime(collection_date_str, "%d/%m/%Y")
    current_date = collection_date
    business_days = 0
    while business_days < 3:
        current_date += timedelta(days=1)
        if current_date.weekday() < 5 and current_date not in uk_holidays:
            business_days += 1
    return current_date.strftime("%d/%m/%Y")

def calculate_delivery_date_bc04(collection_date_str):
    collection_date = datetime.strptime(collection_date_str, "%d/%m/%Y")
    delivery = collection_date + timedelta(days=1)
    while delivery.weekday() >= 5 or delivery in uk_holidays:
        delivery += timedelta(days=1)
    return delivery.strftime("%d/%m/%Y")

TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Intertechnic Jobs</title>
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background: linear-gradient(120deg, #f5f7fa 0%, #e0f2e9 100%);
            margin: 0;
            padding: 0;
        }
        .header-bar {
            background: #1b6e3a;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 92px;
            box-shadow: 0 2px 12px #0002;
            padding: 0;
            position: relative;
            z-index: 10;
        }
        .header-content {
            display: flex;
            align-items: center;
            gap: 14px;
            padding: 0 0 0 0;
        }
        .admin-link {
            position: absolute;
            right: 36px;
            top: 50%;
            transform: translateY(-50%);
            color: #fff;
            background: #388f2a;
            padding: 8px 18px;
            border-radius: 7px;
            font-size: 1.08em;
            font-weight: 600;
            text-decoration: none;
            box-shadow: 0 2px 8px #1b6e3a22;
            transition: background 0.2s;
        }
        .admin-link:hover {
            background: #1b6e3a;
        }
        .logo-blend {
            background: rgba(255,255,255,0.7);
            border-radius: 10px;
            box-shadow: 0 1px 4px #1b6e3a11;
            padding: 3px 10px 3px 10px;
            display: flex;
            align-items: center;
            height: 44px;
        }
        .logo {
            height: 32px;
            width: auto;
            display: block;
        }
        .header-title {
            font-size: 2.1em;
            font-weight: 700;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            height: 44px;
            margin-left: 0;
        }
        .header-divider {
            position: absolute;
            left: 0; right: 0; bottom: 0;
            height: 4px;
            background: linear-gradient(90deg, #1b6e3a 0%, #4e6ed6 100%);
            opacity: 0.12;
        }
        .container {
            max-width: 700px;
            margin: 48px auto 0 auto;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 8px 32px #1b6e3a22;
            padding: 0;
            overflow: hidden;
        }
        .accent-bar {
            height: 8px;
            background: linear-gradient(90deg, #1b6e3a 0%, #4e6ed6 100%);
        }
        .form-card {
            background: linear-gradient(120deg, #f7faff 60%, #e9ecf3 100%);
            padding: 48px 40px 36px 40px;
            border-radius: 0 0 18px 18px;
            box-shadow: 0 2px 12px #1b6e3a11;
        }
        .section-title {
            display: flex;
            align-items: center;
            font-size: 2.3em;
            font-weight: 700;
            color: #1b6e3a;
            margin-bottom: 16px;
            letter-spacing: 0.5px;
        }
        .section-icon {
            background: #1b6e3a;
            color: #fff;
            border-radius: 50%;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.7em;
            margin-right: 20px;
            box-shadow: 0 2px 8px #1b6e3a22;
        }
        label {
            font-weight: 600;
            display: block;
            margin-top: 18px;
            margin-bottom: 6px;
        }
        .helper {
            color: #6b7ba3;
            font-size: 0.98em;
            margin-bottom: 8px;
            margin-top: -2px;
        }
        select, textarea, input[type="text"] {
            width: 100%;
            padding: 12px;
            margin-top: 0;
            border-radius: 7px;
            border: 1.5px solid #bfc7d1;
            font-size: 1.08em;
            background: #f7f9fc;
            transition: border 0.2s;
        }
        select:focus, textarea:focus, input[type="text"]:focus {
            border: 2px solid #1b6e3a;
            outline: none;
            background: #fff;
        }
        textarea {
            min-height: 160px;
            font-family: 'Consolas', 'Menlo', monospace;
            resize: vertical;
        }
        .date-fields-card {
            background: #f7f9fc;
            border: 1.5px solid #bfc7d1;
            border-radius: 10px;
            box-shadow: 0 2px 8px #1b6e3a11;
            padding: 24px 24px 10px 24px;
            margin: 28px 0 18px 0;
        }
        .date-labels {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
            align-items: start;
            margin-bottom: 0;
        }
        .date-labels > div {
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        .date-labels label {
            margin-bottom: 4px;
        }
        .date-labels input[type="text"] {
            width: 100%;
            box-sizing: border-box;
            min-height: 44px;
            margin-bottom: 0;
            font-size: 1.08em;
        }
        @media (max-width: 700px) {
            .date-labels {
                grid-template-columns: 1fr;
                gap: 0;
            }
            .date-labels > div {
                margin-bottom: 18px;
            }
        }
        .btn {
            background: linear-gradient(90deg, #1b6e3a 60%, #388f2a 100%);
            color: #fff;
            border: none;
            padding: 20px 0;
            border-radius: 8px;
            font-size: 1.25em;
            margin-top: 32px;
            width: 100%;
            cursor: pointer;
            font-weight: 700;
            box-shadow: 0 4px 16px #1b6e3a22;
            transition: background 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            background: linear-gradient(90deg, #388f2a 60%, #1b6e3a 100%);
            box-shadow: 0 8px 24px #1b6e3a33;
        }
        .btn:disabled {
            background: #bfc7d1;
            color: #fff;
            cursor: not-allowed;
        }
        .divider {
            border: none;
            border-top: 2px solid #e0e4ef;
            margin: 36px 0 18px 0;
        }
        .job-count {
            color: #1b6e3a;
            font-size: 1.08em;
            font-weight: 600;
            margin-top: 8px;
            margin-bottom: 0;
            text-align: right;
        }
        .error {
            color: #d00;
            margin-top: 16px;
            font-weight: 500;
        }
        .debug {
            color: #888;
            font-size: 0.97em;
            margin-top: 12px;
            background: #f7f7f7;
            padding: 10px;
            border-radius: 6px;
        }
        .footer {
            text-align: center;
            color: #bfc7d1;
            margin-top: 60px;
            font-size: 1em;
            letter-spacing: 0.5px;
        }
        .history-section {
            margin: 48px auto 0 auto;
            max-width: 700px;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 8px 32px #1b6e3a22;
            padding: 32px 40px 32px 40px;
        }
        .history-title {
            font-size: 1.5em;
            font-weight: 700;
            color: #1b6e3a;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
        }
        .history-icon {
            background: #1b6e3a;
            color: #fff;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1em;
            margin-right: 12px;
        }
        .history-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        .history-table th, .history-table td {
            border: 1px solid #e0e4ef;
            padding: 10px 12px;
            text-align: left;
        }
        .history-table th {
            background: #f5f7fa;
            color: #1b6e3a;
            font-weight: 600;
        }
        .history-table tr:nth-child(even) {
            background: #f7f9fc;
        }
        .history-table tr:hover {
            background: #e0f2e9;
            transition: background 0.2s;
        }
        .info-box {
            background: #eaf6ff;
            border-left: 5px solid #1b6e3a;
            color: #1b6e3a;
            padding: 14px 18px;
            margin-bottom: 18px;
            border-radius: 7px;
            font-size: 1.05em;
        }
    </style>
    <script>
    function autoSetDeliveryDate() {
        var jobType = document.getElementById('job_type').value;
        var collection = document.getElementById('collection_date').value;
        var delivery = document.getElementById('delivery_date');
        if (jobType === 'AC01' || jobType === 'BC04') {
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/auto_delivery_date', true);
            xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
            xhr.onreadystatechange = function() {
                if (xhr.readyState === 4 && xhr.status === 200) {
                    delivery.value = xhr.responseText;
                }
            };
            xhr.send('job_type=' + encodeURIComponent(jobType) + '&collection_date=' + encodeURIComponent(collection));
        }
    }
    function updateJobCount() {
        var textarea = document.getElementById('job_data');
        var jobType = document.getElementById('job_type').value;
        var count = 0;
        if (textarea && (jobType === 'AC01' || jobType === 'EU01' || jobType === 'BC04')) {
            var text = textarea.value;
            // Count jobs by counting 'FROM' at the start of a line
            var matches = text.match(/^FROM/mg);
            if (matches) count = matches.length;
        }
        document.getElementById('job_count').innerText = count + (count === 1 ? ' job found' : ' jobs found');
    }
    window.onload = function() {
        var textarea = document.getElementById('job_data');
        if (textarea) {
            textarea.addEventListener('input', updateJobCount);
            updateJobCount();
        }
    };
    </script>
</head>
<body>
    <div class="header-bar">
        <div class="header-content">
            <span class="logo-blend">
                <img src="{{ url_for('static', filename='intertechnic_logo.gif') }}" class="logo" alt="Intertechnic Logo" onerror="this.onerror=null;this.src='https://via.placeholder.com/180x54?text=Logo+Missing';">
            </span>
            <div class="header-title">Intertechnic Jobs</div>
        </div>
        {% if username in ['admin', 'bradlakin1'] %}
        <a href="/admin" class="admin-link">Admin</a>
        {% endif %}
        <div class="header-divider"></div>
    </div>
    <div class="container">
        <div class="accent-bar"></div>
        <div class="form-card">
            <div class="section-title">
                <span class="section-icon">📄</span>
                Job Submission
            </div>
            <form method="POST" enctype="multipart/form-data">
                <label for="job_type">Job Type:</label>
                <div class="helper">Select the type of job you want to process.</div>
                <select name="job_type" id="job_type" onchange="this.form.submit()">
                    <option value="AC01" {% if job_type == 'AC01' %}selected{% endif %}>AC01</option>
                    <option value="BC04" {% if job_type == 'BC04' %}selected{% endif %}>BC04</option>
                    <option value="GR11" {% if job_type == 'GR11' %}selected{% endif %}>GR11</option>
                    <option value="CW09" {% if job_type == 'CW09' %}selected{% endif %}>CW09</option>
                    <option value="EU01" {% if job_type == 'EU01' %}selected{% endif %}>EU01</option>
                </select>

                {% if job_type == 'AC01' %}
                <div class="info-box">
                    <b>Note on AC01 Parsing Accuracy:</b><br>
                    The AC01 parser is highly accurate (99%) and requires release codes to function correctly. In rare cases, it may confuse address fields and place the town name twice (for example, 'St. Margarets Way' could be replaced with 'LEICESTER'). This is usually easy to spot, as the phone number will appear as a placeholder (e.g., 500000000000) if the address is not parsed correctly. Please double-check the output for these rare cases.
                </div>
                {% endif %}

                {% if job_type == 'BC04' %}
                <div class="info-box">
                    <b>Note on BC04 Parsing Accuracy:</b><br>
                    The BC04 parser is approximately 80% accurate, requires release codes, and is still under active development. Please review the output carefully.
                </div>
                {% endif %}

                {% if job_type == 'EU01' %}
                <div class="info-box">
                    <b>EU01 Parsing:</b><br>
                    EU01 parsing is coming soon and is not yet available.
                </div>
                {% endif %}

                {% if job_type == 'CW09' %}
                <div class="info-box">
                    <b>Note on CW09 Parsing Accuracy:</b><br>
                    The CW09 parser is approximately 80% accurate and has not been fully developed yet. Use with caution.
                </div>
                {% endif %}

                {% if job_type in ['AC01', 'BC04', 'EU01'] %}
                    <label for="job_data">Paste Job Data:</label>
                    <div class="helper">Paste the job text exactly as provided by your source.</div>
                    <textarea name="job_data" id="job_data">{{ job_data|default('') }}</textarea>
                    <div class="job-count" id="job_count">0 jobs found</div>
                {% endif %}

                {% if job_type in ['GR11', 'CW09'] %}
                    <label>Upload Excel/CSV (for GR11/CW09):</label>
                    <div class="helper">Upload the Excel or CSV file for this job type.</div>
                    <input type="file" name="file">
                {% endif %}

                <div class="date-fields-card">
                    <div class="date-labels">
                        <div>
                            <label for="collection_date">Collection Date (DD/MM/YYYY):</label>
                            <input type="text" name="collection_date" id="collection_date" value="{{ collection_date|default('') }}" oninput="autoSetDeliveryDate()">
                        </div>
                        <div>
                            <label for="delivery_date">Delivery Date (DD/MM/YYYY):</label>
                            <input type="text" name="delivery_date" id="delivery_date" value="{{ delivery_date|default('') }}">
                        </div>
                    </div>
                </div>
                <button class="btn" type="submit">Process Jobs</button>
                <hr class="divider">
                {% if error %}
                    <div class="error">{{ error }}</div>
                {% endif %}
                {% if debug %}
                    <div class="debug">{{ debug|safe }}</div>
                {% endif %}
            </form>
        </div>
    </div>
    <div class="history-section">
        <div class="history-title"><span class="history-icon">📊</span>Job History</div>
        <table class="history-table">
            <tr><th>Timestamp</th><th>Job Type</th><th>CSV File</th><th>User</th></tr>
            {% for row in job_history %}
            <tr>
                <td>{{ row.timestamp }}</td>
                <td>{{ row.job_type }}</td>
                <td><a href="{{ url_for('protected_history_file', filename=row.csv_path.split('/')[-1]) }}" target="_blank">Download</a></td>
                <td>{{ row.user or 'N/A' }}</td>
            </tr>
            {% endfor %}
            {% if not job_history %}
            <tr><td colspan="4" style="text-align:center; color:#aaa;">No jobs processed yet.</td></tr>
            {% endif %}
        </table>
    </div>
    <div class="footer">&copy; 2024 Intertechnic Jobs &mdash; All rights reserved</div>
</body>
</html>
'''

def normalize_line_endings(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')

@app.route('/auto_delivery_date', methods=['POST'])
def auto_delivery_date():
    job_type = request.form.get('job_type')
    collection_date = request.form.get('collection_date')
    if not collection_date:
        return ''
    if job_type == 'AC01':
        return calculate_delivery_date_ac01(collection_date)
    elif job_type == 'BC04':
        return calculate_delivery_date_bc04(collection_date)
    else:
        return collection_date

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = users.get(username)
        if user and user.get('enabled', False) and check_password(password, user['password']):
            session['username'] = username
            return redirect(url_for('index'))
        error = 'Invalid credentials or account disabled.'
    return render_template_string('''
    <html><head><title>Login</title><style>body{background:#e0f2e9;font-family:sans-serif;} .login-box{background:#fff;max-width:400px;margin:80px auto;padding:40px 32px 32px 32px;border-radius:14px;box-shadow:0 4px 24px #1b6e3a22;} h2{color:#1b6e3a;} label{font-weight:600;} input{width:100%;padding:12px;margin:8px 0 18px 0;border-radius:7px;border:1.5px solid #bfc7d1;font-size:1.08em;} button{background:#1b6e3a;color:#fff;border:none;padding:14px 0;border-radius:8px;font-size:1.1em;width:100%;font-weight:700;box-shadow:0 2px 8px #1b6e3a22;} .error{color:#d00;margin-bottom:12px;}</style></head><body><div class="login-box"><h2>Login</h2>{% if error %}<div class="error">{{ error }}</div>{% endif %}<form method="POST"><label>Username:</label><input name="username" required><label>Password:</label><input name="password" type="password" required><button type="submit">Login</button></form></div></body></html>
    ''', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/history/<path:filename>')
@login_required
def protected_history_file(filename):
    static_history_dir = os.path.join(os.path.dirname(__file__), 'static', 'history')
    file_path = os.path.join(static_history_dir, filename)
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    global job_history
    error = None
    debug = None
    job_type = request.form.get('job_type', 'AC01')
    job_data = request.form.get('job_data', '')
    collection_date = request.form.get('collection_date', datetime.now().strftime('%d/%m/%Y'))
    delivery_date = request.form.get('delivery_date', '')

    # Auto-set delivery date if not provided
    if not delivery_date:
        if job_type == 'AC01':
            delivery_date = calculate_delivery_date_ac01(collection_date)
        elif job_type == 'BC04':
            delivery_date = calculate_delivery_date_bc04(collection_date)
        else:
            delivery_date = collection_date

    if request.method == 'POST':
        if job_type in ['AC01', 'BC04', 'EU01']:
            job_data_norm = normalize_line_endings(job_data)
            if job_type == 'AC01' or job_type == 'EU01':
                parser = JobParser(collection_date, delivery_date)
            elif job_type == 'BC04':
                parser = BC04Parser(collection_date, delivery_date)
            else:
                parser = None
            jobs = parser.parse_jobs(job_data_norm) if parser else []
            if not jobs:
                debug = f"<b>Debug:</b><br>Input preview (first 500 chars):<br><pre>{job_data_norm[:500]}</pre><br>Jobs found: 0"
                error = "No valid jobs found. Please check your input format."
            else:
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=jobs[0].keys())
                writer.writeheader()
                writer.writerows(jobs)
                output.seek(0)
                # Save CSV to static/history with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                csv_filename = f"history_{job_type}_{timestamp}.csv"
                static_history_dir = os.path.join(os.path.dirname(__file__), 'static', 'history')
                os.makedirs(static_history_dir, exist_ok=True)
                csv_path = os.path.join(static_history_dir, csv_filename)
                with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(output.getvalue())
                # Add to job history (user is placeholder for now)
                job_history.insert(0, {
                    'timestamp': timestamp,
                    'job_type': job_type,
                    'csv_path': f'history/{csv_filename}',
                    'user': None
                })
                save_job_history(job_history)
                return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'{job_type}_jobs_{timestamp}.csv')
        elif job_type in ['GR11', 'CW09']:
            file = request.files.get('file')
            if not file:
                error = "Please upload an Excel or CSV file."
            else:
                try:
                    df = pd.read_excel(file) if file.filename.endswith('.xlsx') else pd.read_csv(file)
                    # Find columns case-insensitively
                    colmap = {}
                    for col in df.columns:
                        cl = col.strip().lower()
                        if cl in ['reg no', 'reg number', 'registration', 'reg']: colmap['reg'] = col
                        elif cl in ['pdi centre', 'pdi', 'pdi_center']: colmap['pdi'] = col
                        elif cl in ['model']: colmap['model'] = col
                        elif cl in ['chassis', 'vin']: colmap['chassis'] = col
                        elif cl in ['delivery due date', 'delivery date', 'del date']: colmap['date'] = col
                        elif cl in ['delivery address', 'address', 'delivery addr']: colmap['address'] = col
                        elif cl in ['price']: colmap['price'] = col
                        elif cl in ['special instructions', 'special']: colmap['special'] = col
                    jobs = []
                    makes = ["FORD", "VAUXHALL", "VOLKSWAGEN", "VW", "BMW", "MERCEDES", "AUDI", "TOYOTA", "HONDA", "NISSAN", "HYUNDAI", "KIA", "SKODA", "SEAT", "RENAULT", "PEUGEOT", "CITROEN", "FIAT", "MAZDA", "VOLVO"]
                    for _, row in df.iterrows():
                        reg = str(row.get(colmap.get('reg',''), '')).strip()
                        if not reg: continue
                        vin = str(row.get(colmap.get('chassis',''), '')).strip()
                        model = str(row.get(colmap.get('model',''), '')).strip()
                        make = ''
                        m_model = model
                        for m in makes:
                            if m.lower() in model.lower():
                                make = m
                                if model.lower().startswith(m.lower()):
                                    m_model = model[len(m):].strip()
                                break
                        pdi_centre = str(row.get(colmap.get('pdi',''), '')).upper() if colmap.get('pdi') else ''
                        if 'UPPER' in pdi_centre or 'HEYFORD' in pdi_centre:
                            customer_ref = 'GR15'
                            collection_addr1 = 'Greenhous Upper Heyford'
                            collection_addr2 = 'Heyford Park, Bicester'
                            collection_addr3 = 'Bicester'
                            collection_addr4 = 'UPPER HEYFORD'
                            collection_postcode = 'OX25 5HA'
                        else:
                            customer_ref = 'GR11'
                            collection_addr1 = 'Greenhous High Ercall'
                            collection_addr2 = 'Greenhous Village Osbaston'
                            collection_addr3 = 'High Ercall'
                            collection_addr4 = ''
                            collection_postcode = 'TF6 6RA'
                        your_ref = reg
                        delivery_date = str(row.get(colmap.get('date',''), '')).strip()
                        delivery_addr = str(row.get(colmap.get('address',''), '')).strip()
                        # Split delivery address into ADDR1-4 and POSTCODE
                        addr1 = addr2 = addr3 = addr4 = dpostcode = ''
                        if delivery_addr:
                            address_parts = [a.strip() for a in re.split(r',|\n', delivery_addr) if a.strip()]
                            if address_parts:
                                addr1 = address_parts[0]
                                addr2 = address_parts[1] if len(address_parts) > 1 else ''
                                addr3 = address_parts[2] if len(address_parts) > 2 else ''
                                addr4 = address_parts[3] if len(address_parts) > 3 else ''
                                # Try to find postcode in any part
                                postcode_pattern = r'\b([A-Z]{1,2}\d{1,2}[A-Z]? ?\d[A-Z]{2})\b'
                                for i, part in enumerate(address_parts):
                                    m = re.search(postcode_pattern, part.upper())
                                    if m:
                                        dpostcode = m.group(1)
                                        # Remove postcode from addr part
                                        address_parts[i] = address_parts[i].replace(dpostcode, '').strip()
                                        break
                        special_instructions = str(row.get(colmap.get('special',''), '')).strip()
                        price = str(row.get(colmap.get('price',''), '')).strip()
                        special_instructions = f"VIN: {vin} " + special_instructions if special_instructions else f"VIN: {vin}"
                        jobs.append({
                            'REG NUMBER': reg,
                            'VIN': vin,
                            'MAKE': make,
                            'MODEL': m_model,
                            'COLLECTION ADDR1': collection_addr1,
                            'COLLECTION ADDR2': collection_addr2,
                            'COLLECTION ADDR3': collection_addr3,
                            'COLLECTION ADDR4': collection_addr4,
                            'COLLECTION POSTCODE': collection_postcode,
                            'YOUR REF NO': your_ref,
                            'DELIVERY ADDR1': addr1,
                            'DELIVERY ADDR2': addr2,
                            'DELIVERY ADDR3': addr3,
                            'DELIVERY ADDR4': addr4,
                            'DELIVERY POSTCODE': dpostcode,
                            'SPECIAL INSTRUCTIONS': special_instructions,
                            'PRICE': price,
                            'CUSTOMER REF': 'GR11/GR15',
                            'TRANSPORT TYPE': ''
                        })
                    if not jobs:
                        error = "No valid jobs found in the file."
                    else:
                        output = io.StringIO()
                        fieldnames = [
                            'REG NUMBER', 'VIN', 'MAKE', 'MODEL',
                            'COLLECTION DATE', 'YOUR REF NO',
                            'COLLECTION ADDR1', 'COLLECTION ADDR2', 'COLLECTION ADDR3', 'COLLECTION ADDR4', 'COLLECTION POSTCODE',
                            'DELIVERY DATE',
                            'DELIVERY ADDR1', 'DELIVERY ADDR2', 'DELIVERY ADDR3', 'DELIVERY ADDR4', 'DELIVERY POSTCODE',
                            'SPECIAL INSTRUCTIONS', 'PRICE', 'CUSTOMER REF', 'TRANSPORT TYPE'
                        ]
                        writer = csv.DictWriter(output, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(jobs)
                        output.seek(0)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        csv_filename = f"history_{job_type}_{timestamp}.csv"
                        static_history_dir = os.path.join(os.path.dirname(__file__), 'static', 'history')
                        os.makedirs(static_history_dir, exist_ok=True)
                        csv_path = os.path.join(static_history_dir, csv_filename)
                        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                            f.write(output.getvalue())
                        job_history.insert(0, {
                            'timestamp': timestamp,
                            'job_type': job_type,
                            'csv_path': f'history/{csv_filename}',
                            'user': session.get('username')
                        })
                        save_job_history(job_history)
                        return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name=f'{job_type}_jobs_{timestamp}.csv')
                except Exception as e:
                    error = f"Failed to process file: {e}"
    # List all CSVs in static/history for job history
    static_history_dir = os.path.join(os.path.dirname(__file__), 'static', 'history')
    if os.path.exists(static_history_dir):
        files = sorted(os.listdir(static_history_dir), reverse=True)
        job_history = [row for row in job_history if os.path.exists(os.path.join(static_history_dir, row['csv_path'].split('/')[-1]))]
    else:
        files = []
    return render_template_string(TEMPLATE, job_type=job_type, job_data=job_data, collection_date=collection_date, delivery_date=delivery_date, error=error, debug=debug, job_history=job_history, username=session.get('username'))

def is_admin():
    return session.get('username') in ['admin', 'bradlakin1']

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if not is_admin():
        abort(403)
    msg = None
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username', '').strip()
        if action == 'add':
            password = request.form.get('password', '')
            if username in users:
                msg = f'User {username} already exists.'
            else:
                users[username] = {'password': hash_password(password), 'enabled': True}
                save_users(users)
                msg = f'User {username} added and enabled.'
        elif action == 'enable':
            if username in users:
                users[username]['enabled'] = True
                save_users(users)
                msg = f'User {username} enabled.'
        elif action == 'disable':
            if username in users:
                users[username]['enabled'] = False
                save_users(users)
                msg = f'User {username} disabled.'
        elif action == 'setpw':
            password = request.form.get('password', '')
            if username in users:
                users[username]['password'] = hash_password(password)
                save_users(users)
                msg = f'Password updated for {username}.'
    return render_template_string('''
    <html><head><title>Admin Panel</title><style>body{background:#e0f2e9;font-family:sans-serif;} .admin-box{background:#fff;max-width:600px;margin:40px auto;padding:40px 32px 32px 32px;border-radius:14px;box-shadow:0 4px 24px #1b6e3a22;} h2{color:#1b6e3a;} table{width:100%;border-collapse:collapse;margin-bottom:24px;} th,td{border:1px solid #bfc7d1;padding:8px 10px;} th{background:#f5f7fa;} tr:nth-child(even){background:#f7f9fc;} .btn{background:#1b6e3a;color:#fff;border:none;padding:6px 16px;border-radius:6px;font-size:1em;font-weight:600;margin:0 2px;} .btn:disabled{background:#bfc7d1;} .msg{color:#1b6e3a;margin-bottom:12px;font-weight:600;} .form-row{margin-bottom:18px;} label{font-weight:600;}</style></head><body><div class="admin-box"><h2>User Management</h2>{% if msg %}<div class="msg">{{ msg }}</div>{% endif %}<table><tr><th>Username</th><th>Status</th><th>Actions</th></tr>{% for u, v in users.items() %}<tr><td>{{ u }}</td><td>{{ 'ENABLED' if v.enabled else 'DISABLED' }}</td><td><form method="post" style="display:inline"><input type="hidden" name="username" value="{{ u }}"><button class="btn" name="action" value="enable" {% if v.enabled %}disabled{% endif %}>Enable</button><button class="btn" name="action" value="disable" {% if not v.enabled %}disabled{% endif %}>Disable</button></form><form method="post" style="display:inline"><input type="hidden" name="username" value="{{ u }}"><input type="text" name="password" placeholder="New password" required style="width:110px;"><button class="btn" name="action" value="setpw">Set Password</button></form></td></tr>{% endfor %}</table><h3>Add New User</h3><form method="post"><div class="form-row"><label>Username:</label><input name="username" required></div><div class="form-row"><label>Password:</label><input name="password" type="password" required></div><button class="btn" name="action" value="add">Add User</button></form><div style="margin-top:24px;"><a href="/">Back to main</a></div></div></body></html>
    ''', users={u: type('obj', (), v) for u, v in users.items()}, msg=msg)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_file(os.path.join(os.path.dirname(__file__), 'static', filename))

if __name__ == '__main__':
    app.run(debug=True)