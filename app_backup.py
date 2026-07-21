from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for, session, flash, Response
import json
import requests
import re
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "mysecretkey123")

app.config['PROPAGATE_EXCEPTIONS'] = True

# 🔗 Backend API
BASE_URL = os.getenv("BACKEND_URL", "http://192.168.1.159:5001")

#Role based access
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'role' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash("Access denied", "danger")
                return redirect(url_for('dashboard'))
            import inspect
            sig = inspect.signature(f)
            if 'current_user' in sig.parameters:
                # Create current_user object to pass to the function
                current_user = {
                    'user_id': session.get('user_id'),
                    'username': session.get('username'),
                    'role': session.get('role'),
                    'employee_name': session.get('employee_name')
                }
                return f(current_user, *args, **kwargs)
            else:
                # Function doesn't expect current_user, call normally
                return f(*args, **kwargs)
        return wrapper
    return decorator

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'token' not in session:
            return redirect(url_for('login'))
        import inspect
        sig = inspect.signature(f)
        if 'current_user' in sig.parameters:
            current_user = {
                'user_id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role'),
                'employee_name': session.get('employee_name')
            }
            return f(current_user, *args, **kwargs)
        return f(*args, **kwargs)
    return decorated




#Helper function
def get_headers(exclude_content_type=False):
    token = session.get('token')
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if not exclude_content_type:
        headers["Content-Type"] = "application/json"
    
    return headers


def fetch_leave_balance_helper(employee_name):
    """
    Helper to fetch leave balance with fallback for potential name prefixes.
    """
    if not employee_name:
        return None
    
    try:
        # First try with the full name
        res = requests.get(f"{BASE_URL}/leave-balance/{employee_name}", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return res.json()
        
        # If it failed, try fallback (removing potential prefix like "01 ")
        if len(employee_name) > 2:
            # Try removing prefix and strip whitespace
            clean_name = employee_name[2:].strip()
            res2 = requests.get(f"{BASE_URL}/leave-balance/{clean_name}", headers=get_headers(), timeout=10)
            if res2.status_code == 200:
                return res2.json()
    except Exception as e:
        print(f"Error fetching leave balance for {employee_name}: {e}")
    return None


#Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any existing flash messages at the start of login
    session.pop('_flashes', None)
    
    if request.method == 'POST':
        payload = {
            "username": request.form.get("username"),
            "password": request.form.get("password")
        }
        try:
            res = requests.post(f"{BASE_URL}/auth/login", json=payload)
            data = res.json()
        except Exception as e:
            print("LOGIN ERROR:", e)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": "Server not reachable"}), 500
            flash("Server not reachable", "danger")
            return render_template('login.html')

        if res.status_code == 200 and data.get("success"):
            # Validate token exists
            if 'token' in data and data['token']:
                session['token'] = data['token']
                session['user'] = data['user']['username']
                session['role'] = data['user']['role']
                session['employee_name'] = data['user']['employee_name']
                session['employee_id'] = data['user'].get('id', 'N/A')

                # If AJAX, return status and flag
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({
                        "success": True, 
                        "password_change_required": data['user'].get("password_change_required", False)
                    })
                
                if data['user'].get('password_change_required'):
                    flash("Password change required. Please set a new password to continue.", "warning")
                    return redirect(url_for('change_password'))
                
                # Clear any existing flash messages before redirecting
                session.pop('_flashes', None)
                return redirect(url_for('dashboard'))

            else:
                print("ERROR: No token in response")
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "error": "Authentication failed - no token received"}), 401
                flash("Authentication failed - no token received", "danger")
                return redirect(url_for('login'))
        else:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": data.get("error", "Invalid login")}), 401
            flash(data.get("error", "Invalid login"), "danger")

    return render_template('login.html')


# Forgot Password - Render Form
@app.route('/forgot-password', methods=['GET'])
def forgot_password():
    return render_template('forgot_password.html')


# Forgot Password - API Handler
@app.route('/forgot-password', methods=['POST'])
def handle_forgot_password():
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        res = requests.post(
            f"{BASE_URL}/auth/forgot-password",
            json={'email': email},
            headers={'Content-Type': 'application/json'}
        )
        
        response_data = res.json()
        return jsonify(response_data), res.status_code
    except Exception as e:
        print("Forgot password error:", e)
        return jsonify({'success': False, 'error': 'Server error occurred'}), 500


# Reset Password - Render Form
@app.route('/reset-password', methods=['GET'])
def reset_password():
    token = request.args.get('token', '')
    return render_template('reset_password.html', token=token)


# Reset Password - API Handler
@app.route('/reset-password', methods=['POST'])
def handle_reset_password():
    try:
        data = request.get_json() or {}
        token = data.get('token', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        if not all([token, new_password, confirm_password]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
        
        # Password complexity validation
        if len(new_password) < 8 or not re.search(r"[A-Z]", new_password) or not re.search(r"[@$!%*?&]", new_password):
            return jsonify({'success': False, 'error': 'Password must be 8+ chars and include a capital and a special character'}), 400
        
        res = requests.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                'token': token,
                'new_password': new_password,
                'confirm_password': confirm_password
            },
            headers={'Content-Type': 'application/json'}
        )
        
        response_data = res.json()
        return jsonify(response_data), res.status_code
    except Exception as e:
        print("Reset password error:", e)
        return jsonify({'success': False, 'error': 'Server error occurred'}), 500


#  Home → show dashboard
@app.route('/')
def home():
    return redirect(url_for('login'))

#  Dashboard
@app.route('/dashboard')
def dashboard():
    if 'token' not in session:
        return redirect(url_for('login'))

    # 1. Initialize ALL variables to prevent UnboundLocalError
    birthday_data = []
    holidays = []
    stats = {"employees": 0, "timesheets": 0, "leaves": 0}
    hd_stats = {}
    reimbursement_stats = {}
    pending_agreements = []
    projects = []
    pending_timesheets_list = []
    pending_timesheets_count = 0
    team_pending_timesheets = []
    team_leaves = []
    timesheets = []
    leaves = []

    try:
        # 2. Core Stats & Data Fetching
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if emp_res.status_code == 401:
            session.clear()
            return redirect(url_for('login'))
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
        
        time_res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        timesheets = time_res.json().get("timesheets", []) if time_res.status_code == 200 else []
        
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leaves = leave_res.json().get("leaves", []) if leave_res.status_code == 200 else []
        
        # 3. Calculate Stats
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Pending timesheets for total employees in the current month
        pending_timesheets_month = []
        for t in timesheets:
            status = str(t.get('status', '')).lower()
            if status in ['submitted', 'pending']:
                try:
                    start_date_str = t.get('start_date', '')[:10]
                    dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                    if dt.month == current_month and dt.year == current_year:
                        pending_timesheets_month.append(t)
                except:
                    pass
        
        # Pending leaves
        pending_leaves = [l for l in leaves if str(l.get('status', '')).lower() == 'pending']
        
        stats = {
            "employees": len(employees),
            "timesheets": len(pending_timesheets_month),
            "leaves": len(pending_leaves)
        }

        # 4. Holidays & Birthdays
        holiday_res = requests.get(f"{BASE_URL}/holidays?year=2026", headers=get_headers())
        if holiday_res.status_code == 200:
            holidays = holiday_res.json().get("holidays", [])
            for h in holidays:
                raw_date = str(h.get("date", ""))
                try:
                    dt = datetime.strptime(raw_date[:10], "%Y-%m-%d") if "-" in raw_date else datetime.strptime(raw_date.strip(), "%a, %d %b")
                    h["formatted_date"] = dt.strftime("%d %b")
                except: h["formatted_date"] = raw_date

        bd_res = requests.get(f"{BASE_URL}/birthdays/dashboard", headers=get_headers())
        birthday_data = bd_res.json().get("today", {}).get("birthdays", []) if bd_res.status_code == 200 else []

        # 4. Role-Specific Data (HR/Admin)
        if session.get('role') in ['hr', 'admin']:
            try:
                hd_res = requests.get(f"{BASE_URL}/helpdesk/stats", headers=get_headers(), timeout=5)
                if hd_res.status_code == 200: hd_stats = hd_res.json()
            except: pass
            try:
                rb_res = requests.get(f"{BASE_URL}/reimbursement/stats", headers=get_headers(), timeout=5)
                if rb_res.status_code == 200: reimbursement_stats = rb_res.json()
            except: pass

        # 5. Role-Specific Data (Employee)
        if session.get('role') == 'employee':
            try:
                my_devices_res = requests.get(f"{BASE_URL}/devices/my-devices", headers=get_headers(), timeout=5)
                if my_devices_res.status_code == 200:
                    my_devices = my_devices_res.json().get('devices', [])
                    pending_agreements = [d for d in my_devices if d.get('acceptance_status') == 'pending']
            except: pass
            
            current_user = session.get('employee_name')
            pending_timesheets_list = [t for t in timesheets if t.get('employee_name') == current_user and str(t.get('status', '')).lower() in ['pending', 'missing', 'missing entry']]
            today_str = datetime.now().strftime('%Y-%m-%d')
            has_today_entry = any(t for t in timesheets if t.get('employee_name') == current_user and t.get('start_date', '')[:10] == today_str)
            pending_timesheets_count = len(pending_timesheets_list)
            if not has_today_entry:
                pending_timesheets_count += 1
                pending_timesheets_list.insert(0, {'project': 'Today\'s Entry', 'start_date': today_str, 'status': 'missing'})

        # 6. Role-Specific Data (Manager)
        if session.get('role') == 'manager':
            global projects_db
            manager_name = session.get('employee_name')
            if os.path.exists('projects.json'):
                with open('projects.json', 'r') as f:
                    projects_db = json.load(f)
                    projects = [proj for proj in projects_db if proj.get('assigned_manager') == manager_name and proj.get('status') == 'active']
            
            manager_project_names = [proj.get('name') for proj in projects]
            team_pending_timesheets = [t for t in timesheets if t.get('project') in manager_project_names and str(t.get('status', '')).lower() in ['pending', 'missing', 'missing entry']]
            
            team_member_names = set()
            for proj in projects:
                mems = proj.get('team_members')
                if isinstance(mems, list):
                    for m in mems: team_member_names.add(m if isinstance(m, str) else (m.get('name') or m.get('employee_name')))
                elif isinstance(mems, str):
                    team_member_names.update([m.strip() for m in mems.split(',') if m.strip()])
            
            team_leaves = [l for l in leaves if l.get('employee_name') in team_member_names and l.get('status', '').lower() in ['pending', 'approved']]
            team_leaves.sort(key=lambda x: x.get('start_date', ''), reverse=True)

    except Exception as e:
        print(f"Dashboard Exception: {e}")
        flash("Error loading some dashboard data", "warning")

    return render_template(
        'dashboard.html',
        stats=stats,
        holidays=holidays,
        birthdays=birthday_data,
        hd_stats=hd_stats,
        reimbursement_stats=reimbursement_stats,
        pending_agreements=pending_agreements,
        projects=projects,
        team_pending_timesheets=team_pending_timesheets,
        team_leaves=team_leaves[:10],
        pending_timesheets_count=pending_timesheets_count,
        pending_timesheets_list=pending_timesheets_list[:5],
        current_user=session.get('employee_name'),
        role=session.get('role')
    )


@app.context_processor
def inject_user():
    return dict(
        current_user=session.get('employee_name'),
        role=session.get('role'),
        # Sidebar profile photo — stored in session after login or upload
        sidebar_photo_url=session.get('photo_url')
    )


@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    # Check if user is authenticated
    if 'token' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        payload = {
            "new_password": request.form.get("new_password"),
            "confirm_password": request.form.get("confirm_password")
        }
        try:
            res = requests.post(f"{BASE_URL}/auth/change-password", json=payload, headers=get_headers())
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                # Update token with the new one from backend
                if data.get("token"):
                    session['token'] = data['token']
                flash("Password changed successfully!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash(data.get("error", "Failed to change password"), "danger")
        except Exception as e:
            print("Password change error:", e)
            flash("Server error occurred", "danger")
    return render_template('change_password.html')



@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#Employee List
@app.route('/employees')
@role_required(['admin', 'hr', 'manager'])
def employee_list():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('login'))
        data = res.json()
        employees = data.get("employees", [])
        

        # Fetch leaves data for calculating leave balance
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())

        leaves = []
        if leaves_res.status_code == 200:
            leaves_data = leaves_res.json()
            leaves = leaves_data.get("leaves", [])

        # Process employees with leave balance and role
        employees_with_balance = []
        for emp in employees:
            # Use role from backend if present, otherwise leave empty
            if 'role' not in emp:
                emp['role'] = ''

            # Fetch leave balance from backend API using helper
            emp_name = emp.get("name")
            emp['leave_balance'] = 0
            balance_data = fetch_leave_balance_helper(emp_name)
            
            if balance_data:
                # Try to get remaining leaves from different possible fields
                summary = balance_data.get("summary", {})
                balances = balance_data.get("balances", [])
                
                # Method 1: From summary.remaining_leaves
                if summary.get("remaining_leaves") is not None:
                    emp['leave_balance'] = summary.get("remaining_leaves")
                # Method 2: From summary.total_leaves - summary.used_leaves
                elif summary.get("total_leaves") is not None and summary.get("used_leaves") is not None:
                    emp['leave_balance'] = summary.get("total_leaves") - summary.get("used_leaves")
                # Method 3: Sum of remaining_leaves from balances array
                elif balances:
                    emp['leave_balance'] = sum(b.get("remaining_leaves", 0) for b in balances if isinstance(b, dict))
            else:
                # Fallback: calculate from leaves data if API fails
                used_leave_days = 0
                for leave in leaves:
                    if leave.get("employee_name") == emp_name and leave.get("status") == "approved":
                        from datetime import datetime
                        start_date_str = leave.get("start_date")
                        end_date_str = leave.get("end_date")
                        
                        for date_format in ["%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z"]:
                            try:
                                start_date = datetime.strptime(start_date_str, date_format)
                                end_date = datetime.strptime(end_date_str, date_format)
                                break
                            except ValueError:
                                continue
                        
                        days = (end_date - start_date).days + 1
                        used_leave_days += days
                emp['leave_balance'] = 30 - used_leave_days

            employees_with_balance.append(emp)

    except Exception as e:
        print("ERROR:", e)
        employees_with_balance = []

    return render_template("all_employees.html", employees=employees_with_balance, BASE_URL=BASE_URL)



#  Add Employee
@app.route('/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'GET':
        return render_template('add_employee.html')
    
    form = request.form
    #  Form data
    payload = {
        "name": form['name'],
        "email": form['email'],
        "date_of_joining": form['date_of_joining'],
        "role": form.get('role', 'employee'),
        #"password": form.get('initial_password', ''),
        "date_of_birth": form.get('date_of_birth', ''),
        "phone": form.get('phone', ''),
        #"salary": form.get('salary', ''),
        "designation": form.get('designation', ''),
        "department": form.get('department', ''),
        "gender": form.get('gender', ''),
        "employment_type": form.get('employment_type', ''),
        "reporting_manager": form.get('reporting_manager', ''),
        "address": form.get('address', ''),
    }
    files = {}
    # PDF file
    if 'pdf_file' in request.files:
        pdf = request.files['pdf_file']
        if pdf.filename:
            files['pdf_file'] = (pdf.filename, pdf.read(), pdf.mimetype)
    # DOCX file
    if 'docx_file' in request.files:
        docx = request.files['docx_file']
        if docx.filename:
            files['docx_file'] = (docx.filename, docx.read(), docx.mimetype)
    #  Send to backend API
    try:
        # If there are files, send as form data; otherwise send as JSON
        if files:
            res = requests.post(
                f"{BASE_URL}/employees",
                data=payload,
                files=files,
                headers=get_headers()
            )
        else:
            res = requests.post(
                f"{BASE_URL}/employees",
                json=payload,
                headers=get_headers()
            )

        print("STATUS:", res.status_code)
        print("RESPONSE:", res.text)
        if res.status_code == 201:
            flash("Employee added successfully!", "success")
        else:
            flash("Failed to add employee!", "danger")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash("Server error occurred!", "danger")

    return redirect(url_for('employee_list'))


#  Delete
@app.route('/delete/<int:id>', methods=['POST'])
def delete_employee(id):
    requests.delete(f"{BASE_URL}/employees/{id}", headers=get_headers())
    return redirect(url_for('employee_list'))

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def edit_employee(id):
    if request.method == 'POST':
        form = request.form
        files = request.files
        payload = {
            "name": form['name'],
            "email": form['email'],
            "phone": form['phone'],
            "date_of_joining": form['date_of_joining'],
            "date_of_birth": form.get('date_of_birth', ''),
            "designation": form.get('designation', ''),
            "department": form.get('department', ''),
            "gender": form.get('gender', ''),
            "employment_type": form.get('employment_type', ''),
            "reporting_manager": form.get('reporting_manager', ''),
            "address": form.get('address', ''),
        }
        # Add role to payload if provided (admin only)
        if 'role' in form and form['role']:
            payload['role'] = form['role']
        print(f"EDIT EMPLOYEE PAYLOAD: {payload}")
        file_data = {}
        if 'document' in files:
            doc = files['document']
            if doc.filename != "":
                file_data['document'] = (doc.filename, doc.read(), doc.mimetype)

        try:
            # If there are files, send as form data; otherwise send as JSON
            if file_data:
                res = requests.patch(
                    f"{BASE_URL}/employees/{id}",
                    data=payload,
                    files=file_data,
                    headers=get_headers()
                )
            else:
                res = requests.patch(
                    f"{BASE_URL}/employees/{id}",
                    json=payload,
                    headers=get_headers()
                )
            print(f"EDIT EMPLOYEE RESPONSE (PATCH): Status {res.status_code}, Body: {res.text}")
            
            # If PATCH fails with 405, try PUT
            if res.status_code == 405:
                if file_data:
                    res = requests.put(
                        f"{BASE_URL}/employees/{id}",
                        data=payload,
                        files=file_data,
                        headers=get_headers()
                    )
                else:
                    res = requests.put(
                        f"{BASE_URL}/employees/{id}",
                        json=payload,
                        headers=get_headers()
                    )
                print(f"EDIT EMPLOYEE RESPONSE (PUT): Status {res.status_code}, Body: {res.text}")
            
            # If PUT also fails with 405, try POST
            if res.status_code == 405:
                if file_data:
                    res = requests.post(
                        f"{BASE_URL}/employees/{id}",
                        data=payload,
                        files=file_data,
                        headers=get_headers()
                    )
                else:
                    res = requests.post(
                        f"{BASE_URL}/employees/{id}",
                        json=payload,
                        headers=get_headers()
                    )
                print(f"EDIT EMPLOYEE RESPONSE (POST): Status {res.status_code}, Body: {res.text}")
            
            if res.status_code == 200:
                flash("Employee updated successfully!", "success")
            else:
                flash(f"Failed to update employee: {res.text}", "danger")
        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "danger")

        response = redirect(url_for('employee_list'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    else:
        res = requests.get(f"{BASE_URL}/employees/{id}", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('login'))
        data = res.json()
        return render_template('edit_employee.html', employee=data.get("employee"))


@app.route('/add-timesheet', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def add_timesheet():
    if request.method == 'POST':
        payload = {
            "employee_name": request.form.get("employee_name"),
            "project": request.form.get("project"),
            "task": request.form.get("task"),
            "hours": request.form.get("hours"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "description": request.form.get("description")
        }
        requests.post(f"{BASE_URL}/timesheets", json=payload, headers=get_headers())
        return redirect(url_for('timesheets'))

    # GET projects from backend in real-time
    projects = []
    try:
        proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
        if proj_res.status_code == 200:
            data = proj_res.json()
            projects = data.get("projects", []) if isinstance(data, dict) else data
    except Exception as e:
        print("Failed to fetch projects from backend:", e)

    # existing employees
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    if emp_res.status_code == 401:
        return redirect(url_for('login'))
    employees = emp_res.json().get("employees", [])

    return render_template(
        "add_timesheet.html",
        employees=employees,
        projects=projects,
        today_date=datetime.now().strftime('%Y-%m-%d')
    )


@app.route('/edit-timesheet/<int:timesheet_id>', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def edit_timesheet(timesheet_id):
    # GET existing timesheet data
    res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('login'))
    
    timesheets = res.json().get("timesheets", [])
    timesheet = next((t for t in timesheets if t.get('id') is not None and int(t.get('id')) == int(timesheet_id)), None)
    
    if not timesheet:
        flash("Timesheet not found", "danger")
        return redirect(url_for('timesheets'))
    
    # Backend validation: Only allow editing if status is submitted
    if timesheet.get('status') != 'submitted':
        flash("Cannot edit timesheet - it has already been approved or rejected", "danger")
        return redirect(url_for('timesheets'))
    
    # Backend validation: Only allow employees to edit their own timesheets
    # HR, Manager, and Admin cannot edit employee timesheets
    current_user = session.get('employee_name')
    user_role = session.get('role')
    
    if user_role not in ['employee', 'hr', 'admin']:
        flash("Only authorized roles can edit their own timesheets", "danger")
        return redirect(url_for('timesheets'))
    
    if timesheet.get('employee_name') != current_user:
        flash("You can only edit your own timesheets", "danger")
        return redirect(url_for('timesheets'))
    
    if request.method == 'POST':
        payload = {
            "employee_name": request.form.get("employee_name"),
            "project": request.form.get("project"),
            "task": request.form.get("task"),
            "hours": request.form.get("hours"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "description": request.form.get("description")
        }
        
        # Try PATCH first
        res = requests.patch(
            f"{BASE_URL}/timesheets/{timesheet_id}",
            json=payload,
            headers=get_headers()
        )
        
        # If PATCH fails with 405, try PUT
        if res.status_code == 405:
            res = requests.put(
                f"{BASE_URL}/timesheets/{timesheet_id}",
                json=payload,
                headers=get_headers()
            )
            
        # If PUT also fails with 405, try POST
        if res.status_code == 405:
            res = requests.post(
                f"{BASE_URL}/timesheets/{timesheet_id}",
                json=payload,
                headers=get_headers()
            )
            
        if res.status_code == 200:
            flash("Timesheet updated successfully!", "success")
            return redirect(url_for('timesheets'))
        else:
            flash(f"Failed to update timesheet: {res.text}", "danger")
            return redirect(url_for('timesheets'))

    # GET projects from backend in real-time
    projects = []
    try:
        proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
        if proj_res.status_code == 200:
            data = proj_res.json()
            projects = data.get("projects", []) if isinstance(data, dict) else data
    except Exception as e:
        print("Failed to fetch projects from backend:", e)

    # existing employees
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    if emp_res.status_code == 401:
        return redirect(url_for('login'))
    employees = emp_res.json().get("employees", [])

    return render_template(
        "edit_timesheet.html",
        timesheet=timesheet,
        employees=employees,
        projects=projects
    )


@app.route('/notifications')
@role_required(['admin', 'employee', 'hr', 'manager'])
def notifications():
    if 'token' not in session:
        return redirect(url_for('login'))
    return render_template('notifications.html')


@app.route('/timesheets')
@role_required(['admin', 'employee', 'hr', 'manager'])
def timesheets():
    res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('login'))
    data = res.json()

    # Create project_manager_map from projects_db to map project name to manager name
    project_manager_map = {proj['name'].strip().lower(): proj.get('assigned_manager', '-') for proj in projects_db}

    # Filter timesheets based on role
    timesheets_list = data.get("timesheets", [])

    # Fetch employees to map roles
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    role_map = {emp.get('name'): emp.get('role', 'employee') for emp in employees}

    # Add employee_role to each timesheet
    for t in timesheets_list:
        t['employee_role'] = role_map.get(t.get('employee_name'), 'employee')

    user_role = str(session.get('role', '')).lower()
    current_user = session.get('employee_name')
    
    if user_role == 'employee':
        # Employees can only see their own timesheets
        timesheets_list = [t for t in timesheets_list if t.get('employee_name') == current_user]
    elif user_role == 'manager':
        # Managers can only see timesheets for projects they manage
        managed_projects = [proj['name'] for proj in projects_db if proj.get('assigned_manager') == current_user]
        timesheets_list = [t for t in timesheets_list if t.get('project') in managed_projects]
    # HR and admin see all timesheets (no filtering)

    return render_template(
        "timesheets.html",
        timesheets=timesheets_list,
        project_manager_map=project_manager_map
    )


@app.route('/add-weekly-timesheet')
@role_required(['admin', 'employee', 'hr', 'manager'])
def add_weekly_timesheet():
    return render_template('add_weekly_timesheet.html')


# VIEW LEAVES
@app.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves():
    res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('login'))
    data = res.json()
    return render_template("leaves.html", leaves=data.get("leaves", []), BASE_URL=BASE_URL)

# LEAVES CALENDAR API PROXY
@app.route('/api/leaves/calendar')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_calendar():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    employee_name = request.args.get('employee_name')
    
    params = {'year': year, 'month': month}
    if employee_name:
        params['employee_name'] = employee_name
    
    res = requests.get(f"{BASE_URL}/leaves/calendar", params=params, headers=get_headers())
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

# LEAVES BALANCE API PROXY
@app.route('/api/leaves/balance')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_balance():
    employee_name = request.args.get('employee_name') or session.get('employee_name')
    if not employee_name:
        return jsonify({"success": False, "error": "Employee name required"}), 400
    
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        return jsonify(balance_data)
    
    # Manual Fallback calculation if API fails
    try:
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers(), timeout=10)
        if leaves_res.status_code == 200:
            leaves_data = leaves_res.json().get("leaves", [])
            # Detailed fallback calculation by category
            used_stats = {
                "casual": 0,
                "sick": 0,
                "earned": 0,
                "total": 0
            }
            
            # Standard quotas (can be adjusted if database provides them)
            quotas = {
                "casual": 12,
                "sick": 10,
                "earned": 8,
                "total": 30
            }

            # Try both names for matching
            names_to_try = [employee_name]
            if len(employee_name) > 2:
                names_to_try.append(employee_name[2:].strip())

            for leave in leaves_data:
                if leave.get("employee_name") in names_to_try and leave.get("status") == "approved":
                    try:
                        s_date = datetime.strptime(leave.get("start_date")[:10], "%Y-%m-%d")
                        e_date = datetime.strptime(leave.get("end_date")[:10], "%Y-%m-%d")
                        days = (e_date - s_date).days + 1
                        
                        ltype = (leave.get("leave_type") or "").lower()
                        if "casual" in ltype: used_stats["casual"] += days
                        elif "sick" in ltype: used_stats["sick"] += days
                        elif "earned" in ltype: used_stats["earned"] += days
                        
                        used_stats["total"] += days
                    except:
                        continue
            
            return jsonify({
                "success": True,
                "summary": {
                    "total_leaves": quotas["total"],
                    "used_leaves": used_stats["total"],
                    "remaining_leaves": quotas["total"] - used_stats["total"],
                    "casual_used": used_stats["casual"],
                    "casual_total": quotas["casual"],
                    "sick_used": used_stats["sick"],
                    "sick_total": quotas["sick"],
                    "earned_used": used_stats["earned"],
                    "earned_total": quotas["earned"]
                },
                "balances": [
                    {"leave_type": "Casual", "used_leaves": used_stats["casual"], "total_leaves": quotas["casual"], "remaining_leaves": quotas["casual"] - used_stats["casual"]},
                    {"leave_type": "Sick", "used_leaves": used_stats["sick"], "total_leaves": quotas["sick"], "remaining_leaves": quotas["sick"] - used_stats["sick"]},
                    {"leave_type": "Earned", "used_leaves": used_stats["earned"], "total_leaves": quotas["earned"], "remaining_leaves": quotas["earned"] - used_stats["earned"]}
                ]
            })
    except Exception as e:
        print(f"Error in balance fallback: {e}")
    
    return jsonify({"success": False, "error": "Leave balance API unavailable and fallback calculation failed"}), 500

# ATTENDANCE
@app.route('/attendance')
@role_required(['admin', 'employee', 'hr', 'manager'])
def attendance():
    if 'token' not in session:
        return redirect(url_for('login'))
    
    from datetime import datetime, timedelta
    from calendar import monthrange
    
    try:
        # Get date range from query parameters or default to current month
        from_date_param = request.args.get('from_date')
        to_date_param = request.args.get('to_date')
        
        if from_date_param and to_date_param:
            from_date = from_date_param
            to_date = to_date_param
        else:
            # Default to current month
            today = datetime.now()
            from_date = today.replace(day=1).strftime('%Y-%m-%d')
            last_day = monthrange(today.year, today.month)[1]
            to_date = today.replace(day=last_day).strftime('%Y-%m-%d')
        
        # Calculate total days in the selected range
        from_dt = datetime.strptime(from_date, '%Y-%m-%d')
        to_dt = datetime.strptime(to_date, '%Y-%m-%d')
        total_days = (to_dt - from_dt).days + 1
        
        # Calculate weekends in the selected range
        weekends = 0
        current_date = from_dt
        while current_date <= to_dt:
            if current_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
                weekends += 1
            current_date += timedelta(days=1)
        
        working_days = total_days - weekends
        
        # Fetch attendance records from backend
        # Note: Adjust the endpoint based on your backend API
        attendance_res = requests.get(f"{BASE_URL}/attendance", headers=get_headers())
        
        if attendance_res.status_code == 401:
            return redirect(url_for('login'))
        
        attendance_data = []
        if attendance_res.status_code == 200:
            data = attendance_res.json()
            attendance_data = data.get("attendance", [])
        
        # Fetch leave records
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leave_data = []
        if leaves_res.status_code == 200:
            leaves_json = leaves_res.json()
            leave_data = leaves_json.get("leaves", [])
        
        # Fetch leave balance from backend using helper
        leave_balance = 0
        balance_data = fetch_leave_balance_helper(session.get('employee_name'))
        if balance_data:
            backend_summary = balance_data.get("summary", {})
            balances = balance_data.get("balances", [])
            
            # Try to get remaining leaves from different possible fields
            if backend_summary.get("remaining_leaves") is not None:
                leave_balance = backend_summary.get("remaining_leaves")
            elif backend_summary.get("total_leaves") is not None and backend_summary.get("used_leaves") is not None:
                leave_balance = backend_summary.get("total_leaves") - backend_summary.get("used_leaves")
            elif balances:
                leave_balance = sum(b.get("remaining_leaves", 0) for b in balances if isinstance(b, dict))

        
        # Fetch holidays from backend
        holidays_count = 0
        try:
            holidays_res = requests.get(f"{BASE_URL}/holidays", headers=get_headers())
            if holidays_res.status_code == 200:
                holidays_data = holidays_res.json()
                holidays = holidays_data.get("holidays", [])
                # Count holidays in selected date range
                for holiday in holidays:
                    holiday_date = holiday.get("date", "")
                    if from_date <= holiday_date[:10] <= to_date:
                        holidays_count += 1
        except Exception as e:
            print(f"ERROR fetching holidays: {e}")
            holidays_count = 0
        
        # Filter attendance for current user if employee
        current_user = session.get('employee_name')
        user_role = session.get('role')
        
        # Ensure employee_id is in session
        if session.get('employee_id') == 'N/A' or not session.get('employee_id'):
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
            if emp_res.status_code == 200:
                employees = emp_res.json().get("employees", [])
                for emp in employees:
                    if emp.get('name') == current_user:
                        session['employee_id'] = emp.get('id')
                        break
        
        if user_role == 'employee':
            attendance_data = [a for a in attendance_data if a.get('employee_name') == current_user]
            leave_data = [l for l in leave_data if l.get('employee_name') == current_user]
        
        # Filter attendance and leave data by selected date range
        attendance_data = [a for a in attendance_data if a.get('date') and from_date <= a.get('date')[:10] <= to_date]
        leave_data = [l for l in leave_data if l.get('start_date') and from_date <= l.get('start_date')[:10] <= to_date]
        
        # Calculate metrics from attendance data
        attendance_count = len([a for a in attendance_data if a.get('status') == 'present'])
        half_day_count = len([a for a in attendance_data if a.get('status') == 'half-day'])
        absent_count = len([a for a in attendance_data if a.get('status') == 'absent'])
        
        # Calculate total hours and average
        total_hours = sum(float(a.get('total_worked_hours', 0)) for a in attendance_data)
        avg_hours = round(total_hours / attendance_count, 2) if attendance_count > 0 else 0
        
        # Calculate leaves used
        approved_leaves = [l for l in leave_data if l.get('status') == 'approved']
        leaves_used = len(approved_leaves)
        
        # Calculate attendance metrics
        office_count = len([a for a in attendance_data if a.get('status') == 'present'])
        wfh_count = 0  # Add logic if WFH is tracked
        overtime_count = len([a for a in attendance_data if a.get('work_status') == 'overtime'])
        late_login_count = len([a for a in attendance_data if a.get('remarks') and 'late' in a.get('remarks', '').lower()])
        
        attendance_summary = {
            'from_date': from_date,
            'to_date': to_date,
            'total_days': total_days,
            'working_days': working_days,
            'weekends': weekends,
            'holidays': holidays_count,
            'attendance': attendance_count,
            'avg_hours': avg_hours,
            'leaves_used': leaves_used,
            'leave_balance': leave_balance,
            'absent': absent_count
        }
        
        attendance_metrics = {
            'office': office_count,
            'wfh': wfh_count,
            'half_day': half_day_count,
            'absent': absent_count,
            'overtime': overtime_count,
            'late_login': late_login_count
        }
        
        # Filter for approved attendance (present records)
        approved_attendance = [a for a in attendance_data if a.get('status') in ['present', 'half-day']]
        
        return render_template(
            'attendance.html',
            attendance_summary=attendance_summary,
            attendance_metrics=attendance_metrics,
            approved_attendance=approved_attendance,
            leave_details=leave_data,
            attendance_details=attendance_data
        )
        
    except Exception as e:
        print(f"ERROR in attendance route: {e}")
        return render_template(
            'attendance.html',
            attendance_summary={},
            attendance_metrics={},
            approved_attendance=[],
            leave_details=[],
            attendance_details=[],
            error="Failed to load attendance data"
        )


# HELP DESK
@app.route('/helpdesk')
@role_required(['admin', 'employee', 'hr', 'manager'])
def helpdesk():
    if 'token' not in session:
        return redirect(url_for('login'))
    return render_template('helpdesk.html', BASE_URL=BASE_URL)

# HELP DESK API PROXY ROUTES
@app.route('/api/helpdesk/', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_helpdesk_list():
    try:
        if request.method == 'POST':
            res = requests.post(f"{BASE_URL}/helpdesk/", json=request.get_json(), headers=get_headers(), timeout=10)
        else:
            params = request.args.to_dict()
            res = requests.get(f"{BASE_URL}/helpdesk/", params=params, headers=get_headers(), timeout=10)
        
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        
        return jsonify(res.json())
    except Exception as e:
        print(f"Helpdesk List Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/helpdesk/<int:ticket_id>', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_helpdesk_detail(ticket_id):
    try:
        res = requests.get(f"{BASE_URL}/helpdesk/{ticket_id}", headers=get_headers(), timeout=10)
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        
        return jsonify(res.json())
    except Exception as e:
        print(f"Helpdesk Detail Error: {ticket_id}, {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/helpdesk/<int:ticket_id>/status', methods=['PATCH'])
@role_required(['admin', 'hr'])
def api_helpdesk_status(ticket_id):
    try:
        res = requests.patch(f"{BASE_URL}/helpdesk/{ticket_id}/status", json=request.get_json(), headers=get_headers(), timeout=10)
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return jsonify(res.json())
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/helpdesk/<int:ticket_id>/assign', methods=['PATCH'])
@role_required(['admin', 'hr'])
def api_helpdesk_assign(ticket_id):
    try:
        res = requests.patch(f"{BASE_URL}/helpdesk/{ticket_id}/assign", json=request.get_json(), headers=get_headers(), timeout=10)
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return jsonify(res.json())
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/helpdesk/<int:ticket_id>/priority', methods=['PATCH'])
@role_required(['admin'])
def api_helpdesk_priority(ticket_id):
    try:
        res = requests.patch(f"{BASE_URL}/helpdesk/{ticket_id}/priority", json=request.get_json(), headers=get_headers(), timeout=10)
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return jsonify(res.json())
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

MESSAGES_FILE = 'helpdesk_messages.json'

def load_local_messages():
    try:
        with open(MESSAGES_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_local_messages(messages):
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages, f, indent=4)

@app.route('/api/helpdesk/<int:ticket_id>/messages', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_helpdesk_messages(ticket_id):
    try:
        all_messages = load_local_messages()
        ticket_key = str(ticket_id)
        
        if request.method == 'POST':
            data = request.get_json()
            new_msg = {
                "sender_name": session.get('employee_name', 'Unknown'),
                "message": data.get('message', ''),
                "created_at": datetime.now().isoformat()
            }
            if ticket_key not in all_messages:
                all_messages[ticket_key] = []
            all_messages[ticket_key].append(new_msg)
            save_local_messages(all_messages)
            return jsonify({"success": True, "message": "Message sent locally"})
        else:
            messages = all_messages.get(ticket_key, [])
            return jsonify({"success": True, "messages": messages})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# REIMBURSEMENT
@app.route('/reimbursement')
@role_required(['admin', 'employee', 'hr', 'manager'])
def reimbursement():
    if 'token' not in session:
        return redirect(url_for('login'))
    return render_template('reimbursement.html', BASE_URL=BASE_URL)

@app.route('/api/reimbursements/stats', methods=['GET'])
@role_required(['admin', 'hr'])
def api_reimbursement_stats():
    try:
        res = requests.get(f"{BASE_URL}/reimbursements/stats", headers=get_headers(), timeout=10)
        if res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        return jsonify(res.json())
    except Exception as e:
        print(f"Reimbursement Stats Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# REIMBURSEMENT API PROXY ROUTES
@app.route('/api/reimbursements', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursements():
    if request.method == 'POST':
        # Handle multipart form data for file upload
        if request.content_type and 'multipart' in request.content_type:
            form_data = {}
            for key in request.form:
                form_data[key] = request.form[key]
            
            files = {}
            if 'receipt' in request.files:
                receipt_file = request.files['receipt']
                if receipt_file.filename:
                    # Reset file pointer to beginning
                    receipt_file.seek(0)
                    # Pass file object directly
                    files['receipt'] = (receipt_file.filename, receipt_file, receipt_file.mimetype)
            
            # Use headers without Content-Type for multipart form data
            headers_no_ct = {
                "Authorization": f"Bearer {session.get('token')}"
            }
            res = requests.post(f"{BASE_URL}/reimbursements/", data=form_data, files=files, headers=headers_no_ct)
        else:
            res = requests.post(f"{BASE_URL}/reimbursements/", json=request.get_json(), headers=get_headers())
    else:
        # GET request with filters
        params = request.args.to_dict()
        res = requests.get(f"{BASE_URL}/reimbursements/", params=params, headers=get_headers())
    
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>', methods=['GET', 'DELETE'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursement_detail(record_id):
    if request.method == 'DELETE':
        res = requests.delete(f"{BASE_URL}/reimbursements/{record_id}", headers=get_headers())
    else:
        res = requests.get(f"{BASE_URL}/reimbursements/{record_id}", headers=get_headers())
    
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>/approve', methods=['PATCH'])
@role_required(['admin', 'hr', 'manager'])
def api_approve_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/approve", json=request.get_json(), headers=get_headers())
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>/reject', methods=['PATCH'])
@role_required(['admin', 'hr', 'manager'])
def api_reject_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/reject", json=request.get_json(), headers=get_headers())
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>/pay', methods=['PATCH'])
@role_required(['admin', 'hr', 'manager'])
def api_pay_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/pay", json=request.get_json(), headers=get_headers())
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>/history', methods=['GET'])
@role_required(['admin', 'hr', 'manager'])
def api_reimbursement_history(record_id):
    res = requests.get(f"{BASE_URL}/reimbursements/{record_id}/history", headers=get_headers())
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    return res.json()

@app.route('/api/reimbursements/<int:record_id>/receipt', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursement_receipt(record_id):
    res = requests.get(f"{BASE_URL}/reimbursements/{record_id}/receipt", headers=get_headers(), stream=True)
    if res.status_code == 401:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    if res.status_code == 404:
        return jsonify({"success": False, "error": "Receipt not found"}), 404
    
    # Stream the file back
    def generate():
        for chunk in res.iter_content(chunk_size=8192):
            yield chunk
    
    return Response(generate(), content_type=res.headers.get('Content-Type'), headers={
        'Content-Disposition': res.headers.get('Content-Disposition', 'attachment')
    })


# ADD LEAVE
@app.route('/add-leave', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def add_leave():
    headers = get_headers()
    employee_name = session.get('employee_name')
    if request.method == 'POST':
        payload = {
            "employee_name": request.form.get("employee_name"),
            "start_date": request.form.get("start_date"),
            "end_date": request.form.get("end_date"),
            "leave_type": request.form.get("leave_type"),
            "reason": request.form.get("reason"),
            "leave_type_category": request.form.get("leave_type_category", "full_day")
        }
        # Add half_day_period only if it's a half-day leave
        if request.form.get("leave_type_category") == "half_day":
            payload["half_day_period"] = request.form.get("half_day_period")
        requests.post(f"{BASE_URL}/leaves", json=payload, headers=headers)
        return redirect(url_for('leaves'))

    # LOAD EMPLOYEES (existing)
    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    if res.status_code == 401:
        return redirect(url_for('login'))
    employees = res.json().get("employees", [])
    # NEW: FETCH LEAVE BALANCE
    balance_data = fetch_leave_balance_helper(employee_name)
    balance = []
    summary = {"remaining_leaves": 0, "casual_leaves": 0, "sick_leaves": 0, "earned_leaves": 0}
    if balance_data:
        balance = balance_data.get("balances", [])
        backend_summary = balance_data.get("summary", {})
        
        # Extract specific counts for the dropdown
        summary = {
            "remaining_leaves": backend_summary.get("remaining_leaves", 0),
            "casual_leaves": backend_summary.get("casual_remaining", 0),
            "sick_leaves": backend_summary.get("sick_remaining", 0),
            "earned_leaves": backend_summary.get("earned_remaining", 0)
        }
        
        # If the summary keys are missing, try to find them in the balances array
        if not summary["casual_leaves"] or not summary["sick_leaves"]:
            for b in balance:
                ltype = b.get("leave_type", "").lower()
                if "casual" in ltype: summary["casual_leaves"] = b.get("remaining_leaves", 0)
                if "sick" in ltype: summary["sick_leaves"] = b.get("remaining_leaves", 0)
                if "earned" in ltype: summary["earned_leaves"] = b.get("remaining_leaves", 0)
    else:
        # Fallback calculation if API fails
        try:
            leaves_res = requests.get(f"{BASE_URL}/leaves", headers=headers, timeout=10)
            if leaves_res.status_code == 200:
                leaves_data = leaves_res.json().get("leaves", [])
                used_days = 0
                names_to_try = [employee_name]
                if len(employee_name) > 2:
                    names_to_try.append(employee_name[2:].strip())
                
                for leave in leaves_data:
                    if leave.get("employee_name") in names_to_try and leave.get("status") == "approved":
                        try:
                            s_date = datetime.strptime(leave.get("start_date")[:10], "%Y-%m-%d")
                            e_date = datetime.strptime(leave.get("end_date")[:10], "%Y-%m-%d")
                            used_days += (e_date - s_date).days + 1
                        except:
                            continue
                
                # Default distribution for fallback
                summary = {
                    "remaining_leaves": 30 - used_days,
                    "casual_leaves": 12,
                    "sick_leaves": 10,
                    "earned_leaves": 8
                }
                balance = [{"leave_type": "Calculated Fallback", "remaining_leaves": 30 - used_days}]
        except Exception as e:
            print(f"Error in add_leave fallback: {e}")
            summary = {"remaining_leaves": 0, "casual_leaves": 0, "sick_leaves": 0, "earned_leaves": 0}
            balance = []
    return render_template(
        "add_leave.html",
        employees=employees,
        balance=balance,
        summary=summary
    )







@app.route('/profile')
def profile():
    #  1. LOGIN CHECK
    if 'employee_name' not in session or 'role' not in session:
        return redirect(url_for('login'))
    headers = get_headers()
    employee_name = session.get('employee_name')
    # Get all employees and find the current user
    res = requests.get(
        f"{BASE_URL}/employees",
        headers=headers
    )

    # Initialize with fallback data
    employee = {}
    documents = {}

    try:
        if res.status_code == 200:
            data = res.json()
            employees_list = data.get("employees", [])
            # Find current employee by name
            for emp in employees_list:
                if emp.get("name") == employee_name:
                    employee = emp
                    break

            if not employee:
                employee = {}

        else:
            employee = {
                'name': session.get('employee_name', 'Unknown'),
                'email': 'N/A',
                'role': session.get('role', 'N/A'),
                'department': 'N/A',
                'position': 'N/A'
            }

    except requests.exceptions.JSONDecodeError as e:
        employee = {
            'name': session.get('employee_name', 'Unknown'),
            'email': 'N/A',
            'role': session.get('role', 'N/A'),
            'department': 'N/A',
            'position': 'N/A'
        }

    doc_keys = [
        "pan_card",
        "aadhar_card",
        "tenth_cert",
        "twelfth_cert",
        "graduation_cert",
        "postgrad_cert"
    ]
    #  3. CALCULATE PROGRESS (SAFE)
    uploaded = sum(
        1 for key in doc_keys
        if documents.get(key) and str(documents.get(key)).strip()
    )
    total_docs = len(doc_keys)
    percent = int((uploaded / total_docs) * 100) if total_docs else 0
    # Fetch leave balance from backend API using helper
    summary = {'remaining_leaves': 0}
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        backend_summary = balance_data.get("summary", {})
        balances = balance_data.get("balances", [])
        if backend_summary.get("remaining_leaves") is not None:
            summary = {'remaining_leaves': backend_summary.get("remaining_leaves")}
        elif backend_summary.get("total_leaves") is not None and backend_summary.get("used_leaves") is not None:
            summary = {'remaining_leaves': backend_summary.get("total_leaves") - backend_summary.get("used_leaves")}
        elif balances:
            summary = {'remaining_leaves': sum(b.get("remaining_leaves", 0) for b in balances if isinstance(b, dict))}
    else:
        # Fallback calculation
        try:
            res = requests.get(f"{BASE_URL}/leaves", headers=headers)
            if res.status_code == 200:
                data = res.json()
                leaves = data.get("leaves", [])
                total_leave_days = 30
                used_leave_days = 0
                for leave in leaves:
                    if leave.get("employee_name") == employee_name and leave.get("status") == "approved":
                        from datetime import datetime
                        start_date_str = leave.get("start_date")
                        end_date_str = leave.get("end_date")
                        for date_format in ["%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %Z"]:
                            try:
                                start_date = datetime.strptime(start_date_str, date_format)
                                end_date = datetime.strptime(end_date_str, date_format)
                                break
                            except ValueError:
                                continue
                        days = (end_date - start_date).days + 1
                        used_leave_days += days
                summary = {'remaining_leaves': total_leave_days - used_leave_days}
        except Exception as e:
            print(f"Error in fallback: {e}")
            summary = {'remaining_leaves': 0}


    # Fetch bank details
    bank_details = {}
    try:
        res = requests.get(f"{BASE_URL}/bank-details/", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            bank_details = data.get("bank_details", {})
    except Exception as e:
        print("ERROR fetching bank details:", e)
        bank_details = {}

    #  4. PASS FLAG (IMPORTANT)
    return render_template(
        "profile.html",
        employee=employee,
        documents=documents,
        percent=percent,
        summary=summary,
        bank_details=bank_details,
        is_hr_view=False,
        BASE_URL=BASE_URL
    )


@app.route('/upload-document', methods=['POST'])
def upload_document():
    #if session.get('role') == 'hr':
        #return redirect(url_for('dashboard'))  # ❌ block HR
    file = request.files.get('file')
    doc_type = request.form.get('type')
    employee_id = request.form.get("employee_id")
    payload_data = {
        "type": doc_type,
        "employee_id": employee_id
    }
    if not file or file.filename == "":
        flash("No file selected", "danger")
        return redirect(request.referrer)
    files = {
        "file": (file.filename, file.read(), file.mimetype)
    }
    try:
        res = requests.post(
            f"{BASE_URL}/upload-document",
            data=payload_data,
            files=files,
            headers=get_headers()
        )
        print('UPLOAD RESPONSE STATUS:', res.status_code)
        print('UPLOAD RESPONSE TEXT:', res.text)
        if res.status_code in [200, 201]:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": True, "message": "Document uploaded successfully"})
            else:
                flash("Document uploaded successfully", "success")
                return redirect(request.referrer)
        else:
            error_msg = None
            try:
                error_msg = res.json().get('error')
            except Exception:
                error_msg = res.text
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"success": False, "error": error_msg or "Upload failed"}), res.status_code
            else:
                flash(error_msg or "Upload failed", "danger")
                return redirect(request.referrer)
    except Exception as e:
        print('EXCEPTION during upload:', e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"success": False, "error": "Server error"}), 500
        else:
            flash("Server error", "danger")
            return redirect(request.referrer)


# ── Lightweight photo URL endpoint (called async by sidebar JS) ───────────────
@app.route('/api/my-photo')
def api_my_photo():
    """Return the current user's photo_url for the sidebar. Never blocks login."""
    if 'token' not in session:
        return jsonify({'photo_url': None}), 200
    # Return from session cache if available (set after upload)
    if session.get('photo_url'):
        return jsonify({'photo_url': session['photo_url']}), 200
    # Otherwise do a lightweight lookup
    try:
        emp_name = session.get('employee_name')
        res = requests.get(
            f"{BASE_URL}/employees",
            headers=get_headers(),
            timeout=4
        )
        if res.status_code == 200:
            for emp in res.json().get('employees', []):
                if emp.get('name') == emp_name:
                    url = emp.get('photo_url') or emp.get('photo') or None
                    if url:
                        session['photo_url'] = url  # cache for next time
                    return jsonify({'photo_url': url}), 200
    except Exception:
        pass
    return jsonify({'photo_url': None}), 200


# ── Proxy: serve uploaded files from the backend ──────────────────────────────
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """
    Transparently proxy static uploads (photos, documents) that live on the
    backend server so that <img src="/uploads/photos/xxx.jpg"> works in the
    browser without exposing the backend IP directly.
    """
    try:
        res = requests.get(
            f"{BASE_URL}/uploads/{filename}",
            headers={'Authorization': f"Bearer {session.get('token', '')}"},
            stream=True,
            timeout=10
        )
        if res.status_code == 200:
            return Response(
                res.iter_content(chunk_size=8192),
                status=200,
                content_type=res.headers.get('Content-Type', 'application/octet-stream')
            )
        return '', res.status_code
    except Exception as e:
        print(f"Error proxying upload {filename}: {e}")
        return '', 502


# ── Photo upload: proxy to backend /employees/<id>/photo ──────────────────────
@app.route('/upload-photo', methods=['POST'])
def upload_photo():
    """
    Accepts a multipart/form-data POST with a 'photo' file field and an
    optional 'employee_id' hidden field.  Forwards the file to the backend
    and refreshes the page on success.
    """
    if 'token' not in session:
        return redirect(url_for('login'))

    file = request.files.get('photo')
    employee_id = request.form.get('employee_id')

    # Derive employee_id from session if not provided (own-profile upload)
    if not employee_id:
        # Look up the employee record to get the id
        try:
            emp_res = requests.get(
                f"{BASE_URL}/employees",
                headers=get_headers(),
                timeout=5
            )
            if emp_res.status_code == 200:
                emp_name = session.get('employee_name')
                for emp in emp_res.json().get('employees', []):
                    if emp.get('name') == emp_name:
                        employee_id = emp.get('id')
                        break
        except Exception as e:
            print(f"Error resolving employee_id for photo upload: {e}")

    if not file or file.filename == '':
        flash('No photo file selected', 'danger')
        return redirect(request.referrer or url_for('profile'))

    if not employee_id:
        flash('Could not determine employee ID for photo upload', 'danger')
        return redirect(request.referrer or url_for('profile'))

    try:
        res = requests.post(
            f"{BASE_URL}/employees/{employee_id}/photo",
            files={'photo': (file.filename, file.read(), file.mimetype)},
            headers={'Authorization': f"Bearer {session.get('token', '')}"}
        )
        if res.status_code == 200:
            data = res.json()
            # Update sidebar photo in session immediately
            new_photo_url = data.get('photo_url')
            if new_photo_url:
                session['photo_url'] = new_photo_url
            flash('Profile photo updated successfully!', 'success')
        else:
            err = res.json().get('error', 'Upload failed')
            flash(f'Photo upload failed: {err}', 'danger')
    except Exception as e:
        print(f"Error uploading photo: {e}")
        flash('Server error during photo upload', 'danger')

    return redirect(request.referrer or url_for('profile'))


@app.route('/update-leave/<int:leave_id>/<status>', methods=['PUT'])
@role_required(['admin', 'manager', 'hr'])
def update_leave_status(leave_id, status):
    headers = get_headers()
    try:
        res = requests.put(
            f"{BASE_URL}/leaves/{leave_id}",
            json={"status": status},
            headers=headers
        )
        if res.status_code == 200:
            return jsonify({'success': True, 'message': f'Leave {status} successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to update leave status'}), 500
    except Exception as e:
        print("ERROR updating leave status:", e)
        return jsonify({'success': False, 'error': 'Failed to update leave status'}), 500


@app.route('/update-bank-details', methods=['POST'])
def update_bank_details():
    if 'token' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        # User submits/updates: backend sets status to 'submitted'
        res = requests.post(
            f"{BASE_URL}/bank-details/",
            json=data,
            headers=get_headers()
        )
        
        if res.status_code in [200, 201]:
            return jsonify({'success': True, 'message': 'Bank details updated and sent for verification.'})
        else:
            return jsonify({'success': False, 'error': res.text}), res.status_code
    except Exception as e:
        print("ERROR updating bank details:", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/profile/<employee_name>')
def view_profile(employee_name):
    if 'user' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'hr':
        return redirect(url_for('profile'))  # own profile only
    headers = get_headers()
    res = requests.get(
        f"{BASE_URL}/profile/{employee_name}",
        headers=headers
    )
    data = res.json()
    print("PROFILE API RESPONSE:", data)
    employee = data.get("employee", {})
    documents = data.get("documents") or {}
    # Fetch leave balance for the employee using helper
    summary = {}
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        summary = balance_data.get("summary", {})
    # SAME FIXED PROGRESS LOGIC
    doc_keys = [
        "pan_card",
        "aadhar_card",
        "tenth_cert",
        "twelfth_cert",
        "graduation_cert",
        "postgrad_cert"
    ]
    uploaded = sum(
        1 for key in doc_keys
        if documents.get(key) and str(documents.get(key)).strip()
    )
    percent = int((uploaded / len(doc_keys)) * 100)

    # Fetch bank details
    bank_details = {}
    try:
        res = requests.get(f"{BASE_URL}/bank-details/", headers=headers, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data.get("bank_details"), list):
                # If HR view, find the specific employee
                bank_details = next((b for b in data["bank_details"] if b.get("employee_name") == employee_name), {})
            else:
                bank_details = data.get("bank_details", {})
    except Exception as e:
        print("ERROR fetching bank details:", e)
        bank_details = {}

    return render_template(
        "profile.html",
        employee=employee,
        documents=documents,
        percent=percent,
        summary=summary,
        bank_details=bank_details,
        is_hr_view=True,
        BASE_URL=BASE_URL
    )



# Debug endpoint for policies
@app.route('/debug-policies')
def debug_policies():
    debug_info = {
        'BASE_URL': BASE_URL,
        'session_keys': list(session.keys()),
        'has_user': 'user' in session,
        'has_token': 'token' in session,
        'token': session.get('token', 'None'),
        'user': session.get('user', 'None'),
        'role': session.get('role', 'None'),
        'headers': get_headers()
    }

    # Test backend connectivity

    try:

        test_res = requests.get(f"{BASE_URL}/", timeout=5)

        debug_info['backend_test'] = {

            'status': test_res.status_code,

            'reachable': True

        }

    except Exception as e:

        debug_info['backend_test'] = {

            'status': 'Error',

            'reachable': False,

            'error': str(e)

        }

    

    return f"<pre>{json.dumps(debug_info, indent=2)}</pre>"





# Policies Page - All Users

@app.route('/policies')

@role_required(['admin', 'employee', 'hr', 'manager'])

def policies():

    try:

        # Check if user is logged in and has token

        if 'user' not in session:

            print("DEBUG: User not in session - redirecting to login")

            return redirect(url_for('login'))

        

        token = session.get('token')

        if not token:

            

            return redirect(url_for('login'))

        

        

        

        

        

        res = requests.get(f"{BASE_URL}/reports/policies", headers=get_headers(), timeout=10)

        

        

        

        if res.status_code == 401:

            

            return redirect(url_for('login'))

        

        # Check for authentication error in response body

        try:

            response_data = res.json()

            if not response_data.get('success') and 'Token is missing' in response_data.get('error', ''):

                

                return redirect(url_for('login'))

        except:

            pass  # If response is not JSON, continue with normal flow

        

        if res.status_code != 200:

            if res.status_code == 404:
                return render_template(
                    "policies.html",
                    policies=[],
                    categories=[],
                    BASE_URL=BASE_URL
                )
            else:
                

                

                return render_template(

                    "policies.html",

                    policies=[],

                    categories=[],

                    BASE_URL=BASE_URL,

                    error=f"Failed to fetch policies: API returned {res.status_code} - {res.text[:100]}"

                )

        

        data = res.json()

        
        policies_list = data.get("policies", [])

        # Extract unique categories for filter dropdown
        categories = list(set(policy.get('category', 'General') for policy in policies_list))
        categories.sort()

        return render_template(
            "policies.html",
            policies=policies_list,
            categories=categories,
            BASE_URL=BASE_URL
        )

    except requests.exceptions.ConnectionError as e:

        print(f"ERROR: Cannot connect to backend API: {e}")

        print(f"ERROR: Make sure backend server is running at {BASE_URL}")

        return render_template(

            "policies.html",

            policies=[],

            categories=[],

            BASE_URL=BASE_URL,

            error=f"Cannot connect to backend server at {BASE_URL}. Please ensure the backend server is running and accessible."

        )

    except requests.exceptions.Timeout as e:

        print(f"ERROR: Connection timeout to backend API: {e}")

        return render_template(

            "policies.html",

            policies=[],

            categories=[],

            BASE_URL=BASE_URL,

            error=f"Connection timeout to backend server. The server may be busy or not responding."

        )

    except Exception as e:

        print(f"ERROR in policies route: {e}")

        import traceback

        traceback.print_exc()

        return render_template(

            "policies.html",

            policies=[],

            categories=[],

            BASE_URL=BASE_URL,

            error=f"Error: {str(e)}"

        )

    





# API route for manager timesheet approval
@app.route('/manager/timesheets/pending', methods=['GET'])
@role_required(['admin', 'manager', 'hr'])
def api_get_pending_timesheets(current_user):

    try:

        # Prefer backend pending endpoint if available.
        res = requests.get(
            f"{BASE_URL}/timesheets/pending",
            headers=get_headers(),
            timeout=10
        )

        if res.status_code == 200:
            data = res.json()
            pending_timesheets = (
                data.get("pending_timesheets")
                if isinstance(data.get("pending_timesheets"), list)
                else data.get("timesheets", [])
            )
            # Keep a defensive filter in case backend returns a mixed list.
            pending_timesheets = [t for t in pending_timesheets if str(t.get('status', '')).lower() in ('submitted', 'pending')]
            # Return both keys for backward compatibility with existing frontend code.
            return jsonify({
                "success": True,
                "pending_timesheets": pending_timesheets,
                "timesheets": pending_timesheets
            }), 200
        elif res.status_code == 404:
            # Fallback for older backends without dedicated pending endpoint.
            fallback_res = requests.get(
                f"{BASE_URL}/timesheets",
                headers=get_headers(),
                timeout=10
            )
            if fallback_res.status_code == 200:
                data = fallback_res.json()
                all_timesheets = data.get("timesheets", [])
                pending_timesheets = [t for t in all_timesheets if str(t.get('status', '')).lower() in ('submitted', 'pending')]
                return jsonify({
                    "success": True,
                    "pending_timesheets": pending_timesheets,
                    "timesheets": pending_timesheets
                }), 200
            try:
                return jsonify(fallback_res.json()), fallback_res.status_code
            except:
                return jsonify({"success": False, "error": fallback_res.text}), fallback_res.status_code
        else:
            try:
                return jsonify(res.json()), res.status_code
            except:
                return jsonify({"success": False, "error": res.text}), res.status_code

            

    except requests.exceptions.ConnectionError as e:

        print(f"ERROR: Cannot connect to backend at {BASE_URL}: {e}")

        return jsonify({

            "success": False, 

            "error": f"Cannot connect to backend server at {BASE_URL}. Please ensure the backend server is running."

        }), 500

    except requests.exceptions.Timeout as e:

        print(f"ERROR: Connection timeout to backend: {e}")

        return jsonify({

            "success": False, 

            "error": "Connection timeout to backend server. The server may be busy."

        }), 500

    except Exception as e:

        print(f"ERROR in pending timesheets API: {e}")

        return jsonify({"success": False, "error": str(e)}), 500



def _fetch_timesheet_by_id(timesheet_id):
    """Fetch a single timesheet; fallback to list lookup when detail response shape varies."""
    detail_res = requests.get(
        f"{BASE_URL}/timesheets/{timesheet_id}",
        headers=get_headers(),
        timeout=10
    )
    if detail_res.status_code == 200:
        detail_data = detail_res.json()
        if isinstance(detail_data, dict) and isinstance(detail_data.get("timesheet"), dict):
            return detail_data.get("timesheet")
        if isinstance(detail_data, dict):
            return detail_data

    list_res = requests.get(
        f"{BASE_URL}/timesheets",
        headers=get_headers(),
        timeout=10
    )
    if list_res.status_code == 200:
        all_timesheets = list_res.json().get("timesheets", [])
        wanted_id = str(timesheet_id)
        return next((t for t in all_timesheets if str(t.get("id")) == wanted_id), None)

    return None


def _update_timesheet_status(timesheet_id, target_status, rejection_reason=""):
    review_url = f"{BASE_URL}/timesheets/{timesheet_id}/review"
    direct_url = f"{BASE_URL}/timesheets/{timesheet_id}"

    # Backend contract from README: PATCH /timesheets/<id>/review
    method_targets = [
        (requests.patch, review_url),
        # Compatibility fallbacks for existing deployments.
        (requests.patch, direct_url),
        (requests.put, direct_url),
        (requests.post, direct_url),
    ]

    payloads = [
        {"status": target_status},
        {"action": target_status},
        {"review_status": target_status},
    ]
    if target_status == "rejected" and rejection_reason:
        payloads.append({"status": target_status, "rejection_reason": rejection_reason})
        payloads.append({"status": target_status, "manager_comments": rejection_reason})
        payloads.append({"action": target_status, "manager_comments": rejection_reason})
    payloads.extend([
        {"state": target_status},
        {"approval_status": target_status},
        {"approved": target_status == "approved"}
    ])

    last_res = None
    for payload in payloads:
        for method, url in method_targets:
            last_res = method(
                url,
                json=payload,
                headers=get_headers(),
                timeout=10
            )
            if last_res.status_code not in (200, 201):
                continue
            updated_timesheet = _fetch_timesheet_by_id(timesheet_id)
            current_status = str((updated_timesheet or {}).get("status", "")).lower()
            if current_status == target_status:
                return True, last_res, updated_timesheet

    return False, last_res, _fetch_timesheet_by_id(timesheet_id)


# API route for approving timesheets
@app.route('/manager/timesheets/approve', methods=['POST'])

@role_required(['admin', 'manager', 'hr'])

def api_approve_timesheets(current_user):

    try:

        data = request.get_json(silent=True) or {}
        timesheet_id = data.get('timesheet_id')
        
        if not timesheet_id:
            return jsonify({"success": False, "error": "timesheet_id required"}), 400

        # Get current timesheet to check status
        timesheet = _fetch_timesheet_by_id(timesheet_id)
        if not timesheet:
            return jsonify({"success": False, "error": "Timesheet not found"}), 404

        if str(timesheet.get('status', '')).lower() != 'submitted':
            return jsonify({"success": False, "error": f"Timesheet is already {timesheet.get('status')}"}), 400

        updated, res, updated_timesheet = _update_timesheet_status(timesheet_id, "approved")
        if not updated:
            backend_error = res.text if res is not None else "No response from backend"
            return jsonify({
                "success": False,
                "error": f"Timesheet status update not persisted. Last backend response: {backend_error}"
            }), 500

        return jsonify({
            "success": True,
            "message": "Timesheet approved",
            "timesheet": updated_timesheet,
            "status": "approved"
        }), 200

            

    except Exception as e:

        print(f"ERROR in approve timesheets API: {e}")

        return jsonify({"success": False, "error": str(e)}), 500



# API route for rejecting timesheets

@app.route('/manager/timesheets/reject', methods=['POST'])

@role_required(['admin', 'manager', 'hr'])

def api_reject_timesheets(current_user):

    try:

        data = request.get_json(silent=True) or {}
        timesheet_id = data.get('timesheet_id')
        rejection_reason = data.get('rejection_reason', '')
        
        if not timesheet_id:
            return jsonify({"success": False, "error": "timesheet_id required"}), 400

        timesheet = _fetch_timesheet_by_id(timesheet_id)
        if not timesheet:
            return jsonify({"success": False, "error": "Timesheet not found"}), 404

        if str(timesheet.get('status', '')).lower() != 'submitted':
            return jsonify({"success": False, "error": f"Timesheet is already {timesheet.get('status')}"}), 400

        updated, res, updated_timesheet = _update_timesheet_status(timesheet_id, "rejected", rejection_reason)
        if not updated:
            backend_error = res.text if res is not None else "No response from backend"
            return jsonify({
                "success": False,
                "error": f"Timesheet status update not persisted. Last backend response: {backend_error}"
            }), 500

        return jsonify({
            "success": True,
            "message": "Timesheet rejected",
            "timesheet": updated_timesheet,
            "status": "rejected"
        }), 200

            

    except Exception as e:

        print(f"ERROR in reject timesheets API: {e}")

        return jsonify({"success": False, "error": str(e)}), 500



# API route for updating policies

@app.route('/api/policies/<int:policy_id>', methods=['PUT'])

@role_required(['admin', 'hr'])

def api_update_policy(policy_id):

    try:

        data = request.get_json()

        

        

        res = requests.put(

            f"{BASE_URL}/reports/policies/{policy_id}",

            json=data,

            headers=get_headers()

        )

        

        

        

        

        if res.status_code == 200:

            return jsonify(res.json()), 200

        else:

            return jsonify(res.json()), res.status_code

            

    except Exception as e:

        print(f"ERROR in policy update API: {e}")

        return jsonify({"success": False, "error": str(e)}), 500



import json

import os



# Global projects database that persists across sessions

projects_db = []



# Load projects from file if exists

if os.path.exists('projects.json'):

    with open('projects.json', 'r') as f:

        projects_db = json.load(f)

else:
    pass

# Initialize with empty projects database
def initialize_projects():
    pass



# Initialize projects on app startup

initialize_projects()



# Save projects to file

def save_projects():

    with open('projects.json', 'w') as f:

        json.dump(projects_db, f)



# Projects List (HR sees all, Manager sees assigned, Employee sees assigned)

@app.route('/projects')

@role_required(['admin', 'hr', 'manager', 'employee'])

def projects():

    

    if 'token' not in session:

        

        return redirect(url_for('login'))

    

    # Reload projects from file to get latest data

    global projects_db

    if os.path.exists('projects.json'):

        with open('projects.json', 'r') as f:

            projects_db = json.load(f)

            

    

    user_role = session.get('role')

    user_name = session.get('employee_name')

    

    # Debug session information

    

    

    

    

    

    if user_role == 'hr' or user_role == 'admin':

        # HR and admin see all projects

        projects_to_show = projects_db

        

    elif user_role == 'manager':

        # Manager sees only projects assigned to them

        projects_to_show = [proj for proj in projects_db if proj.get('assigned_manager') == user_name]

        

        

    elif user_role == 'employee':

        # Employee sees only projects they are team members of

        for proj in projects_db:

            team_members = proj.get('team_members', [])
            for member in team_members:
                if user_name in team_members:
                    print(f"DEBUG: MATCH! Employee {user_name} should see project {proj.get('name')}")

        projects_to_show = [proj for proj in projects_db if user_name in proj.get('team_members', [])]
        print(f"DEBUG: Employee {user_name} - showing {len(projects_to_show)} assigned projects")
        print(f"DEBUG: Employee's projects: {[{'id': p.get('id'), 'name': p.get('name'), 'team_members': p.get('team_members')} for p in projects_to_show]}")
    else:
        projects_to_show = []
        print(f"DEBUG: Other role - showing 0 projects")
    return render_template('projects.html', projects=projects_to_show, user_role=user_role)

# HR Project Creation
@app.route('/create_project', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def create_project():
    if 'token' not in session:
        return redirect(url_for('login'))
    if request.method == 'GET':
        # Get all managers for assignment dropdown
        try:
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
            if emp_res.status_code == 401:
                return redirect(url_for('login'))
            employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
            managers = [emp for emp in employees if emp.get('role') == 'manager']     
            return render_template('create_project.html', managers=managers)

        except Exception as e:
            print(f"ERROR: Error fetching managers: {e}")
            import traceback
            traceback.print_exc()
            return render_template('create_project.html', managers=[])
    elif request.method == 'POST':
        try:
            data = request.get_json()
            # Generate unique project ID
            max_id = max([p['id'] for p in projects_db], default=0)
            # Create new project
            new_project = {
                'id': max_id + 1,
                'name': data.get('name'),
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
                'customer_name': data.get('customer_name'),
                'customer_contact': data.get('customer_contact'),
                'customer_phone': data.get('customer_phone'),
                'customer_email': data.get('customer_email'),
                'assigned_manager': data.get('assigned_manager'),
                'created_by': session.get('employee_name'),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'active',
                'team_members': []
            }
            projects_db.append(new_project)
            save_projects()  # Save to file for persistence
            # Send notification to assigned manager (stored in session for now)
            # Note: In real implementation, this would be stored in database
            manager_notification = {
                'employeeName': data.get('assigned_manager'),
                'action': 'project_assigned',
                'project_name': data.get('name'),
                'comments': 'You have been assigned to project: ' + data.get("name"),
                'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                'read': False
            }
            return jsonify({"success": True, "message": "Project created successfully", "redirect": url_for('projects')})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

# Project Details
@app.route('/project_details/<int:project_id>')
@role_required(['admin', 'manager', 'employee'])
def project_details(project_id):
    if 'token' not in session:
        return redirect(url_for('login'))
    # Get current user info
    user_role = session.get('role', '')
    user_name = session.get('name', '')
    # Find project by ID
    project = next((proj for proj in projects_db if proj.get('id') == project_id), None)
    if not project:
        flash("Project not found", "danger")
        if user_role == 'manager':
            return redirect(url_for('manager_projects'))
        else:
            return redirect(url_for('dashboard'))

    # Check if user has access to this project
    if user_role == 'employee' and user_name not in project.get('team_members', []):
        flash("You don't have access to this project", "danger")
        return redirect(url_for('dashboard'))
    # For managers, get available team members
    available_members = []
    if user_role == 'manager':
        try:
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
            if emp_res.status_code == 401:
                return redirect(url_for('login'))
            employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
            available_members = [emp for emp in employees if emp.get('role') not in ['hr', 'manager']]
        except Exception as e:
            print(f"Error fetching team members: {e}")
    return render_template('project_details.html', project=project, available_members=available_members, user_role=user_role)



# Get Employees with Allocation
@app.route('/api/employees_with_allocation')
@role_required(['admin', 'hr', 'manager'])
def api_employees_with_allocation():
    try:
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if emp_res.status_code == 401:
            return jsonify({"success": False, "error": "Unauthorized"}), 401
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    valid_employees = [emp for emp in employees if emp.get('role') == 'employee']
    allocations = {}
    projects_list = {}
    
    for proj in projects_db:
        if proj.get('status') == 'active':
            for member in proj.get('team_members', []):
                name = member if isinstance(member, str) else member.get('name')
                if not name:
                    name = member.get('employee_name') if isinstance(member, dict) else None
                if not name: continue
                
                if isinstance(member, dict):
                    alloc = member.get('allocation') or member.get('allocation_percentage') or member.get('billable_percentage') or member.get('percentage') or 100
                else:
                    alloc = 100
                    
                if name not in allocations:
                    allocations[name] = 0
                    projects_list[name] = []
                
                allocations[name] += int(alloc)
                projects_list[name].append({"project_id": proj.get("id"), "project_name": proj.get("name"), "allocation": int(alloc)})

    result = []
    for emp in valid_employees:
        name = emp.get("name")
        current_alloc = allocations.get(name, 0)
        remaining = max(0, 150 - current_alloc)
        
        if current_alloc >= 150:
            status = "fully_allocated"
        elif current_alloc > 100:
            status = "over_allocated"
        elif current_alloc > 0:
            status = "partially_available"
        else:
            status = "available"
            
        result.append({
            "name": name,
            "employee_name": name,
            "role": emp.get("role"),
            "designation": emp.get("designation", "Employee"),
            "workload": {"total_allocation": current_alloc, "projects": projects_list.get(name, [])},
            "available_capacity": remaining,
            "availability_status": status,
            "allow_over_allocation": True
        })

    return jsonify({"success": True, "employees": result})

# Add Team Members
@app.route('/add_team_members', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def add_team_members():
    if 'token' not in session:
        return redirect(url_for('login'))

    try:
        data = request.get_json()
        project_id = data.get('project_id')
        team_members = data.get('team_members', [])
        print(f"DEBUG: Add team members - Project ID: {project_id}")
        print(f"DEBUG: Add team members - Team members to add: {team_members}")
        print(f"DEBUG: Current projects in database: {len(projects_db)}")

        # Find project
        project = next((proj for proj in projects_db if proj.get('id') == project_id), None)
        if project:
            print(f"DEBUG: Found project: {project.get('name')}")
            print(f"DEBUG: Current team members: {project.get('team_members', [])}")

            # Add team members
            for member_data in team_members:
                new_name = member_data.get('name') if isinstance(member_data, dict) else member_data
                if not new_name:
                    continue

                existing_names = []
                for m in project.setdefault('team_members', []):
                    if isinstance(m, str):
                        existing_names.append(m)
                    elif isinstance(m, dict):
                        existing_names.append(m.get('name', ''))

                if new_name not in existing_names:
                    project['team_members'].append(member_data)
                    print(f"DEBUG: Added team member: {new_name}")
                    # Send notification to team member (stored in session for now)
                    # Note: In real implementation, this would be stored in database
                    member_notification = {
                        'employeeName': new_name,
                        'action': 'project_assigned',
                        'project_name': project.get('name'),
                        'comments': 'You have been assigned to project: ' + str(project.get("name")),
                        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                        'read': False
                    }
                else:
                    print(f"DEBUG: Team member {new_name} already exists in project")
            print(f"DEBUG: Updated team members: {project.get('team_members', [])}")
            save_projects()  # Save to file for persistence
            return jsonify({"success": True, "message": "Team members added successfully"})
        else:
            print(f"DEBUG: Project with ID {project_id} not found")
            return jsonify({"success": False, "error": "Project not found"}), 404

    except Exception as e:
        print(f"ERROR in add_team_members: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500



# Get Project Details
@app.route('/get_project_details/<int:project_id>')
@role_required(['hr', 'manager', 'employee'])
def get_project_details(project_id):
    if 'token' not in session:
        return redirect(url_for('login'))
    
    try:
        # Find project
        project = next((proj for proj in projects_db if proj.get('id') == project_id), None)
        
        if project:
            return jsonify({"success": True, "project": project})
        else:
            return jsonify({"success": False, "error": "Project not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# Payslips Page (Manager + Employee)
@app.route('/payslips')
@role_required(['admin', 'manager', 'employee'])
def payslips():
    if 'token' not in session:
        return redirect(url_for('login'))

    try:
        print(f"DEBUG: Attempting to fetch payslips from {BASE_URL}/payslips")
        
        res = requests.get(f"{BASE_URL}/reports/payslips", headers=get_headers(), timeout=10)
        print(f"DEBUG: Payslips API response status: {res.status_code}")
        print(f"DEBUG: Payslips API response: {res.text}")
        if res.status_code == 401:
            
            return redirect(url_for('login'))

        if res.status_code != 200:
            
            
            return render_template(
                "payslips.html",
                payslips=[],
                error=f"Failed to fetch payslips: API returned {res.status_code} - {res.text[:100]}"
            )
        data = res.json()
        print(f"DEBUG: Payslips API response data: {data}")
        payslips_list = data.get("payslips", [])
        print(f"DEBUG: Number of payslips found: {len(payslips_list)}")
        return render_template(
            "payslips.html",
            payslips=payslips_list
        )
    except requests.exceptions.ConnectionError as e:
        print(f"ERROR: Cannot connect to backend API: {e}")
        print(f"ERROR: Make sure backend server is running at {BASE_URL}")
        return render_template(
            "payslips.html",
            payslips=[],
            error=f"Cannot connect to backend server at {BASE_URL}. Please ensure the backend server is running and accessible."
        )
    except requests.exceptions.Timeout as e:
        print(f"ERROR: Connection timeout to backend API: {e}")
        return render_template(
            "payslips.html",
            payslips=[],
            error=f"Connection timeout to backend server. The server may be busy or not responding."
        )
    except Exception as e:
        print(f"ERROR in payslips route: {e}")
        import traceback
        traceback.print_exc()
        return render_template(
            "payslips.html",
            payslips=[],
            error=f"Error: {str(e)}"
        )


# Update Project
@app.route('/update_project', methods=['POST'])
@role_required(['admin', 'hr'])
def update_project():
    if 'token' not in session:
        return redirect(url_for('login'))

    try:
        data = request.get_json()
        project_id = data.get('id')
        # Find project
        project = next((proj for proj in projects_db if proj.get('id') == project_id), None)
        if project:
            # Update project data
            project.update({
                'name': data.get('name'),
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
                'customer_name': data.get('customer_name'),
                'customer_contact': data.get('customer_contact'),
                'customer_phone': data.get('customer_phone'),
                'customer_email': data.get('customer_email'),
                'assigned_manager': data.get('assigned_manager')
            })
            return jsonify({"success": True, "message": "Project updated successfully"})
        else:
            return jsonify({"success": False, "error": "Project not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Delete Project
@app.route('/delete_project/<int:project_id>', methods=['POST'])
@role_required(['admin', 'hr'])
def delete_project(project_id):

    if 'token' not in session:
        return redirect(url_for('login'))

    try:
        print(f"DEBUG: Deleting project with ID: {project_id}")
        print(f"DEBUG: Current projects in database: {len(projects_db)}")
        # Find project index
        project_index = None
        for i, proj in enumerate(projects_db):
            if proj.get('id') == project_id:
                project_index = i
                break

        if project_index is not None:
            # Remove project from database
            deleted_project = projects_db.pop(project_index)
            print(f"DEBUG: Deleted project: {deleted_project.get('name')}")
            # Save changes to file
            save_projects()
            print(f"DEBUG: Projects saved to file. Remaining projects: {len(projects_db)}")
            return jsonify({"success": True, "message": "Project deleted successfully"})

        else:
            print(f"DEBUG: Project with ID {project_id} not found")
            return jsonify({"success": False, "error": "Project not found"}), 404
    
    except Exception as e:
        print(f"ERROR in delete_project: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/bank-verification')
@role_required(['admin', 'hr'])
def bank_verification():
    try:
        res = requests.get(
            f"{BASE_URL}/bank-details/",
            headers=get_headers(),
            timeout=5
        )
        bank_details = res.json().get("bank_details", []) if res.status_code == 200 else []
    except Exception as e:
        print("ERROR fetching bank details:", e)
        bank_details = []

    return render_template("bank_admin.html", bank_details=bank_details)


@app.route('/admin/bank-details/<int:detail_id>/<action>', methods=['PATCH'])
@role_required(['admin', 'hr'])
def verify_bank_admin(detail_id, action):
    """
    action: approve or reject
    """
    if action not in ['approve', 'reject']:
        return jsonify({"success": False, "error": "Invalid action"}), 400
        
    data = request.get_json() or {}
    try:
        res = requests.patch(
            f"{BASE_URL}/bank-details/{detail_id}/{action}",
            json=data,
            headers=get_headers(),
            timeout=5
        )
        return jsonify(res.json()), res.status_code
    except Exception as e:
        print(f"ERROR {action}ing bank details:", e)
        return jsonify({"success": False, "error": str(e)}), 500


# This file contains the calendar API endpoint code
# Add this to app.py after the add_weekly_timesheet function

@app.route('/api/timesheets/calendar')
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_timesheets_calendar():
    from datetime import datetime
    from calendar import monthrange
    
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    current_user = session.get('employee_name')
    user_role = session.get('role')
    
    # Fetch timesheets
    timesheets = []
    try:
        res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        if res.status_code == 200:
            data = res.json()
            all_timesheets = data.get("timesheets", [])
            if user_role == 'employee':
                timesheets = [t for t in all_timesheets if t.get('employee_name') == current_user]
            else:
                timesheets = all_timesheets
    except Exception as e:
        print("ERROR fetching timesheets:", e)
    
    # Fetch holidays
    holidays = []
    try:
        holiday_res = requests.get(f"{BASE_URL}/holidays?year={year}", headers=get_headers())
        if holiday_res.status_code == 200:
            holidays = holiday_res.json().get("holidays", [])
    except Exception as e:
        print("ERROR fetching holidays:", e)
    
    # Fetch approved leaves
    leaves = []
    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 200:
            all_leaves = leave_res.json().get("leaves", [])
            if user_role == 'employee':
                leaves = [l for l in all_leaves if l.get('employee_name') == current_user and l.get('status') == 'approved']
            else:
                leaves = [l for l in all_leaves if l.get('status') == 'approved']
    except Exception as e:
        print("ERROR fetching leaves:", e)
    
    # Build calendar data
    days = {}
    first_day, last_day = monthrange(year, month)
    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = date_obj.weekday()
        
        status = 'missing'
        label = 'Missing Entry'
        hours = 0
        holiday_info = None
        
        if day_of_week >= 5:
            status = 'weekend'
            label = 'Weekend'
        
        for holiday in holidays:
            holiday_date = str(holiday.get("date", ""))
            # Handle different date formats from backend
            if "-" in holiday_date and len(holiday_date) >= 10:
                # Format: YYYY-MM-DD
                holiday_date_formatted = holiday_date[:10]
            else:
                # Format: Thu, 01 Jan 2026 00:00:00 GMT
                try:
                    from datetime import datetime
                    dt = datetime.strptime(holiday_date.strip(), "%a, %d %b %Y %H:%M:%S %Z")
                    holiday_date_formatted = dt.strftime("%Y-%m-%d")
                except:
                    try:
                        # Try format: Thu, 01 Jan
                        dt = datetime.strptime(holiday_date.strip(), "%a, %d %b")
                        holiday_date_formatted = dt.strftime("%Y-%m-%d")
                    except:
                        holiday_date_formatted = holiday_date
            
            if holiday_date_formatted == date_str:
                status = 'holiday'
                label = 'Holiday'
                holiday_info = holiday
                break
        
        for leave in leaves:
            try:
                start_date = datetime.strptime(leave.get('start_date'), "%Y-%m-%d")
                end_date = datetime.strptime(leave.get('end_date'), "%Y-%m-%d")
                if start_date <= date_obj <= end_date:
                    status = 'leave'
                    label = 'Approved Leave'
                    break
            except:
                continue
        
        if status not in ['weekend', 'holiday', 'leave']:
            for ts in timesheets:
                if ts.get('start_date', '').startswith(date_str):
                    status = 'completed'
                    label = 'Completed'
                    break
        
        # Only set future status if not already a holiday, leave, or weekend
        if date_obj > datetime.now() and status not in ['holiday', 'leave', 'weekend']:
            status = 'future'
            label = 'Future'
        
        days[date_str] = {
            'status': status,
            'label': label,
            'hours': hours,
            'holiday': holiday_info
        }
    
    return jsonify({
        'success': True,
        'days': days
    })


@app.route('/api/timesheets/day')
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_timesheets_day():
    from datetime import datetime
    
    date_str = request.args.get('date')
    current_user = session.get('employee_name')
    user_role = session.get('role')
    
    # Parse date
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = date_obj.weekday()
    except:
        return jsonify({'success': False, 'error': 'Invalid date format'}), 400
    
    # Determine status
    status = 'missing'
    label = 'Missing Entry'
    holiday_info = None
    entries = []
    can_add_or_update = True
    
    # Check if weekend
    if day_of_week >= 5:
        status = 'weekend'
        label = 'Weekend'
        can_add_or_update = False
    
    # Fetch holidays for the year
    year = date_obj.year
    holidays = []
    try:
        holiday_res = requests.get(f"{BASE_URL}/holidays?year={year}", headers=get_headers())
        if holiday_res.status_code == 200:
            holidays = holiday_res.json().get("holidays", [])
    except Exception as e:
        print("ERROR fetching holidays:", e)
    
    # Check if holiday
    for holiday in holidays:
        holiday_date = str(holiday.get("date", ""))
        if "-" in holiday_date and len(holiday_date) >= 10:
            holiday_date_formatted = holiday_date[:10]
        else:
            try:
                dt = datetime.strptime(holiday_date.strip(), "%a, %d %b %Y %H:%M:%S %Z")
                holiday_date_formatted = dt.strftime("%Y-%m-%d")
            except:
                try:
                    dt = datetime.strptime(holiday_date.strip(), "%a, %d %b")
                    holiday_date_formatted = dt.strftime("%Y-%m-%d")
                except:
                    holiday_date_formatted = holiday_date
        
        if holiday_date_formatted == date_str:
            status = 'holiday'
            label = 'Holiday'
            holiday_info = holiday
            can_add_or_update = False
            break
    
    # Fetch approved leaves
    leaves = []
    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 200:
            all_leaves = leave_res.json().get("leaves", [])
            if user_role == 'employee':
                leaves = [l for l in all_leaves if l.get('employee_name') == current_user and l.get('status') == 'approved']
            else:
                leaves = [l for l in all_leaves if l.get('status') == 'approved']
    except Exception as e:
        print("ERROR fetching leaves:", e)
    
    # Check if approved leave
    for leave in leaves:
        try:
            start_date = datetime.strptime(leave.get('start_date'), "%Y-%m-%d")
            end_date = datetime.strptime(leave.get('end_date'), "%Y-%m-%d")
            if start_date <= date_obj <= end_date:
                status = 'leave'
                label = 'Approved Leave'
                can_add_or_update = False
                break
        except:
            continue
    
    # Fetch timesheets for the date
    if status not in ['weekend', 'holiday', 'leave']:
        try:
            res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
            if res.status_code == 200:
                data = res.json()
                all_timesheets = data.get("timesheets", [])
                if user_role == 'employee':
                    timesheets = [t for t in all_timesheets if t.get('employee_name') == current_user]
                else:
                    timesheets = all_timesheets
                
                # Filter for the specific date
                for ts in timesheets:
                    if ts.get('start_date', '').startswith(date_str):
                        entries.append(ts)
                
                if entries:
                    status = 'completed'
                    label = 'Completed'
                    can_add_or_update = True
        except Exception as e:
            print("ERROR fetching timesheets:", e)
    
    # Check if future date
    if date_obj > datetime.now():
        can_add_or_update = False
    
    return jsonify({
        'success': True,
        'status': status,
        'label': label,
        'holiday': holiday_info,
        'entries': entries,
        'can_add_or_update': can_add_or_update
    })


# --- ASSET MANAGEMENT ROUTES ---

@app.route('/assets')
@role_required(['admin', 'hr'])
def assets():
    return render_template('assets.html')

@app.route('/assets/agreement/<int:asset_id>')
@token_required
def asset_agreement_page(current_user, asset_id):
    """Render the digital signature agreement page."""
    return render_template('agreement.html', asset_id=asset_id)

# Centralized helper for backend proxying
def proxy_to_backend(method, path_prefix, path_suffix="", **kwargs):
    """
    Tries multiple backend endpoint variations (devices/assets, with/without prefixes and slashes).
    Returns (response, last_error_message).
    """
    # The user confirmed the prefix is '/devices'
    endpoints = [
        f"/devices{path_suffix}",
        f"/devices/{path_suffix}".replace("//", "/")
    ]
    # Keep unique ones
    endpoints = list(dict.fromkeys(endpoints))
    
    res = None
    last_error = "No connectivity to backend"
    
    print(f"DEBUG: Proxying {method} {path_suffix} to {BASE_URL}. Endpoints: {endpoints}")
    for i, ep in enumerate(endpoints):
        url = f"{BASE_URL}{ep}"
        try:
            print(f"DEBUG: Attempt {i+1}: {method} {url}")
            if method == 'GET':
                test_res = requests.get(url, headers=get_headers(), timeout=15)
            elif method == 'POST':
                test_res = requests.post(url, timeout=30, **kwargs)
            elif method == 'PATCH':
                test_res = requests.patch(url, timeout=30, **kwargs)
            elif method == 'DELETE':
                test_res = requests.delete(url, timeout=30, **kwargs)
            else:
                return None, f"Unsupported method: {method}"
            
            print(f"DEBUG: Attempt {i+1} Response: {test_res.status_code}")
            if test_res.status_code in [200, 201]:
                return test_res, None
            res = test_res
            last_error = f"Status {test_res.status_code}: {test_res.text[:100]}"
        except Exception as e:
            print(f"DEBUG: Attempt {i+1} Exception: {str(e)}")
            last_error = f"Connection failed to {url}: {str(e)}"
            continue
            
    return res, last_error

@app.route('/api/assets', methods=['GET', 'POST'])
@app.route('/api/assets/', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def api_assets_handler():
    if request.method == 'GET':
        res, err = proxy_to_backend('GET', '')
        if res and res.status_code == 200:
            data = res.json()
            items = data.get("assets") or data.get("devices") or []
            return jsonify({"success": True, "assets": items})
        return jsonify({"success": False, "error": res.text if res else f"Backend unreachable: {err}"}), res.status_code if res else 500

    # POST - Create Asset
    try:
        payload = request.form.to_dict() if request.files else (request.get_json() or {})
        
        # Capture all details from the form/JSON payload
        create_data = {
            "device_name": payload.get("device_name"),
            "device_type": payload.get("device_type"),
            "serial_number": payload.get("serial_number"),
            "brand": payload.get("device_name"), # Fallback for backend systems using brand
            "model": payload.get("device_type"), # Fallback for backend systems using model
            "status": "Available"
        }
        
        # Step 1: Create Device (JSON)
        res, err = proxy_to_backend('POST', '', json=create_data, headers=get_headers())
        
        if not res or res.status_code not in [200, 201]:
            return jsonify({"success": False, "error": res.text if res else f"Creation failed: {err}"}), res.status_code if res else 500
        
        data = res.json()
        device_id = data.get("device_id") or data.get("id")
        
        # Step 2: Upload Image if present
        if request.files and device_id:
            files_to_upload = []
            for key in request.files:
                for file in request.files.getlist(key):
                    files_to_upload.append(('image', (file.filename, file.read(), file.content_type)))
            
            if files_to_upload:
                proxy_to_backend('POST', '', path_suffix=f"/{device_id}/upload-image", 
                                 files=[files_to_upload[0]], 
                                 headers=get_headers(exclude_content_type=True))

        return jsonify({"success": True, "asset": {"id": device_id, "brand": create_data["brand"], "model": create_data["model"]}})
        
    except Exception as e:
        return jsonify({"success": False, "error": f"Internal proxy error: {str(e)}"}), 500

@app.route('/api/assets/<int:asset_id>/assign', methods=['POST'])
@role_required(['admin', 'hr'])
def api_assign_asset(asset_id):
    try:
        data = request.get_json() or {}
        # If frontend sends employee_id but backend wants employee_name, map it here
        if 'employee_id' in data and 'employee_name' not in data:
            data['employee_name'] = data['employee_id']
            
        res, err = proxy_to_backend('POST', '', path_suffix=f"/{asset_id}/assign", json=data, headers=get_headers())
        
        if res and res.status_code == 200:
            return jsonify({"success": True, "message": "Asset assigned successfully"})
        return jsonify({"success": False, "error": res.text if res else f"Assignment failed: {err}"}), res.status_code if res else 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/assets/<int:asset_id>')
@role_required(['admin', 'hr'])
def api_get_asset_details(asset_id):
    try:
        res, err = proxy_to_backend('GET', '', path_suffix=f"/{asset_id}")
        if res and res.status_code == 200:
            return jsonify({"success": True, "asset": res.json()})
        return jsonify({"success": False, "error": res.text if res else f"Details fetch failed: {err}"}), res.status_code if res else 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/assets/<int:asset_id>/history')
@role_required(['admin', 'hr'])
def api_get_asset_history(asset_id):
    try:
        res, err = proxy_to_backend('GET', '', path_suffix=f"/{asset_id}/history")
        if res and res.status_code == 200:
            return jsonify({"success": True, "history": res.json()})
        return jsonify({"success": False, "error": res.text if res else f"History fetch failed: {err}"}), res.status_code if res else 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/employees')
@role_required(['admin', 'hr', 'manager'])
def api_get_employees():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "employees": res.json().get("employees", [])})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/assets/<int:asset_id>', methods=['DELETE'])
@role_required(['admin', 'hr'])
def api_delete_asset(asset_id):
    """Delete an asset from inventory."""
    res, err = proxy_to_backend('DELETE', '', path_suffix=f"/{asset_id}", headers=get_headers())
    if res and res.status_code in [200, 204]:
        return jsonify({"success": True, "message": "Asset deleted successfully"})
    return jsonify({"success": False, "error": res.text if res else f"Delete failed: {err}"}), res.status_code if res else 500

@app.route('/api/assets/<int:asset_id>/acceptance-status', methods=['GET'])
@token_required
def api_asset_acceptance_status(asset_id):
    """Proxy for device acceptance status."""
    res, err = proxy_to_backend('GET', '', path_suffix=f"/{asset_id}/acceptance-status", headers=get_headers())
    if res and res.status_code == 200:
        return jsonify(res.json())
    return jsonify({"success": False, "error": res.text if res else f"Status fetch failed: {err}"}), res.status_code if res else 500

@app.route('/api/assets/<int:asset_id>/agreement', methods=['GET'])
@token_required
def api_asset_agreement(asset_id):
    """Proxy for fetching the personalised agreement document."""
    res, err = proxy_to_backend('GET', '', path_suffix=f"/{asset_id}/agreement", headers=get_headers())
    if res and res.status_code == 200:
        return jsonify(res.json())
    return jsonify({"success": False, "error": res.text if res else f"Agreement fetch failed: {err}"}), res.status_code if res else 500

@app.route('/api/assets/<int:asset_id>/accept', methods=['POST'])
@token_required
def api_asset_accept(asset_id):
    """Proxy for submitting digital signature / accepting agreement."""
    # Transform Flask files to Requests-compatible format
    files = {}
    for key, file in request.files.items():
        files[key] = (file.filename, file.read(), file.content_type)
    
    # Must exclude Content-Type header to let 'requests' set the multipart boundary
    res, err = proxy_to_backend('POST', '', path_suffix=f"/{asset_id}/accept", 
                                files=files, data=request.form, 
                                headers=get_headers(exclude_content_type=True))
    
    if res and res.status_code == 200:
        return jsonify(res.json())
    return jsonify({"success": False, "error": res.text if res else f"Acceptance failed: {err}"}), res.status_code if res else 500

@app.route('/api/assets/my-devices', methods=['GET'])
@token_required
def api_my_devices(current_user):
    """Proxy for fetching devices assigned to the current user."""
    res, err = proxy_to_backend('GET', '', path_suffix="/my-devices", headers=get_headers())
    if res and res.status_code == 200:
        return jsonify(res.json())
    return jsonify({"success": False, "error": res.text if res else f"Fetch failed: {err}"}), res.status_code if res else 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
