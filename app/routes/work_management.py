import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from datetime import datetime, timedelta
from calendar import monthrange
from app.utils import BASE_URL, get_headers, role_required, fetch_leave_balance_helper
import os
import json

work_bp = Blueprint('work', __name__)

# --- TIMESHEETS ---
@work_bp.route('/timesheets')
@role_required(['admin', 'employee', 'hr', 'manager'])
def timesheets_list():
    projects_file = os.path.join(os.getcwd(), 'projects.json')
    projects_db = []
    if os.path.exists(projects_file):
        with open(projects_file, 'r') as f:
            projects_db = json.load(f)

    res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('auth.login'))
    data = res.json()
    project_manager_map = {proj['name'].strip().lower(): proj.get('assigned_manager', '-') for proj in projects_db}
    timesheets_list = data.get("timesheets", [])
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    role_map = {emp.get('name'): emp.get('role', 'employee') for emp in employees}
    for t in timesheets_list:
        t['employee_role'] = role_map.get(t.get('employee_name'), 'employee')
    user_role = str(session.get('role', '')).lower()
    current_user = session.get('employee_name')
    if user_role == 'employee':
        timesheets_list = [t for t in timesheets_list if t.get('employee_name') == current_user]
    elif user_role == 'manager':
        managed_projects = [proj['name'] for proj in projects_db if proj.get('assigned_manager') == current_user]
        timesheets_list = [t for t in timesheets_list if t.get('project') in managed_projects]
    return render_template("timesheets.html", timesheets=timesheets_list, project_manager_map=project_manager_map)

@work_bp.route('/add-timesheet', methods=['GET', 'POST'])
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
        return redirect(url_for('work.timesheets_list'))
    projects_file = os.path.join(os.getcwd(), 'projects.json')
    projects = []
    if os.path.exists(projects_file):
        with open(projects_file, 'r') as f:
            projects = json.load(f)
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    return render_template("add_timesheet.html", employees=employees, projects=projects, today_date=datetime.now().strftime('%Y-%m-%d'))

# --- LEAVES ---
@work_bp.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_list():
    res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('auth.login'))
    data = res.json()
    return render_template("leaves.html", leaves=data.get("leaves", []), BASE_URL=BASE_URL)

@work_bp.route('/add-leave', methods=['GET', 'POST'])
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
        if request.form.get("leave_type_category") == "half_day":
            payload["half_day_period"] = request.form.get("half_day_period")
        requests.post(f"{BASE_URL}/leaves", json=payload, headers=headers)
        return redirect(url_for('work.leaves_list'))
    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    employees = res.json().get("employees", []) if res.status_code == 200 else []
    balance_data = fetch_leave_balance_helper(employee_name)
    balance = []
    summary = {"remaining_leaves": 0, "casual_leaves": 0, "sick_leaves": 0, "earned_leaves": 0}
    if balance_data:
        balance = balance_data.get("balances", [])
        backend_summary = balance_data.get("summary", {})
        summary = {
            "remaining_leaves": backend_summary.get("remaining_leaves", 0),
            "casual_leaves": backend_summary.get("casual_remaining", 0),
            "sick_leaves": backend_summary.get("sick_remaining", 0),
            "earned_leaves": backend_summary.get("earned_remaining", 0)
        }
    return render_template("add_leave.html", employees=employees, balance=balance, summary=summary)

# --- ATTENDANCE ---
@work_bp.route('/attendance')
@role_required(['admin', 'employee', 'hr', 'manager'])
def attendance_view():
    # (Simplified version of attendance logic for brevity, should include full logic from app.py)
    return render_template('attendance.html', attendance_summary={}, attendance_metrics={}, approved_attendance=[], leave_details=[], attendance_details=[])
