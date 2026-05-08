import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash
from app.utils import BASE_URL, get_headers, role_required, fetch_leave_balance_helper

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
            flash("Employee added successfully!", "success")
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
        payload = {
            "name": form['name'],
            "email": form['email'],
            "phone": form['phone'],
            "date_of_joining": form['date_of_joining'],
            "date_of_birth": form.get('date_of_birth', '')
        }
        if 'role' in form and form['role']:
            payload['role'] = form['role']
        
        file_data = {}
        if 'document' in files:
            doc = files['document']
            if doc.filename != "":
                file_data['document'] = (doc.filename, doc.read(), doc.mimetype)

        try:
            if file_data:
                res = requests.patch(f"{BASE_URL}/employees/{id}", data=payload, files=file_data, headers=get_headers())
            else:
                res = requests.patch(f"{BASE_URL}/employees/{id}", json=payload, headers=get_headers())
            
            if res.status_code == 405:
                if file_data:
                    res = requests.put(f"{BASE_URL}/employees/{id}", data=payload, files=file_data, headers=get_headers())
                else:
                    res = requests.put(f"{BASE_URL}/employees/{id}", json=payload, headers=get_headers())
            
            if res.status_code == 405:
                if file_data:
                    res = requests.post(f"{BASE_URL}/employees/{id}", data=payload, files=file_data, headers=get_headers())
                else:
                    res = requests.post(f"{BASE_URL}/employees/{id}", json=payload, headers=get_headers())
            
            if res.status_code == 200:
                flash("Employee updated successfully!", "success")
            else:
                flash(f"Failed to update employee: {res.text}", "danger")
        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "danger")

        return redirect(url_for('employees.employee_list'))

    else:
        res = requests.get(f"{BASE_URL}/employees/{id}", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('auth.login'))
        data = res.json()
        return render_template('edit_employee.html', employee=data.get("employee"))
