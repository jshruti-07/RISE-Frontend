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

@work_bp.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_list():
    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 401:
            return redirect(url_for('auth.login'))
        
        leaves = []
        if leave_res.status_code == 200:
            data = leave_res.json()
            leaves = data.get("leaves", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Fetch employees for role mapping
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
        role_map = {emp.get('name'): emp.get('role', 'employee') for emp in employees}
        
        # Process leaves and ensure employee_role is present
        processed_leaves = []
        for l in leaves:
            if isinstance(l, dict):
                l['employee_role'] = role_map.get(l.get('employee_name'), 'employee')
                processed_leaves.append(l)

        # Role-based filtering
        user_role = str(session.get('role', '')).lower().strip()
        current_user = session.get('employee_name')
        
        if user_role == 'employee':
            final_leaves = [l for l in processed_leaves if l.get('employee_name') == current_user]
        else:
            final_leaves = processed_leaves
            
        return render_template("leaves.html", leaves=final_leaves, BASE_URL=BASE_URL)
    except Exception as e:
        print(f"Error in leaves_list: {e}")
        return render_template("leaves.html", leaves=[], error=str(e))

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
    
    # Robust summary for add_leave template
    balance_data = fetch_leave_balance_helper(employee_name)
    balance = []
    summary = {"remaining_leaves": 0, "casual_leaves": 0, "sick_leaves": 0, "earned_leaves": 0}
    
    if balance_data and (balance_data.get("balances") or balance_data.get("summary")):
        balance = balance_data.get("balances", [])
        bs = balance_data.get("summary", {})
        
        # Robust mapping for summary
        summary["remaining_leaves"] = bs.get("remaining_leaves") or bs.get("total_remaining") or 0
        summary["casual_leaves"] = bs.get("casual_remaining") or bs.get("casual_leaves_remaining") or bs.get("casual_leaves") or 0
        summary["sick_leaves"] = bs.get("sick_remaining") or bs.get("sick_leaves_remaining") or bs.get("sick_leaves") or 0
        summary["earned_leaves"] = bs.get("earned_remaining") or bs.get("earned_leaves_remaining") or bs.get("earned_leaves") or 0
        
        # If still 0, try to find in balances array
        if balance and (summary["casual_leaves"] == 0 or summary["sick_leaves"] == 0):
            for b in balance:
                ltype = (b.get("leave_type") or "").lower()
                rem = b.get("remaining_leaves") or b.get("remaining") or 0
                if "casual" in ltype: summary["casual_leaves"] = rem
                elif "sick" in ltype: summary["sick_leaves"] = rem
                elif "earned" in ltype: summary["earned_leaves"] = rem
    else:
        # Fallback calculation if API fails
        try:
            leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers(), timeout=10)
            if leaves_res.status_code == 200:
                leaves_data = leaves_res.json().get("leaves", [])
                used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}
                quotas = {"casual": 12, "sick": 10, "earned": 8, "total": 30}
                names_to_try = [employee_name]
                if len(employee_name) > 2: names_to_try.append(employee_name[2:].strip())

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
                        except: continue
                
                summary = {
                    "remaining_leaves": quotas["total"] - used_stats["total"],
                    "casual_leaves": quotas["casual"] - used_stats["casual"],
                    "sick_leaves": quotas["sick"] - used_stats["sick"],
                    "earned_leaves": quotas["earned"] - used_stats["earned"]
                }
                balance = [{"leave_type": "Calculated Fallback", "remaining_leaves": summary["remaining_leaves"]}]
        except Exception as e:
            print(f"Error in add_leave fallback: {e}")

    return render_template("add_leave.html", employees=employees, balance=balance, summary=summary)

@work_bp.route('/api/leaves/calendar')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_calendar():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    employee_name = request.args.get('employee_name')
    params = {'year': year, 'month': month}
    if employee_name: params['employee_name'] = employee_name
    try:
        res = requests.get(f"{BASE_URL}/leaves/calendar", params=params, headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- ATTENDANCE ---
@work_bp.route('/attendance')
@role_required(['admin', 'employee', 'hr', 'manager'])
def attendance_view():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        from_date_param = request.args.get('from_date')
        to_date_param = request.args.get('to_date')
        
        if from_date_param and to_date_param:
            from_date, to_date = from_date_param, to_date_param
        else:
            today = datetime.now()
            from_date = today.replace(day=1).strftime('%Y-%m-%d')
            last_day = monthrange(today.year, today.month)[1]
            to_date = today.replace(day=last_day).strftime('%Y-%m-%d')
        
        from_dt = datetime.strptime(from_date, '%Y-%m-%d')
        to_dt = datetime.strptime(to_date, '%Y-%m-%d')
        total_days = (to_dt - from_dt).days + 1
        
        weekends = 0
        curr = from_dt
        while curr <= to_dt:
            if curr.weekday() >= 5: weekends += 1
            curr += timedelta(days=1)
        
        working_days = total_days - weekends
        
        attendance_res = requests.get(f"{BASE_URL}/attendance", headers=get_headers())
        attendance_data = attendance_res.json().get("attendance", []) if attendance_res.status_code == 200 else []
        
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        leave_data = leaves_res.json().get("leaves", []) if leaves_res.status_code == 200 else []
        
        leave_balance = 0
        balance_data = fetch_leave_balance_helper(session.get('employee_name'))
        if balance_data:
            leave_balance = balance_data.get("summary", {}).get("remaining_leaves", 0)

        holidays_count = 0
        try:
            hol_res = requests.get(f"{BASE_URL}/holidays", headers=get_headers())
            if hol_res.status_code == 200:
                hols = hol_res.json().get("holidays", [])
                holidays_count = len([h for h in hols if from_date <= h.get("date", "")[:10] <= to_date])
        except: pass
        
        current_user = session.get('employee_name')
        user_role = session.get('role')
        
        # Determine target employee (default to self)
        target_employee = request.args.get('employee_name') or current_user
        
        # Security check: employees can only see themselves
        if user_role == 'employee':
            target_employee = current_user
        
        def is_match(rec_name, target):
            if not rec_name or not target: return False
            r, t = str(rec_name).lower().strip(), str(target).lower().strip()
            if r == t: return True
            # Handle cases where one has a prefix (H_, T_, etc) and the other doesn't
            if len(r) > 2 and r[1] == '_' and r[2:] == t: return True
            if len(t) > 2 and t[1] == '_' and t[2:] == r: return True
            return False

        # Filter data by target employee with robust matching
        attendance_data = [a for a in attendance_data if is_match(a.get('employee_name'), target_employee)]
        leave_data = [l for l in leave_data if is_match(l.get('employee_name'), target_employee)]
        
        # Further filter by date range
        attendance_data = [a for a in attendance_data if a.get('date') and from_date <= a.get('date')[:10] <= to_date]
        leave_data = [l for l in leave_data if l.get('start_date') and from_date <= l.get('start_date')[:10] <= to_date]
        
        # Calculate balance for target employee
        leave_balance = 0
        balance_data = fetch_leave_balance_helper(target_employee)
        if balance_data:
            leave_balance = balance_data.get("summary", {}).get("remaining_leaves", 0)

        # Get employee list and target employee details
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        all_employees = []
        display_name = target_employee
        display_emp_id = 'N/A'
        
        if emp_res.status_code == 200:
            emp_list = emp_res.json().get("employees", [])
            if user_role in ['hr', 'admin', 'manager']:
                all_employees = emp_list
            
            for emp in emp_list:
                if emp.get("name") == target_employee:
                    display_name = emp.get("name")
                    display_emp_id = emp.get("employee_id") or emp.get("id") or 'N/A'
                    break

        present_count = len([a for a in attendance_data if a.get('status') == 'present'])
        half_day_count = len([a for a in attendance_data if a.get('status') == 'half-day'])
        absent_count = len([a for a in attendance_data if a.get('status') == 'absent'])
        
        total_hours = sum(float(a.get('total_worked_hours', 0)) for a in attendance_data)
        avg_hours = round(total_hours / present_count, 2) if present_count > 0 else 0
        
        attendance_summary = {
            'from_date': from_date, 'to_date': to_date, 'total_days': total_days,
            'working_days': working_days, 'weekends': weekends, 'holidays': holidays_count,
            'attendance': present_count, 'avg_hours': avg_hours, 
            'leaves_used': len([l for l in leave_data if l.get('status') == 'approved']),
            'leave_balance': leave_balance, 'absent': absent_count,
            'target_employee': target_employee
        }
        
        attendance_metrics = {
            'office': present_count, 'wfh': 0, 'half_day': half_day_count,
            'absent': absent_count, 'overtime': len([a for a in attendance_data if a.get('work_status') == 'overtime']),
            'late_login': len([a for a in attendance_data if 'late' in a.get('remarks', '').lower()])
        }
        
        return render_template('attendance.html', 
                               attendance_summary=attendance_summary, 
                               attendance_metrics=attendance_metrics, 
                               approved_attendance=[a for a in attendance_data if a.get('status') in ['present', 'half-day']],
                               leave_details=leave_data, 
                               attendance_details=attendance_data,
                               display_name=display_name,
                               display_emp_id=display_emp_id,
                               all_employees=all_employees)
    except Exception as e:
        print(f"ERROR in attendance route: {e}")
        return render_template('attendance.html', error="Failed to load attendance data", 
                               attendance_summary={}, attendance_metrics={}, approved_attendance=[], 
                               leave_details=[], attendance_details=[])

@work_bp.route('/api/leaves/balance')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_balance():
    employee_name = request.args.get('employee_name') or session.get('employee_name')
    if not employee_name:
        return jsonify({"success": False, "error": "Employee name required"}), 400
    
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data and (balance_data.get("balances") or balance_data.get("summary")):
        return jsonify(balance_data)
    
    # Manual Fallback calculation if API fails
    try:
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers(), timeout=10)
        if leaves_res.status_code == 200:
            leaves_data = leaves_res.json().get("leaves", [])
            used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}
            quotas = {"casual": 12, "sick": 10, "earned": 8, "total": 30}
            names_to_try = [employee_name]
            if len(employee_name) > 2: names_to_try.append(employee_name[2:].strip())

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
                    except: continue
            
            return jsonify({
                "success": True,
                "summary": {
                    "total_leaves": quotas["total"], "used_leaves": used_stats["total"],
                    "remaining_leaves": quotas["total"] - used_stats["total"],
                    "casual_used": used_stats["casual"], "casual_total": quotas["casual"],
                    "sick_used": used_stats["sick"], "sick_total": quotas["sick"],
                    "earned_used": used_stats["earned"], "earned_total": quotas["earned"]
                },
                "balances": [
                    {"leave_type": "Casual", "used_leaves": used_stats["casual"], "total_leaves": quotas["casual"], "remaining_leaves": quotas["casual"] - used_stats["casual"]},
                    {"leave_type": "Sick", "used_leaves": used_stats["sick"], "total_leaves": quotas["sick"], "remaining_leaves": quotas["sick"] - used_stats["sick"]},
                    {"leave_type": "Earned", "used_leaves": used_stats["earned"], "total_leaves": quotas["earned"], "remaining_leaves": quotas["earned"] - used_stats["earned"]}
                ]
            })
    except Exception as e:
        print(f"Error in balance fallback: {e}")
    
    return jsonify({"success": False, "error": "Leave balance API unavailable"}), 500

@work_bp.route('/update-leave/<int:leave_id>/<status>', methods=['PUT'])
@role_required(['admin', 'manager', 'hr'])
def update_leave_status(leave_id, status):
    try:
        res = requests.put(f"{BASE_URL}/leaves/{leave_id}", json={"status": status}, headers=get_headers())
        if res.status_code == 200:
            return jsonify({'success': True, 'message': f'Leave {status} successfully'}), 200
        return jsonify({'success': False, 'error': 'Failed to update leave status'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
