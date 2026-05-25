import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from app.utils import BASE_URL, get_headers, role_required, fetch_leave_balance_helper
from app.ui_constants import UI_LABELS

employees_bp = Blueprint('employees', __name__)

@employees_bp.route('/employees')
@role_required(['admin', 'hr', 'manager'])
def employee_list():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('auth.login'))
        data = res.json()
        employees = data.get("employees", [])
        
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leaves = []
        if leaves_res.status_code == 200:
            leaves_data = leaves_res.json()
            leaves = leaves_data.get("leaves", [])

        employees_with_balance = []
        for emp in employees:
            if 'role' not in emp:
                emp['role'] = ''

            emp_name = emp.get("name")
            emp['leave_balance'] = 0
            balance_data = fetch_leave_balance_helper(emp_name)
            
            if balance_data:
                summary = balance_data.get("summary", {})
                balances = balance_data.get("balances", [])
                
                if summary.get("remaining_leaves") is not None:
                    emp['leave_balance'] = summary.get("remaining_leaves")
                elif summary.get("total_leaves") is not None and summary.get("used_leaves") is not None:
                    emp['leave_balance'] = summary.get("total_leaves") - summary.get("used_leaves")
                elif balances:
                    emp['leave_balance'] = sum(b.get("remaining_leaves", 0) for b in balances if isinstance(b, dict))
            else:
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

@employees_bp.route('/add', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def add_employee():
    if request.method == 'GET':
        return render_template('add_employee.html')
    
    form = request.form
    payload = {
        "name": form['name'],
        "email": form['email'],
        "date_of_joining": form['date_of_joining'],
        "role": form.get('role', 'employee'),
        "date_of_birth": form.get('date_of_birth', ''),
        "phone": form.get('phone', ''),
    }
    files = {}
    if 'pdf_file' in request.files:
        pdf = request.files['pdf_file']
        if pdf.filename:
            files['pdf_file'] = (pdf.filename, pdf.read(), pdf.mimetype)
    if 'docx_file' in request.files:
        docx = request.files['docx_file']
        if docx.filename:
            files['docx_file'] = (docx.filename, docx.read(), docx.mimetype)
    
    try:
        if files:
            res = requests.post(f"{BASE_URL}/employees", data=payload, files=files, headers=get_headers())
        else:
            res = requests.post(f"{BASE_URL}/employees", json=payload, headers=get_headers())

        if res.status_code == 201:
            flash(UI_LABELS['EMPLOYEE_ADDED_SUCCESS'], "success")
        else:
            flash("Failed to add employee!", "danger")
    except Exception as e:
        flash("Server error occurred!", "danger")

    return redirect(url_for('employees.employee_list'))

@employees_bp.route('/delete/<int:id>', methods=['POST'])
@role_required(['admin', 'hr'])
def delete_employee(id):
    requests.delete(f"{BASE_URL}/employees/{id}", headers=get_headers())
    return redirect(url_for('employees.employee_list'))

@employees_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def edit_employee(id):
    if request.method == 'POST':
        form = request.form
        files = request.files

        # ── Basic employee fields (name, email, phone, dates, document) ──────
        payload = {
            "name": form['name'],
            "email": form['email'],
            "phone": form['phone'],
            "date_of_joining": form['date_of_joining'],
            "date_of_birth": form.get('date_of_birth', '')
        }

        file_data = {}
        if 'document' in files:
            doc = files['document']
            if doc.filename != "":
                file_data['document'] = (doc.filename, doc.read(), doc.mimetype)

        # ── Role update — must go to the dedicated /auth/users/<user_id>/role ─
        # The employee table has NO role column; role lives in the users table.
        # Sending role to PATCH /employees/<id> is silently ignored by the backend.
        new_role = form.get('role', '').strip()
        role_changed = False
        role_error = None

        if new_role:
            try:
                # 1. Look up the user record that owns this employee
                users_res = requests.get(
                    f"{BASE_URL}/auth/users", headers=get_headers(), timeout=10
                )
                # 2. Find current employee name to match against users table
                emp_res = requests.get(
                    f"{BASE_URL}/employees/{id}", headers=get_headers(), timeout=5
                )
                current_emp_name = None
                if emp_res.status_code == 200:
                    current_emp_name = emp_res.json().get("employee", {}).get("name")

                if users_res.status_code == 200 and current_emp_name:
                    all_users = users_res.json().get("users", [])
                    matched_user = next(
                        (u for u in all_users if u.get("employee_name") == current_emp_name),
                        None
                    )

                    if matched_user:
                        current_role = matched_user.get("role", "")
                        if current_role == new_role:
                            role_changed = True  # Same role — nothing to do
                        else:
                            user_id = matched_user["id"]
                            role_res = requests.patch(
                                f"{BASE_URL}/auth/users/{user_id}/role",
                                json={"role": new_role},
                                headers=get_headers(),
                                timeout=10
                            )
                            if role_res.status_code == 200:
                                role_changed = True
                                # Backend also renames the employee_name prefix;
                                # update payload so the basic-info save uses the new name
                                new_username = role_res.json().get("new_username")
                                if new_username:
                                    payload["name"] = new_username
                            else:
                                role_error = role_res.json().get(
                                    "error", f"Role update failed (HTTP {role_res.status_code})"
                                )
                    else:
                        role_error = "No user account found for this employee. Role not changed."
                else:
                    role_error = f"Could not retrieve user list (HTTP {users_res.status_code})."

            except Exception as e:
                role_error = f"Role update error: {str(e)}"

        # ── Save basic employee info (PATCH → PUT → POST fallback) ────────────
        basic_ok = False
        try:
            if file_data:
                res = requests.patch(f"{BASE_URL}/employees/{id}", data=payload,
                                     files=file_data, headers=get_headers())
            else:
                res = requests.patch(f"{BASE_URL}/employees/{id}", json=payload,
                                     headers=get_headers())

            if res.status_code == 405:
                res = (requests.put(f"{BASE_URL}/employees/{id}", data=payload,
                                    files=file_data, headers=get_headers())
                       if file_data else
                       requests.put(f"{BASE_URL}/employees/{id}", json=payload,
                                    headers=get_headers()))

            if res.status_code == 405:
                res = (requests.post(f"{BASE_URL}/employees/{id}", data=payload,
                                     files=file_data, headers=get_headers())
                       if file_data else
                       requests.post(f"{BASE_URL}/employees/{id}", json=payload,
                                     headers=get_headers()))

            basic_ok = (res.status_code == 200)
        except Exception as e:
            flash(f"Error updating employee details: {str(e)}", "danger")
            return redirect(url_for('employees.employee_list'))

        # ── Flash accurate result ─────────────────────────────────────────────
        if role_error:
            flash(f"Role update failed: {role_error}", "danger")
        elif new_role and role_changed and basic_ok:
            flash(f"{UI_LABELS['EMPLOYEE_UPDATED_SUCCESS']} (role updated to {new_role.upper()})", "success")
        elif new_role and role_changed:
            flash(f"Role updated to {new_role.upper()} successfully.", "success")
        elif basic_ok:
            flash(UI_LABELS['EMPLOYEE_UPDATED_SUCCESS'], "success")
        else:
            flash(f"Failed to update employee: {res.text}", "danger")

        return redirect(url_for('employees.employee_list'))

    else:
        # ── GET: fetch employee, then overlay real role from users table ───────
        res = requests.get(f"{BASE_URL}/employees/{id}", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('auth.login'))

        employee = res.json().get("employee", {})

        # The employee table has no 'role' column — get the real role from users
        try:
            users_res = requests.get(
                f"{BASE_URL}/auth/users", headers=get_headers(), timeout=10
            )
            if users_res.status_code == 200:
                all_users = users_res.json().get("users", [])
                emp_name = employee.get("name", "")
                matched = next(
                    (u for u in all_users if u.get("employee_name") == emp_name),
                    None
                )
                if matched:
                    employee["role"] = matched.get("role", "employee")
                    employee["user_id"] = matched.get("id")
        except Exception as e:
            print(f"Could not fetch user role for employee {id}: {e}")

        return render_template('edit_employee.html', employee=employee)

@employees_bp.route('/profile/<employee_name>')
@role_required(['hr', 'admin'])
def view_profile(employee_name):
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    headers = get_headers()
    # Fetch profile data from backend
    res = requests.get(f"{BASE_URL}/profile/{employee_name}", headers=headers)
    
    employee = {}
    documents = {}
    
    if res.status_code == 200:
        data = res.json()
        employee = data.get("employee", {})
        documents = data.get("documents") or {}
    else:
        # Fallback: Try to find employee in the main list
        list_res = requests.get(f"{BASE_URL}/employees", headers=headers)
        if list_res.status_code == 200:
            employees = list_res.json().get("employees", [])
            employee = next((e for e in employees if e.get("name") == employee_name), None)
            
        if not employee:
            flash("Employee profile not found", "danger")
            return redirect(url_for('employees.employee_list'))
    
    # Calculate progress
    doc_keys = ["pan_card", "aadhar_card", "tenth_cert", "twelfth_cert", "graduation_cert", "postgrad_cert"]
    uploaded = sum(1 for key in doc_keys if documents.get(key) and str(documents.get(key)).strip())
    percent = int((uploaded / len(doc_keys)) * 100) if doc_keys else 0
    
    # Get leave balance
    summary = {'remaining_leaves': 0}
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        summary = balance_data.get("summary", {})
        
    # Get bank details
    bank_details = {}
    try:
        bank_res = requests.get(f"{BASE_URL}/bank-details/", headers=headers, timeout=5)
        if bank_res.status_code == 200:
            bd_list = bank_res.json().get("bank_details", [])
            if isinstance(bd_list, list):
                bank_details = next((b for b in bd_list if b.get("employee_name") == employee_name), {})
    except: pass
    
    is_own_profile = employee.get('name') == session.get('employee_name')

    return render_template(
        "profile.html",
        employee=employee,
        documents=documents,
        percent=percent,
        summary=summary,
        bank_details=bank_details,
        is_hr_view=not is_own_profile,
        is_own_profile=is_own_profile,
        BASE_URL=BASE_URL,
    )

@employees_bp.route('/api/employees')
@role_required(['admin', 'hr', 'manager'])
def api_get_employees():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            data = res.json()
            employees = data.get("employees", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            return jsonify({"success": True, "employees": employees})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
