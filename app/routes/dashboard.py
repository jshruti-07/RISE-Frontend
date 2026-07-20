import os
import json
import requests
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers, role_required
from app.api_helpers import (
    names_match,
    extract_list,
    pick,
    person_system_name,
    project_team_members,
    record_belongs_to_person,
    strip_role_prefix,
)

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if 'token' not in session:
        return redirect(url_for('auth.login'))

    # Joinee candidates must not access the HR/employee dashboard
    if str(session.get('role', '')).lower().strip() == 'onboarding_candidate':
        return redirect(url_for('onboarding.joinee_dashboard'))

    birthday_data = []
    holidays = []
    stats = {"employees": 0, "timesheets": 0, "leaves": 0}
    hd_stats = {}
    reimbursement_stats = {}
    pending_agreements = []
    projects = []
    my_projects = []
    pending_timesheets_list = []
    pending_timesheets_count = 0
    team_pending_timesheets = []
    team_leaves = []
    timesheets = []
    leaves = []
    announcements = []

    try:
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        if emp_res.status_code == 401:
            session.clear()
            return redirect(url_for('auth.login'))
        employees = extract_list(emp_res.json(), 'employees', 'data') if emp_res.status_code == 200 else []
        
        time_res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        timesheets = extract_list(time_res.json(), 'timesheets', 'data') if time_res.status_code == 200 else []
        
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leaves = extract_list(leave_res.json(), 'leaves', 'data') if leave_res.status_code == 200 else []
        
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
            holidays = extract_list(holiday_res.json(), 'holidays', 'data')
            for h in holidays:
                raw_date = str(h.get("date", ""))
                try:
                    dt = datetime.strptime(raw_date[:10], "%Y-%m-%d") if "-" in raw_date else datetime.strptime(raw_date.strip(), "%a, %d %b")
                    h["formatted_date"] = dt.strftime("%d %b")
                except: h["formatted_date"] = raw_date

        # Create a map for employee photos
        photo_map = {}
        for emp in employees:
            nm = person_system_name(emp)
            photo = pick(emp, 'photo_url', 'photo')
            if nm and photo:
                photo_map[nm] = photo
                bare = strip_role_prefix(nm)
                if bare:
                    photo_map[bare] = photo

        # 1. Today's Birthdays
        try:
            today_res = requests.get(f"{BASE_URL}/birthdays/today/", headers=get_headers(), timeout=5)
            if today_res.status_code == 200:
                today_data = today_res.json()
                today_list = extract_list(today_data, 'birthdays', 'data')
                for b in today_list:
                    b['is_today'] = True
                    b['photo_url'] = photo_map.get(b.get('name')) or photo_map.get(strip_role_prefix(b.get('name')))
                    birthday_data.append(b)
        except: pass

        # 2. Upcoming Birthdays (Next 7 Days)
        try:
            upcoming_res = requests.get(f"{BASE_URL}/birthdays/upcoming/", headers=get_headers(), timeout=5)
            if upcoming_res.status_code == 200:
                upcoming_data = upcoming_res.json()
                upcoming_list = extract_list(upcoming_data, 'upcoming_birthdays', 'birthdays', 'data')
                for b in upcoming_list:
                    b['is_today'] = False
                    b['photo_url'] = photo_map.get(b.get('name')) or photo_map.get(strip_role_prefix(b.get('name')))
                    birthday_data.append(b)
        except: pass

        # 3. All Birthdays (for Timeline navigation)
        all_birthdays = []
        for emp in employees:
            dob = emp.get('date_of_birth')
            if dob:
                nm = person_system_name(emp) or emp.get('employee_name') or emp.get('name', 'Unknown')
                photo = photo_map.get(nm) or photo_map.get(strip_role_prefix(nm))
                all_birthdays.append({
                    'name': nm,
                    'date_of_birth': dob,
                    'photo_url': photo
                })

        if session.get('role') in ['hr', 'admin']:
            try:
                hd_res = requests.get(f"{BASE_URL}/helpdesk/stats/", headers=get_headers(), timeout=5)
                if hd_res.status_code == 200: hd_stats = hd_res.json()
            except: pass
            try:
                rb_res = requests.get(f"{BASE_URL}/reimbursements/", headers=get_headers(), timeout=5)
                if rb_res.status_code == 200:
                    claims = extract_list(rb_res.json(), 'reimbursements', 'data')
                    pending_count = 0
                    approved_count = 0
                    rejected_count = 0
                    
                    for claim in claims:
                        status = str(claim.get("status", "")).lower().strip()
                        if status in ["pending", "submitted", "pending_approval"]:
                            pending_count += 1
                        elif status in ["approved", "paid"]:
                            approved_count += 1
                        elif status in ["rejected", "cancelled"]:
                            rejected_count += 1
                    
                    reimbursement_stats = {
                        "pending_approval": {"count": pending_count},
                        "by_status": {
                            "approved": {"count": approved_count},
                            "rejected": {"count": rejected_count}
                        }
                    }
                else:
                    # Fallback to stats endpoint if /reimbursements/ fails
                    rb_stat_res = requests.get(f"{BASE_URL}/reimbursement/stats/", headers=get_headers(), timeout=5)
                    if rb_stat_res.status_code == 200:
                        raw_rb = rb_stat_res.json()
                        # Structure it correctly for the template
                        pending = raw_rb.get("pending_approval", 0)
                        if isinstance(pending, dict):
                            pending_count = pending.get("count", 0)
                        else:
                            pending_count = int(pending or 0)
                            
                        approved_count = 0
                        rejected_count = 0
                        
                        by_status = raw_rb.get("by_status", {})
                        if isinstance(by_status, dict):
                            app_data = by_status.get("approved", 0)
                            rej_data = by_status.get("rejected", 0)
                            approved_count = app_data.get("count", 0) if isinstance(app_data, dict) else int(app_data or 0)
                            rejected_count = rej_data.get("count", 0) if isinstance(rej_data, dict) else int(rej_data or 0)
                        else:
                            approved_count = int(raw_rb.get("approved", 0))
                            rejected_count = int(raw_rb.get("rejected", 0))
                            
                        reimbursement_stats = {
                            "pending_approval": {"count": pending_count},
                            "by_status": {
                                "approved": {"count": approved_count},
                                "rejected": {"count": rejected_count}
                            }
                        }
                    else:
                        reimbursement_stats = {
                            "pending_approval": {"count": 0},
                            "by_status": {
                                "approved": {"count": 0},
                                "rejected": {"count": 0}
                            }
                        }
            except Exception as rb_err:
                print(f"Error calculating reimbursement stats: {rb_err}")
                reimbursement_stats = {
                    "pending_approval": {"count": 0},
                    "by_status": {
                        "approved": {"count": 0},
                        "rejected": {"count": 0}
                    }
                }
            
            # HR and Admin should see all pending/approved leaves as "Team Leaves" on dashboard
            team_leaves = [l for l in leaves if l.get('status', '').lower() in ['pending', 'approved']]
            team_leaves.sort(key=lambda x: x.get('start_date', ''), reverse=True)
            
            # HR and Admin should also see all pending timesheets
            team_pending_timesheets = [
                t for t in timesheets
                if str(t.get('status', '')).lower() in ['submitted', 'pending', 'missing', 'missing entry']
            ]
            team_pending_timesheets.sort(key=lambda x: x.get('start_date', ''), reverse=True)

        if session.get('role') == 'employee':
            try:
                my_devices_res = requests.get(f"{BASE_URL}/devices/my-devices", headers=get_headers(), timeout=5)
                if my_devices_res.status_code == 200:
                    my_devices = my_devices_res.json().get('devices', [])
                    pending_agreements = [d for d in my_devices if d.get('acceptance_status') == 'pending']
            except: pass
            
            current_user = session.get('employee_name')
            pending_timesheets_list = [
                t for t in timesheets
                if record_belongs_to_person(t, current_user)
                and str(t.get('status', '')).lower() in ['submitted', 'pending', 'missing', 'missing entry']
            ]
            today_str = datetime.now().strftime('%Y-%m-%d')
            has_today_entry = any(
                t for t in timesheets
                if record_belongs_to_person(t, current_user) and t.get('start_date', '')[:10] == today_str
            )
            pending_timesheets_count = len(pending_timesheets_list)
            if not has_today_entry:
                pending_timesheets_count += 1
                pending_timesheets_list.insert(0, {'project': 'Today\'s Entry', 'start_date': today_str, 'status': 'missing'})

            # Fetch projects assigned to this employee (limited view – no customer data)
            try:
                proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
                if proj_res.status_code == 200:
                    all_projects = extract_list(proj_res.json(), 'projects', 'data')
                    for proj in all_projects:
                        if str(proj.get('status', '')).lower() != 'active':
                            continue
                        # Backend already returns only this employee's assigned projects.
                        allocation = 100
                        billing_type = 'Billable'
                        for m in project_team_members(proj):
                            nm = m.get('employee_name') or m.get('name')
                            if names_match(nm, current_user):
                                allocation = (
                                    m.get('allocation') or m.get('allocation_percentage')
                                    or m.get('billable_percentage') or m.get('billable_pct')
                                    or m.get('percentage') or 100
                                )
                                billing_type = m.get('billing_type') or (
                                    'Billable' if m.get('is_billable', True) else 'Non-Billable'
                                )
                                break
                        my_projects.append({
                            'id': proj.get('id'),
                            'name': proj.get('name', 'Unnamed Project'),
                            'status': proj.get('status', 'active'),
                            'start_date': proj.get('start_date', ''),
                            'end_date': proj.get('end_date', ''),
                            'manager': proj.get('assigned_manager') or proj.get('manager_name') or proj.get('assigned_manager_name', ''),
                            'allocation': allocation,
                            'billing_type': billing_type,
                        })
            except Exception as proj_err:
                print(f"Error fetching employee projects on dashboard: {proj_err}")

        if session.get('role') == 'manager':
            manager_name = session.get('employee_name')
            
            # Fetch projects from API instead of static json
            projects_db = []
            try:
                proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
                if proj_res.status_code == 200:
                    data = proj_res.json()
                    projects_db = extract_list(data, 'projects', 'data')
            except: pass

            # Backend already returns projects this manager directs or is assigned to.
            projects = [
                proj for proj in projects_db
                if str(proj.get('status', '')).lower() == 'active'
            ]
            
            manager_project_names = [proj.get('name', '').lower().strip() for proj in projects]
            team_pending_timesheets = [
                t for t in timesheets
                if str(t.get('project', '')).lower().strip() in manager_project_names
                and str(t.get('status', '')).lower() in ['submitted', 'pending', 'missing', 'missing entry']
            ]
            
            team_member_names = set()
            for proj in projects:
                for m in project_team_members(proj):
                    nm = m.get('employee_name') or m.get('name')
                    if nm:
                        team_member_names.add(nm)
            
            team_leaves = []
            for l in leaves:
                if str(l.get('status', '')).lower() in ['pending', 'approved']:
                    emp_n = l.get('employee_name') or l.get('name') or l.get('emp_name')
                    # Check if this employee matches any in the team
                    if any(names_match(emp_n, tm) for tm in team_member_names):
                        team_leaves.append(l)
            team_leaves.sort(key=lambda x: x.get('start_date', ''), reverse=True)

        # Fetch active announcements for the dashboard widget
        try:
            ann_res = requests.get(f"{BASE_URL}/announcements/dashboard", headers=get_headers(), timeout=5)
            if ann_res.status_code == 200:
                res_data = ann_res.json()
                if isinstance(res_data, list):
                    announcements = res_data
                elif isinstance(res_data, dict):
                    announcements = res_data.get("announcements", res_data.get("data", []))
                else:
                    announcements = []
        except Exception as ann_err:
            print(f"Error fetching dashboard announcements: {ann_err}")

    except Exception as e:
        print(f"Dashboard Exception: {e}")
        flash("Error loading some dashboard data", "warning")

    return render_template(
        'dashboard.html',
        stats=stats,
        holidays=holidays,
        birthdays=birthday_data,
        all_birthdays=all_birthdays,
        hd_stats=hd_stats,
        reimbursement_stats=reimbursement_stats,
        pending_agreements=pending_agreements,
        projects=projects,
        my_projects=my_projects,
        team_pending_timesheets=team_pending_timesheets,
        team_leaves=team_leaves[:10],
        pending_timesheets_count=pending_timesheets_count,
        pending_timesheets_list=pending_timesheets_list[:5],
        announcements=announcements,
        current_user=session.get('employee_name'),
        role=session.get('role'),
        BASE_URL=BASE_URL
    )
