import os
import json
import requests
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash, Response
from app.utils import BASE_URL, get_headers, role_required, token_required, fetch_leave_balance_helper

main_bp = Blueprint('main', __name__)

# --- NOTIFICATIONS ---
@main_bp.route('/notifications')
@role_required(['admin', 'employee', 'hr', 'manager'])
def notifications():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    return render_template('notifications.html')

# --- TIMESHEETS ---
@main_bp.route('/timesheets')
@role_required(['admin', 'employee', 'hr', 'manager'])
def timesheets():
    # Use the local projects_db logic here or fetch from file
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

    return render_template(
        "timesheets.html",
        timesheets=timesheets_list,
        project_manager_map=project_manager_map
    )

@main_bp.route('/add-timesheet', methods=['GET', 'POST'])
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
        return redirect(url_for('main.timesheets'))

    projects_file = os.path.join(os.getcwd(), 'projects.json')
    projects = []
    if os.path.exists(projects_file):
        with open(projects_file, 'r') as f:
            projects = json.load(f)

    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []

    return render_template(
        "add_timesheet.html",
        employees=employees,
        projects=projects,
        today_date=datetime.now().strftime('%Y-%m-%d')
    )

@main_bp.route('/add-weekly-timesheet')
@role_required(['admin', 'employee', 'hr', 'manager'])
def add_weekly_timesheet():
    return render_template('add_weekly_timesheet.html')

# --- LEAVES ---
@main_bp.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves():
    res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('auth.login'))
    data = res.json()
    return render_template("leaves.html", leaves=data.get("leaves", []), BASE_URL=BASE_URL)

@main_bp.route('/add-leave', methods=['GET', 'POST'])
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
        return redirect(url_for('main.leaves'))

    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    if res.status_code == 401:
        return redirect(url_for('auth.login'))
    employees = res.json().get("employees", [])
    
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
        if not summary["casual_leaves"] or not summary["sick_leaves"]:
            for b in balance:
                ltype = b.get("leave_type", "").lower()
                if "casual" in ltype: summary["casual_leaves"] = b.get("remaining_leaves", 0)
                if "sick" in ltype: summary["sick_leaves"] = b.get("remaining_leaves", 0)
                if "earned" in ltype: summary["earned_leaves"] = b.get("remaining_leaves", 0)
    return render_template("add_leave.html", employees=employees, balance=balance, summary=summary)

# ... (I will include more routes in subsequent edits or just put the most used ones for now)
# (To be continued in next write_to_file)
