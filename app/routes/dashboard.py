import os
import json
import requests
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'token' not in session:
        return redirect(url_for('auth.login'))

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
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if emp_res.status_code == 401:
            session.clear()
            return redirect(url_for('auth.login'))
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
        
        time_res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        timesheets = time_res.json().get("timesheets", []) if time_res.status_code == 200 else []
        
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leaves = leave_res.json().get("leaves", []) if leave_res.status_code == 200 else []
        
        now = datetime.now()
        current_month = now.month
        current_year = now.year
        
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
        
        pending_leaves = [l for l in leaves if str(l.get('status', '')).lower() == 'pending']
        
        stats = {
            "employees": len(employees),
            "timesheets": len(pending_timesheets_month),
            "leaves": len(pending_leaves)
        }

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

        if session.get('role') in ['hr', 'admin']:
            try:
                hd_res = requests.get(f"{BASE_URL}/helpdesk/stats", headers=get_headers(), timeout=5)
                if hd_res.status_code == 200: hd_stats = hd_res.json()
            except: pass
            try:
                rb_res = requests.get(f"{BASE_URL}/reimbursement/stats", headers=get_headers(), timeout=5)
                if rb_res.status_code == 200: reimbursement_stats = rb_res.json()
            except: pass

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

        if session.get('role') == 'manager':
            manager_name = session.get('employee_name')
            # Look for projects.json in the project root (one level up from app/routes)
            projects_file = os.path.join(os.getcwd(), 'projects.json')
            if os.path.exists(projects_file):
                with open(projects_file, 'r') as f:
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
