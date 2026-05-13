import requests
import io
import pandas as pd
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, send_file
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
    def is_match(name1, name2):
        if not name1 or not name2: return False
        n1, n2 = str(name1).lower().strip(), str(name2).lower().strip()
        if n1 == n2: return True
        # Handle prefixes like H_, T_, etc.
        if len(n1) > 2 and n1[1] == '_' and n1[2:] == n2: return True
        if len(n2) > 2 and n2[1] == '_' and n2[2:] == n1: return True
        return False

    projects_file = os.path.join(os.getcwd(), 'projects.json')
    projects_db = []
    if os.path.exists(projects_file):
        try:
            with open(projects_file, 'r') as f:
                projects_db = json.load(f)
        except: projects_db = []

    res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
    if res.status_code == 401:
        return redirect(url_for('auth.login'))
    
    all_timesheets = res.json().get("timesheets", [])
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    
    role_map = {emp.get('name'): emp.get('role', 'employee') for emp in employees}
    project_manager_map = {proj['name'].strip().lower(): proj.get('assigned_manager', '-') for proj in projects_db}
    
    user_role = str(session.get('role', '')).lower()
    current_user = session.get('employee_name')
    
    filtered_timesheets = []
    for t in all_timesheets:
        emp_name = t.get('employee_name')
        t['employee_role'] = role_map.get(emp_name, 'employee')
        
        # Visibility Logic
        show = False
        if user_role in ['hr', 'admin']:
            show = True
        elif user_role == 'employee':
            show = is_match(emp_name, current_user)
        elif user_role == 'manager':
            # Manager sees own records
            if is_match(emp_name, current_user):
                show = True
            else:
                # Manager sees records for projects they manage
                proj_name = t.get('project', '').strip().lower()
                mgr_for_proj = project_manager_map.get(proj_name)
                if is_match(mgr_for_proj, current_user):
                    show = True
        
        if show:
            filtered_timesheets.append(t)
            
    return render_template("timesheets.html", 
                           timesheets=filtered_timesheets, 
                           project_manager_map=project_manager_map)

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
        try:
            res = requests.post(f"{BASE_URL}/timesheets", json=payload, headers=get_headers(), timeout=10)
            if res.status_code in [200, 201]:
                flash('Timesheet submitted successfully!', 'success')
            else:
                flash(f'Failed to submit timesheet: {res.text}', 'danger')
        except Exception as e:
            flash(f'Error submitting timesheet: {e}', 'danger')
            
        return redirect(url_for('work.timesheets_list'))
    projects_file = os.path.join(os.getcwd(), 'projects.json')
    projects = []
    if os.path.exists(projects_file):
        with open(projects_file, 'r') as f:
            projects = json.load(f)
    emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
    employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
    return render_template("add_timesheet.html", employees=employees, projects=projects, today_date=datetime.now().strftime('%Y-%m-%d'))

@work_bp.route('/timesheets/export')
@role_required(['admin', 'hr', 'manager'])
def export_timesheets():
    try:
        # 1. Fetch data from backend
        res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        if res.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch timesheets from API"}), res.status_code
            
        timesheets = res.json().get("timesheets", [])
        
        # 2. Apply Filters from query params
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        project = request.args.get('project')
        status = request.args.get('status')
        employee_name = request.args.get('employee_name')
        
        filtered = timesheets
        if start_date:
            filtered = [t for t in filtered if t.get('start_date', '')[:10] >= start_date]
        if end_date:
            filtered = [t for t in filtered if t.get('start_date', '')[:10] <= end_date]
        if project:
            filtered = [t for t in filtered if project.lower() in str(t.get('project', '')).lower()]
        if status:
            filtered = [t for t in filtered if str(t.get('status', '')).lower() == status.lower()]
        if employee_name:
            filtered = [t for t in filtered if employee_name.lower() in str(t.get('employee_name', '')).lower()]
            
        if not filtered:
            return jsonify({"success": False, "error": "No data found for selected filters"}), 404
            
        # 3. Create DataFrame
        df = pd.DataFrame(filtered)
        
        # Select and rename columns for better presentation
        columns_map = {
            'employee_name': 'Employee Name',
            'project': 'Project',
            'task': 'Task',
            'hours': 'Hours',
            'start_date': 'Date',
            'description': 'Description',
            'status': 'Status'
        }
        
        # Keep only existing columns from the map
        df = df[[col for col in columns_map.keys() if col in df.columns]]
        df.rename(columns=columns_map, inplace=True)
        
        # Clean dates for Excel
        if 'Date' in df.columns:
            df['Date'] = df['Date'].apply(lambda x: x[:10] if x else '')

        # 4. Generate Excel in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Timesheets')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Timesheets']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)

        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Timesheet_Export_{timestamp}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Export Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_list():
    def is_match(name1, name2):
        if not name1 or not name2: return False
        n1, n2 = str(name1).lower().strip(), str(name2).lower().strip()
        if n1 == n2: return True
        if len(n1) > 2 and n1[1] == '_' and n1[2:] == n2: return True
        if len(n2) > 2 and n2[1] == '_' and n2[2:] == n1: return True
        return False

    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 401:
            return redirect(url_for('auth.login'))
        
        all_leaves = []
        if leave_res.status_code == 200:
            data = leave_res.json()
            all_leaves = data.get("leaves", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Fetch employees and projects for context
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
        role_map = {emp.get('name'): emp.get('role', 'employee') for emp in employees}
        
        projects_file = os.path.join(os.getcwd(), 'projects.json')
        projects_db = []
        if os.path.exists(projects_file):
            try:
                with open(projects_file, 'r') as f:
                    projects_db = json.load(f)
            except: projects_db = []

        user_role = str(session.get('role', '')).lower().strip()
        current_user = session.get('employee_name')
        
        final_leaves = []
        for l in all_leaves:
            if not isinstance(l, dict): continue
            
            emp_name = l.get('employee_name')
            l['employee_role'] = role_map.get(emp_name, 'employee')
            
            # Robust self-check
            l['is_own'] = is_match(emp_name, current_user)
            
            # Visibility Logic
            show = False
            if user_role in ['hr', 'admin']:
                show = True
            elif l['is_own']:
                show = True
            elif user_role == 'manager':
                # Managers see leaves of employees in projects they manage
                managed_projects = [p['name'].strip().lower() for p in projects_db if is_match(p.get('assigned_manager'), current_user)]
                
                # Check if this employee is in any of those projects
                emp_projects = []
                for p in projects_db:
                    is_member = False
                    for m in p.get('team_members', []):
                        m_name = m.get('name') if isinstance(m, dict) else m
                        if is_match(m_name, emp_name):
                            is_member = True
                            break
                    if is_member:
                        emp_projects.append(p['name'].strip().lower())
                
                if any(proj in managed_projects for proj in emp_projects):
                    show = True
            
            if show:
                final_leaves.append(l)

        # Fetch balance summary for current user
        balance_data = fetch_leave_balance_helper(current_user)
        summary = {"remaining_leaves": 0, "casual_leaves": 0, "sick_leaves": 0, "earned_leaves": 0}
        balance = []
        
        if balance_data:
            summary = balance_data.get("summary", summary)
            balance = balance_data.get("balances", [])
            
        return render_template("leaves.html", 
                               leaves=final_leaves, 
                               summary=summary,
                               balance=balance,
                               BASE_URL=BASE_URL)
    except Exception as e:
        print(f"Error in leaves_list: {e}")
        return render_template("leaves.html", leaves=[], summary={}, balance=[], error=str(e))

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
        
        try:
            res = requests.post(f"{BASE_URL}/leaves", json=payload, headers=headers, timeout=10)
            if res.status_code in [200, 201]:
                flash('Leave application submitted successfully!', 'success')
            else:
                flash(f'Failed to submit leave: {res.text}', 'danger')
        except Exception as e:
            flash(f'Error submitting leave: {e}', 'danger')
            
        return redirect(url_for('work.leaves_list'))
    
    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    employees = res.json().get("employees", []) if res.status_code == 200 else []
    
    # Robust summary for add_leave template
    balance_data = fetch_leave_balance_helper(employee_name)
    balance = []
    summary = {
        "remaining_leaves": 0, "total_leaves": 30, "used_leaves": 0,
        "casual_used": 0, "casual_total": 12,
        "sick_used": 0, "sick_total": 10,
        "earned_used": 0, "earned_total": 8
    }
    
    if balance_data:
        summary = balance_data.get("summary", summary)
        balance = balance_data.get("balances", [])
    else:
        # Fallback calculation if API fails
        try:
            leaves_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers(), timeout=10)
            if leaves_res.status_code == 200:
                leaves_data = leaves_res.json().get("leaves", [])
                used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}
                names_to_try = [employee_name]
                if len(employee_name) > 2 and employee_name[1] == '_':
                    names_to_try.append(employee_name[2:].strip())

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
                    "total_leaves": 30,
                    "used_leaves": used_stats["total"],
                    "remaining_leaves": 30 - used_stats["total"],
                    "casual_used": used_stats["casual"], "casual_total": 12,
                    "sick_used": used_stats["sick"], "sick_total": 10,
                    "earned_used": used_stats["earned"], "earned_total": 8
                }
                # Compatibility for add_leave template
                summary["casual_leaves"] = 12 - used_stats["casual"]
                summary["sick_leaves"] = 10 - used_stats["sick"]
                summary["earned_leaves"] = 8 - used_stats["earned"]
                
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
