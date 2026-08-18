import requests
from urllib.parse import quote, unquote
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from app.utils import BASE_URL, get_headers, role_required, fetch_leave_balance_helper
from app.ui_constants import UI_LABELS
from app.routes.user import (
    _fetch_employee_documents,
    _document_view_urls,
    DOC_TYPES,
)
from app.api_helpers import (
    names_match,
    normalize_person,
    normalize_people_list,
    extract_list,
    extract_item,
    parse_profile_response,
    person_system_name,
    pick,
)

employees_bp = Blueprint('employees', __name__)


def _find_employee_record(employee_name, headers):
    """Find employee from list API with flexible name matching."""
    if not employee_name:
        return {}
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=headers, timeout=10)
        if res.status_code == 200:
            for emp in extract_list(res.json(), 'employees', 'data'):
                if names_match(person_system_name(emp), employee_name):
                    return normalize_person(emp)
    except Exception as e:
        print(f"Employee list lookup failed: {e}")
    return {}

@employees_bp.route('/employees')
@role_required(['admin', 'hr', 'manager'])
def employee_list():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('auth.login'))
        employees = normalize_people_list(extract_list(res.json(), 'employees', 'data'))
        
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leaves = []
        if leaves_res.status_code == 200:
            leaves_data = leaves_res.json()
            leaves = extract_list(leaves_data, 'leaves', 'data')

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
                    if names_match(leave.get("employee_name"), emp_name) and leave.get("status") == "approved":
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
    raw_payload = {
        "name": form.get('name', '').strip(),
        "email": form.get('email', '').strip(),
        "date_of_joining": form.get('date_of_joining', '').strip(),
        "role": form.get('role', 'employee').strip(),
        "date_of_birth": form.get('date_of_birth', '').strip(),
        "phone": form.get('phone', '').strip(),
        "designation": form.get('designation', '').strip(),
        "department": form.get('department', '').strip(),
        "gender": form.get("gender", '').strip(),
        "employment_type": form.get("employment_type", '').strip(),
        "reporting_manager": form.get("reporting_manager", '').strip(),
        "address": form.get("address", '').strip(),
    }
    # Only send non-empty fields to avoid parsing errors in backend
    payload = {k: v for k, v in raw_payload.items() if v}
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
            flash(f"Failed to add employee! Error: {res.text}", "danger")
    except Exception as e:
        flash(f"Server error occurred! {str(e)}", "danger")

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
            "date_of_birth": form.get('date_of_birth', ''),
            "designation": form.get('designation', ''),
            "department": form.get('department', ''),
            "gender":form.get("gender",''),
            "employment_type":form.get("employment_type",''),
            "reporting_manager":form.get("reporting_manager",''),
            "address":form.get("address",''),
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

        current_emp_name = None
        if new_role and session.get('role') == 'admin':
            try:
                emp_res = requests.get(
                    f"{BASE_URL}/employees/{id}", headers=get_headers(), timeout=5
                )
                if emp_res.status_code == 200:
                    current_emp_name = person_system_name(
                        extract_item(emp_res.json(), 'employee', 'data')
                    ) or payload.get('name')

                role_res = requests.put(
                    f"{BASE_URL}/employees/{id}/role",
                    json={"role": new_role},
                    headers=get_headers(),
                    timeout=15,
                )
                body = role_res.json() if role_res.content else {}
                if role_res.status_code == 200 and body.get('success') is not False:
                    role_changed = True
                    new_name = pick(body.get('data') or {}, 'new_id', 'new_username', 'employee_name')
                    if new_name:
                        payload['name'] = new_name
                    if names_match(current_emp_name or payload.get('name'), session.get('employee_name')):
                        session['role'] = new_role.lower()
                        if new_name:
                            session['employee_name'] = new_name
                else:
                    role_error = body.get(
                        'error', f"Role update failed (HTTP {role_res.status_code})"
                    )
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

        employee = normalize_person(extract_item(res.json(), 'employee', 'data'))
        if not employee.get('role'):
            try:
                users_res = requests.get(
                    f"{BASE_URL}/auth/users", headers=get_headers(), timeout=10
                )
                if users_res.status_code == 200:
                    emp_name = person_system_name(employee)
                    matched = next(
                        (u for u in extract_list(users_res.json(), 'users', 'data')
                         if names_match(u.get('employee_name'), emp_name)),
                        None,
                    )
                    if matched:
                        employee['role'] = matched.get('role', 'employee')
                        employee['user_id'] = matched.get('id')
            except Exception as e:
                print(f"Could not fetch user role for employee {id}: {e}")

        return render_template('edit_employee.html', employee=employee)

@employees_bp.route('/profile/<path:employee_name>')
@role_required(['hr', 'admin'])
def view_profile(employee_name):
    if 'token' not in session:
        return redirect(url_for('auth.login'))

    employee_name = unquote(employee_name).strip()
    headers = get_headers()

    employee = {}
    documents = {}

    # Primary: dedicated profile endpoint (returns data.profile)
    try:
        profile_url = f"{BASE_URL}/profile/{quote(employee_name, safe='')}"
        res = requests.get(profile_url, headers=headers, timeout=10)
        if res.status_code == 200:
            employee, documents = parse_profile_response(res.json())
        elif res.status_code == 404:
            flash(f"Team member '{employee_name}' was not found.", "warning")
        else:
            print(f"Profile API HTTP {res.status_code}: {res.text[:200]}")
    except Exception as e:
        print(f"Profile API error: {e}")

    # Fallback: employees list (exact / prefixed name match)
    if not employee or not employee.get("email"):
        fallback = _find_employee_record(employee_name, headers)
        if fallback:
            employee = {**fallback, **{k: v for k, v in employee.items() if v is not None and v != ''}}

    # Enrich via single-employee endpoint when we have an id
    emp_id = employee.get("id")
    if emp_id:
        try:
            detail_res = requests.get(
                f"{BASE_URL}/employees/{emp_id}", headers=headers, timeout=10
            )
            if detail_res.status_code == 200:
                detail = normalize_person(extract_item(detail_res.json(), 'employee', 'data'))
                if detail:
                    employee = {**employee, **detail}
        except Exception as e:
            print(f"Employee detail fetch failed: {e}")

    if not employee:
        flash("Employee profile not found", "danger")
        return redirect(url_for('employees.employee_list'))

    display_name = employee.get("name") or employee_name

    # Load documents for the viewed employee (HR/admin)
    if not documents:
        documents = _fetch_employee_documents(display_name, headers)
    document_view_urls = _document_view_urls(documents)

    uploaded = sum(1 for key in DOC_TYPES if documents.get(key) and str(documents.get(key)).strip())
    percent = int((uploaded / len(DOC_TYPES)) * 100) if DOC_TYPES else 0

    # Leave balance — prefer profile fields, then helper API
    summary = {
        'remaining_leaves': employee.get('remaining_leaves') or 0,
        'total_leaves': employee.get('total_leaves') or 0,
        'used_leaves': employee.get('used_leaves') or 0,
    }
    balance_data = fetch_leave_balance_helper(display_name)
    if balance_data:
        summary = balance_data.get("summary", summary)
        
    # Get bank details
    bank_details = {}
    try:
        bank_res = requests.get(f"{BASE_URL}/bank-details/", headers=headers, timeout=5)
        if bank_res.status_code == 200:
            bd_list = bank_res.json().get("bank_details", [])
            if isinstance(bd_list, list):
                bank_details = next(
                    (b for b in bd_list if names_match(b.get("employee_name"), display_name)),
                    {},
                )
    except Exception:
        pass

    is_own_profile = names_match(employee.get('name'), session.get('employee_name'))

    # ── Assets (via new /devices/employee/<name> route) ──────────────────────
    assets = []
    try:
        assets_res = requests.get(
            f"{BASE_URL}/devices/employee/{quote(display_name, safe='')}",
            headers=headers, timeout=5
        )
        if assets_res.status_code == 200:
            assets = assets_res.json().get('devices', [])
    except Exception as e:
        print(f"Assets fetch failed: {e}")

    # ── Employee Projects ─────────────────────────────────────────────────────
    employee_projects = []
    try:
        proj_res = requests.get(
            f"{BASE_URL}/projects/employee/{quote(display_name, safe='')}",
            headers=headers, timeout=5
        )
        if proj_res.status_code == 200:
            employee_projects = proj_res.json().get('projects', [])
    except Exception as e:
        print(f"Projects fetch failed: {e}")

    # ── Active Counts: Leave / Reimbursement / Helpdesk ──────────────────────
    active_leave_count = 0
    try:
        leave_res = requests.get(
            f"{BASE_URL}/leaves",
            headers=headers,
            params={'employee_name': display_name, 'status': 'pending'},
            timeout=5
        )
        if leave_res.status_code == 200:
            leaves_data = leave_res.json().get('leaves', leave_res.json().get('data', []))
            active_leave_count = len([l for l in leaves_data if isinstance(l, dict)])
    except Exception as e:
        print(f"Leave count fetch failed: {e}")

    active_reimbursement_count = 0
    try:
        reimb_res = requests.get(
            f"{BASE_URL}/reimbursements",
            headers=headers,
            params={'employee_name': display_name, 'status': 'pending'},
            timeout=5
        )
        if reimb_res.status_code == 200:
            reimb_data = reimb_res.json().get('reimbursements', reimb_res.json().get('data', []))
            active_reimbursement_count = len([r for r in reimb_data if isinstance(r, dict)])
    except Exception as e:
        print(f"Reimbursement count fetch failed: {e}")

    active_helpdesk_count = 0
    try:
        helpdesk_res = requests.get(
            f"{BASE_URL}/helpdesk",
            headers=headers,
            params={'employee_name': display_name, 'status': 'open'},
            timeout=5
        )
        if helpdesk_res.status_code == 200:
            hd_data = helpdesk_res.json().get('tickets', helpdesk_res.json().get('data', []))
            active_helpdesk_count = len([t for t in hd_data if isinstance(t, dict)])
    except Exception as e:
        print(f"Helpdesk count fetch failed: {e}")

    return render_template(
        "profile.html",
        employee=employee,
        documents=documents,
        document_view_urls=document_view_urls,
        percent=percent,
        uploaded_doc_count=uploaded,
        summary=summary,
        bank_details=bank_details,
        is_hr_view=not is_own_profile,
        is_own_profile=is_own_profile,
        assets=assets,
        employee_projects=employee_projects,
        active_leave_count=active_leave_count,
        active_reimbursement_count=active_reimbursement_count,
        active_helpdesk_count=active_helpdesk_count,
        BASE_URL=BASE_URL,
    )

@employees_bp.route('/api/employees')
@role_required(['admin', 'hr', 'manager', 'employee'])
def api_get_employees():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            data = res.json()
            employees = normalize_people_list(extract_list(data, 'employees', 'data'))
            return jsonify({"success": True, "employees": employees})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
