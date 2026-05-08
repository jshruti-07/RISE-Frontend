import requests
from flask import Blueprint, render_template, redirect, url_for, session, request, jsonify
from app.utils import BASE_URL, get_headers, fetch_leave_balance_helper

user_bp = Blueprint('user', __name__)

@user_bp.route('/profile')
def profile():
    if 'employee_name' not in session:
        return redirect(url_for('auth.login'))
    
    headers = get_headers()
    employee_name = session.get('employee_name')
    
    # Get employee details
    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    employee = {}
    if res.status_code == 200:
        for emp in res.json().get("employees", []):
            if emp.get("name") == employee_name:
                employee = emp
                break
    
    # Get leave balance
    summary = {'remaining_leaves': 0}
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        summary = balance_data.get("summary", {})

    # Get bank details
    bank_details = {}
    try:
        bank_res = requests.get(f"{BASE_URL}/bank-details/", headers=headers)
        if bank_res.status_code == 200:
            bank_details = bank_res.json().get("bank_details", {})
    except: pass

    return render_template("profile.html", employee=employee, summary=summary, bank_details=bank_details, percent=0, is_hr_view=False, BASE_URL=BASE_URL)

@user_bp.route('/bank-verification')
@role_required(['admin', 'hr'])
def bank_verification():
    res = requests.get(f"{BASE_URL}/bank-details/", headers=get_headers())
    bank_details = res.json().get("bank_details", []) if res.status_code == 200 else []
    return render_template("bank_admin.html", bank_details=bank_details)

# Helper to register role_required if not imported
from app.utils import role_required
