import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from datetime import datetime, timedelta
from app.utils import BASE_URL, get_headers, role_required
import os
import json

timesheets_bp = Blueprint('timesheets', __name__)

@timesheets_bp.route('/timesheets')
@role_required(['admin', 'employee', 'hr', 'manager'])
def timesheets_list():
    try:
        res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        if res.status_code == 401:
            return redirect(url_for('auth.login'))
        data = res.json()
        all_timesheets = data.get("timesheets", [])
        
        user_role = session.get('role')
        current_user = session.get('employee_name')
        
        if user_role == 'employee':
            timesheets = [t for t in all_timesheets if t.get('employee_name') == current_user]
        elif user_role == 'manager':
            projects_file = os.path.join(os.getcwd(), 'projects.json')
            manager_projects = []
            if os.path.exists(projects_file):
                with open(projects_file, 'r') as f:
                    projects_db = json.load(f)
                    manager_projects = [p.get('name') for p in projects_db if p.get('assigned_manager') == current_user]
            timesheets = [t for t in all_timesheets if t.get('project') in manager_projects or t.get('employee_name') == current_user]
        else:
            timesheets = all_timesheets

        timesheets.sort(key=lambda x: x.get('start_date', ''), reverse=True)
    except Exception as e:
        print("ERROR:", e)
        timesheets = []

        return render_template("timesheets.html", timesheets=timesheets)

@timesheets_bp.route('/hr/missing-timesheets')
@role_required(['hr'])
def hr_missing_timesheets():
    """Render a view listing employees who have not submitted timesheets for the current week."""
    try:
        # Fetch all employees
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
        # Fetch all submitted timesheets
        ts_res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        all_timesheets = ts_res.json().get("timesheets", []) if ts_res.status_code == 200 else []
        # Determine 21‑day window starting from the 1st of the current month
        today = datetime.utcnow().date()
        start_of_month = today.replace(day=1)
        end_of_window = start_of_month + timedelta(days=20)  # inclusive 21‑day period
        # Build set of employee names who have submitted a timesheet within this window
        submitted_in_window = set()
        for ts in all_timesheets:
            try:
                ts_date_str = ts.get('start_date') or ts.get('date')
                if not ts_date_str:
                    continue
                ts_date = datetime.strptime(ts_date_str[:10], "%Y-%m-%d").date()
                if start_of_month <= ts_date <= end_of_window:
                    submitted_in_window.add(ts.get('employee_name'))
            except Exception:
                continue
        # Employees missing timesheets for the 21‑day period
        missing_timesheets = []
        for emp in employees:
            name = emp.get('name')
            if name not in submitted_in_window:
                missing_timesheets.append({
                    'employee_name': name,
                    'missing_period': f"{start_of_month} to {end_of_window}",
                    'project': emp.get('project', '-')
                })
        return render_template(
            'hr_missing_timesheets.html',
            missing_timesheets=missing_timesheets,
            start_date=start_of_month,
            end_date=end_of_window
        )
    except Exception as e:
        print("ERROR in hr_missing_timesheets:", e)
        return render_template('hr_missing_timesheets.html', missing_timesheets=[])

@timesheets_bp.route('/add-timesheet', methods=['GET', 'POST'])
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
        return redirect(url_for('timesheets.timesheets_list'))

    projects = []
    projects_file = os.path.join(os.getcwd(), 'projects.json')
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

# ... (Adding only essential routes to show progress, keeping the rest for modularization)
