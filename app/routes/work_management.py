import requests
import io
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, send_file
from datetime import datetime, timedelta
from calendar import monthrange
from app.utils import BASE_URL, get_headers, role_required, fetch_leave_balance_helper
from app.api_helpers import (
    names_match,
    extract_list,
    normalize_person,
    normalize_people_list,
    person_system_name,
    person_role,
    record_belongs_to_person,
    project_team_members,
    lookup_role,
    pick,
)
import os
import json

work_bp = Blueprint('work', __name__)

# --- TIMESHEETS ---
@work_bp.route('/timesheets')
@role_required(['admin', 'employee', 'hr', 'manager'])
def timesheets_list():
    try:
        # 1. Fetch ALL projects
        projects_db = []
        project_manager_map = {}
        try:
            proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
            if proj_res.status_code == 200:
                data = proj_res.json()
                projects_db = extract_list(data, 'projects', 'data')
                
                # Map projects to managers
                for proj in projects_db:
                    if not isinstance(proj, dict): continue
                    p_name = str(proj.get('name', '')).strip().lower()
                    mgr = pick(proj, 'assigned_manager', 'manager_name', 'assigned_manager_name', default='-')
                    project_manager_map[p_name] = mgr
        except Exception as e:
            print(f"Error fetching projects for timesheets: {e}")

        # 2. Fetch ALL timesheets
        all_timesheets = []
        try:
            res = requests.get(f"{BASE_URL}/timesheets/", headers=get_headers(), timeout=15)
            if res.status_code == 200:
                all_timesheets = extract_list(res.json(), 'timesheets', 'data')
            elif res.status_code == 401:
                return redirect(url_for('auth.login'))
        except Exception as e:
            print(f"Error fetching timesheets: {e}")
        
        # 3. Fetch employees for role mapping
        role_map = {}
        try:
            emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
            if emp_res.status_code == 200:
                emp_data = emp_res.json()
                employees = extract_list(emp_data, 'employees', 'data')
                role_map = {
                    person_system_name(emp): person_role(emp)
                    for emp in employees if isinstance(emp, dict)
                }
        except Exception as e:
            print(f"Error fetching employees for timesheets: {e}")
        
        user_role = str(session.get('role', '')).lower().strip()
        current_user = session.get('employee_name')
        
        # --- Filtering logic ---
        filtered_timesheets = []
        for t in all_timesheets:
            if not isinstance(t, dict): continue
            
            emp_name = t.get('employee_name') or t.get('name') or t.get('emp_name')
            if not emp_name: continue
            
            t['employee_role'] = lookup_role(role_map, emp_name)
            is_own = names_match(emp_name, current_user)
            t['is_own'] = is_own
            
            # Visibility Logic
            show = False
            if user_role == 'admin':
                show = True
            elif is_own:
                show = True
            elif user_role == 'manager':
                proj_name = str(t.get('project', '')).strip().lower()
                mgr_for_proj = project_manager_map.get(proj_name)
                if names_match(mgr_for_proj, current_user):
                    show = True
            
            if show:
                filtered_timesheets.append(t)

        # 4. Fetch Holidays for Calendar
        holidays = []
        try:
            hol_res = requests.get(f"{BASE_URL}/holidays", headers=get_headers(), timeout=5)
            if hol_res.status_code == 200:
                holidays = extract_list(hol_res.json(), 'holidays', 'data')
        except: pass
                
        return render_template("timesheets.html", 
                               timesheets=filtered_timesheets, 
                               project_manager_map=project_manager_map,
                               holidays=holidays,
                               missing_timesheets=[],
                               project_map={},
                               BASE_URL=BASE_URL)
    except Exception as e:
        print(f"CRITICAL ERROR in timesheets_list: {e}")
        flash(f"An unexpected error occurred while loading timesheets: {str(e)}", "danger")
        return render_template("timesheets.html", 
                               timesheets=[], 
                               project_manager_map={},
                               holidays=[],
                               missing_timesheets=[],
                               project_map={},
                               BASE_URL=BASE_URL)

@work_bp.route('/hr-missing-timesheets')
@role_required(['hr', 'admin'])
def hr_missing_timesheets():
    try:
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        today = datetime.utcnow().date()
        if start_date_str:
            target_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        else:
            target_start = today.replace(day=1)
            
        if end_date_str:
            target_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        else:
            target_end = today

        # Fetch employees
        emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
        employees = []
        if emp_res.status_code == 200:
            emp_data = emp_res.json()
            employees = extract_list(emp_data, 'employees', 'data') if emp_res.status_code == 200 else []
            
        # Fetch timesheets
        all_timesheets = []
        res = requests.get(f"{BASE_URL}/timesheets/", headers=get_headers(), timeout=15)
        if res.status_code == 200:
            all_timesheets = extract_list(res.json(), 'timesheets', 'data')

        submitted_statuses = {'submitted', 'approved', 'rejected'}
        submitted_in_window = set()
        for ts in all_timesheets:
            try:
                status = str(ts.get('status', '')).lower()
                if status not in submitted_statuses:
                    continue
                ts_date_str = ts.get('start_date') or ts.get('date')
                if not ts_date_str:
                    continue
                ts_date = datetime.strptime(ts_date_str[:10], "%Y-%m-%d").date()
                if target_start <= ts_date <= target_end:
                    en = pick(ts, 'employee_name', 'teamMemberName', 'name')
                    if en:
                        submitted_in_window.add(str(en).strip())
            except Exception:
                continue

        missing_timesheets = []
        for emp in employees:
            if not isinstance(emp, dict):
                continue
            name = person_system_name(emp)
            if name and not any(names_match(name, s) for s in submitted_in_window):
                missing_timesheets.append({
                    'employee_name': name,
                    'missing_period': f"{target_start.strftime('%Y-%m-%d')} to {target_end.strftime('%Y-%m-%d')}",
                    'project': emp.get('project', '-')
                })

        return render_template(
            'hr_missing_timesheets.html',
            missing_timesheets=missing_timesheets,
            start_date=target_start.strftime('%Y-%m-%d'),
            end_date=target_end.strftime('%Y-%m-%d'),
            show_list=True
        )
    except Exception as e:
        print(f"Error in hr_missing_timesheets: {e}")
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('work.timesheets_list'))

@work_bp.route('/add-weekly-timesheet')
@role_required(['admin', 'employee', 'hr', 'manager'])
def add_weekly_timesheet():
    return render_template('add_weekly_timesheet.html')

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
            res = requests.post(f"{BASE_URL}/timesheets/", json=payload, headers=get_headers(), timeout=10)
            if res.status_code in [200, 201]:
                flash('Timesheet submitted successfully!', 'success')
            else:
                flash(f'Failed to submit timesheet: {res.text}', 'danger')
        except Exception as e:
            flash(f'Error submitting timesheet: {e}', 'danger')
            
        return redirect(url_for('work.timesheets_list'))
    projects = []
    try:
        proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
        if proj_res.status_code == 200:
            projects = extract_list(proj_res.json(), 'projects', 'data')
    except: pass
    emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
    employees = extract_list(emp_res.json(), 'employees', 'data') if emp_res.status_code == 200 else []
    return render_template("add_timesheet.html", employees=employees, projects=projects, today_date=datetime.now().strftime('%Y-%m-%d'))


@work_bp.route('/edit-timesheet/<int:timesheet_id>', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def edit_timesheet(timesheet_id):
    # GET existing timesheet data
    try:
        res = requests.get(f"{BASE_URL}/timesheets/", headers=get_headers(), timeout=15)
        if res.status_code == 401:
            return redirect(url_for('auth.login'))
        timesheets = extract_list(res.json(), 'timesheets', 'data')
    except Exception as e:
        print("Error fetching timesheets for edit:", e)
        flash("Error loading timesheet data from server", "danger")
        return redirect(url_for('work.timesheets_list'))
    
    # Robust matching by casting both IDs to int
    timesheet = next((t for t in timesheets if t.get('id') is not None and int(t.get('id')) == int(timesheet_id)), None)
    
    if not timesheet:
        flash("Timesheet not found", "danger")
        return redirect(url_for('work.timesheets_list'))
    
    # Backend validation: Only allow editing if status is submitted
    if str(timesheet.get('status', '')).lower() != 'submitted':
        flash("Cannot edit timesheet - it has already been approved or rejected", "danger")
        return redirect(url_for('work.timesheets_list'))
    
    # Backend validation: Only allow employees to edit their own timesheets
    current_user = session.get('employee_name')
    user_role = session.get('role')
    
    if user_role not in ['employee', 'hr', 'admin']:
        flash("Only authorized roles can edit their own timesheets", "danger")
        return redirect(url_for('work.timesheets_list'))
    
    # Check if this timesheet belongs to current user
    if not record_belongs_to_person(timesheet, current_user):
        flash("You can only edit your own timesheets", "danger")
        return redirect(url_for('work.timesheets_list'))
    
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
            # Try PATCH first
            res = requests.patch(
                f"{BASE_URL}/timesheets/{timesheet_id}",
                json=payload,
                headers=get_headers(),
                timeout=10
            )
            
            # If PATCH fails with 405, try PUT
            if res.status_code == 405:
                res = requests.put(
                    f"{BASE_URL}/timesheets/{timesheet_id}",
                    json=payload,
                    headers=get_headers(),
                    timeout=10
                )
                
            # If PUT also fails with 405, try POST
            if res.status_code == 405:
                res = requests.post(
                    f"{BASE_URL}/timesheets/{timesheet_id}",
                    json=payload,
                    headers=get_headers(),
                    timeout=10
                )
            
            if res.status_code in [200, 201]:
                flash("Timesheet updated successfully!", "success")
            else:
                flash(f"Failed to update timesheet: {res.text}", "danger")
        except Exception as e:
            flash(f"Error updating timesheet: {e}", "danger")
            
        return redirect(url_for('work.timesheets_list'))

    # GET: Fetch projects and employees for the edit form
    projects = []
    try:
        proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
        if proj_res.status_code == 200:
            projects = extract_list(proj_res.json(), 'projects', 'data')
    except Exception as e:
        print("Failed to fetch projects from backend:", e)

    employees = []
    try:
        emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
        if emp_res.status_code == 200:
            employees = extract_list(emp_res.json(), 'employees', 'data')
    except Exception as e:
        print("Failed to fetch employees:", e)

    return render_template(
        "edit_timesheet.html",
        timesheet=timesheet,
        employees=employees,
        projects=projects
    )

@work_bp.route('/timesheets/export')
@role_required(['admin', 'hr', 'manager'])
def export_timesheets():
    try:
        # 1. Fetch data from backend
        res = requests.get(f"{BASE_URL}/timesheets/", headers=get_headers())
        if res.status_code != 200:
            return jsonify({"success": False, "error": "Failed to fetch timesheets from API"}), res.status_code
            
        timesheets = extract_list(res.json(), 'timesheets', 'data')

        # 1b. Build project → manager map
        project_manager_map = {}
        try:
            proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
            if proj_res.status_code == 200:
                projects_db = extract_list(proj_res.json(), 'projects', 'data')
                for proj in projects_db:
                    if not isinstance(proj, dict):
                        continue
                    p_name = str(proj.get('name', '')).strip().lower()
                    mgr = pick(proj, 'assigned_manager', 'manager_name', 'assigned_manager_name', default='')
                    project_manager_map[p_name] = mgr
        except Exception as proj_err:
            print(f"Could not fetch projects for export manager map: {proj_err}")

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
            filtered = [t for t in filtered if record_belongs_to_person(t, employee_name)]
            
        if not filtered:
            return jsonify({"success": False, "error": "No data found for selected filters"}), 404

        # 2b. Inject manager field into each row from project_manager_map
        for t in filtered:
            proj_key = str(t.get('project', '')).strip().lower()
            t['manager'] = project_manager_map.get(proj_key, '')
            
        # Select and rename columns mapping
        columns_map = {
            'employee_name': 'Employee Name',
            'project': 'Project',
            'manager': 'Project Manager',
            'task': 'Task',
            'hours': 'Hours',
            'start_date': 'Date',
            'description': 'Description',
            'status': 'Status'
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 3. Handle Export (Excel with CSV fallback)
        if PANDAS_AVAILABLE:
            try:
                df = pd.DataFrame(filtered)
                # Ensure all columns_map keys exist in df (add empty ones if missing)
                for col_key in columns_map.keys():
                    if col_key not in df.columns:
                        df[col_key] = ''
                df = df[[col for col in columns_map.keys() if col in df.columns]]
                df.rename(columns=columns_map, inplace=True)
                if 'Date' in df.columns:
                    df['Date'] = df['Date'].apply(lambda x: x[:10] if x else '')

                output = io.BytesIO()
                # Use xlsxwriter if available, else standard engine
                engine = 'openpyxl'
                try:
                    import openpyxl
                except ImportError:
                    engine = None # Fallback to default pandas excel engine

                with pd.ExcelWriter(output, engine=engine) as writer:
                    df.to_excel(writer, index=False, sheet_name='Timesheets')
                    if engine == 'openpyxl':
                        worksheet = writer.sheets['Timesheets']
                        for idx, col in enumerate(df.columns):
                            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                            worksheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)
                
                output.seek(0)
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f"Timesheet_Export_{timestamp}.xlsx"
                )
            except Exception as excel_err:
                print(f"Excel generation failed, falling back to CSV: {excel_err}")
                # Fall through to CSV fallback

        # 4. CSV Fallback (always works, no complex dependencies)
        import csv
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns_map.values())
        writer.writeheader()
        for row in filtered:
            processed_row = {columns_map[k]: row.get(k, '') for k in columns_map.keys()}
            writer.writerow(processed_row)
        
        mem = io.BytesIO()
        mem.write(output.getvalue().encode('utf-8'))
        mem.seek(0)
        output.close()
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"Timesheet_Export_{timestamp}.csv"
        )
    except Exception as e:
        print(f"Export Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@work_bp.route('/leaves')
@role_required(['admin', 'employee', 'hr', 'manager'])
def leaves_list():
    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 401:
            return redirect(url_for('auth.login'))
        
        all_leaves = []
        if leave_res.status_code == 200:
            data = leave_res.json()
            all_leaves = extract_list(data, 'leaves', 'data') if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Fetch employees and projects for context
        emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
        employees = extract_list(emp_res.json(), 'employees', 'data') if emp_res.status_code == 200 else []
        role_map = {
            person_system_name(emp): person_role(emp)
            for emp in employees if isinstance(emp, dict)
        }
        
        # Fetch projects from API instead of static json
        projects_db = []
        try:
            proj_res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
            if proj_res.status_code == 200:
                data = proj_res.json()
                projects_db = extract_list(data, 'projects', 'data')
        except Exception as e:
            print(f"Error fetching projects for leaves: {e}")

        user_role = str(session.get('role', '')).lower().strip()
        current_user = session.get('employee_name')
        
        final_leaves = []
        for l in all_leaves:
            if not isinstance(l, dict): continue
            
            # Robust name extraction
            emp_name = l.get('employee_name') or l.get('name') or l.get('emp_name')
            if not emp_name: continue
            
            l['employee_role'] = lookup_role(role_map, emp_name)
            
            # Robust self-check
            l['is_own'] = names_match(emp_name, current_user)
            
            # Visibility Logic
            show = False
            if user_role in ['hr', 'admin']:
                show = True
            elif l['is_own']:
                show = True
            elif user_role == 'manager':
                # Managers see leaves of employees in projects they manage
                managed_projects = [p['name'].strip().lower() for p in projects_db if names_match(pick(p, 'assigned_manager', 'manager_name', 'assigned_manager_name'), current_user)]
                
                # Check if this employee is in any of those projects
                emp_projects = []
                for p in projects_db:
                    is_member = False
                    for m in p.get('team_members', []):
                        m_name = m.get('name') if isinstance(m, dict) else m
                        if names_match(m_name, emp_name):
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
            
        holidays = []
        try:
            hol_res = requests.get(f"{BASE_URL}/holidays/", headers=get_headers(), timeout=5)
            if hol_res.status_code == 200:
                hdata = hol_res.json()
                holidays = extract_list(hdata, 'holidays', 'data') if isinstance(hdata, dict) else []
        except Exception as e:
            print(f"Error fetching holidays for leaves page: {e}")

        return render_template("leaves.html", 
                               leaves=final_leaves, 
                               summary=summary,
                               balance=balance,
                               holidays=holidays,
                               BASE_URL=BASE_URL)
    except Exception as e:
        print(f"Error in leaves_list: {e}")
        return render_template("leaves.html", leaves=[], summary={}, balance=[], holidays=[], error=str(e))

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
    
    res = requests.get(f"{BASE_URL}/employees/", headers=headers)
    employees = extract_list(res.json(), 'employees', 'data') if res.status_code == 200 else []
    
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
                leaves_data = extract_list(leaves_res.json(), 'leaves', 'data')
                used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}

                for leave in leaves_data:
                    emp = pick(leave, 'employee_name', 'teamMemberName', 'name')
                    if names_match(emp, employee_name) and leave.get("status") == "approved":
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

@work_bp.route('/api/holidays', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def get_holidays_api():
    try:
        res = requests.get(f"{BASE_URL}/holidays/", headers=get_headers(), timeout=5)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/api/holidays', methods=['POST'])
@role_required(['hr'])
def add_holiday_api():
    try:
        data = request.get_json() or {}
        res = requests.post(f"{BASE_URL}/holidays/", json=data, headers=get_headers(), timeout=5)
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
        
        attendance_res = requests.get(f"{BASE_URL}/attendance/", headers=get_headers())
        attendance_data = extract_list(attendance_res.json(), 'attendance', 'data') if attendance_res.status_code == 200 else []
        
        leaves_res = requests.get(f"{BASE_URL}/leaves/", headers=get_headers())
        leave_data = extract_list(leaves_res.json(), 'leaves', 'data') if leaves_res.status_code == 200 else []
        
        leave_balance = 0
        balance_data = fetch_leave_balance_helper(session.get('employee_name'))
        if balance_data:
            leave_balance = balance_data.get("summary", {}).get("remaining_leaves", 0)

        holidays_count = 0
        try:
            hol_res = requests.get(f"{BASE_URL}/holidays", headers=get_headers())
            if hol_res.status_code == 200:
                hols = extract_list(hol_res.json(), 'holidays', 'data')
                holidays_count = len([h for h in hols if from_date <= h.get("date", "")[:10] <= to_date])
        except: pass
        
        current_user = session.get('employee_name')
        user_role = session.get('role')
        
        # Determine target employee (default to self)
        target_employee = request.args.get('employee_name') or current_user
        
        # Security check: employees can only see themselves
        if user_role == 'employee':
            target_employee = current_user
        
        attendance_data = [a for a in attendance_data if record_belongs_to_person(a, target_employee)]
        leave_data = [l for l in leave_data if record_belongs_to_person(l, target_employee)]
        
        # Further filter by date range and calculate days
        final_leaves = []
        for l in leave_data:
            if l.get('start_date') and from_date <= l.get('start_date')[:10] <= to_date:
                # Calculate days if missing
                if not l.get('days'):
                    try:
                        s = datetime.strptime(l['start_date'][:10], '%Y-%m-%d')
                        e = datetime.strptime(l['end_date'][:10], '%Y-%m-%d')
                        l['days'] = (e - s).days + 1
                    except: l['days'] = 1
                final_leaves.append(l)
        leave_data = final_leaves
        
        # Calculate balance for target employee
        leave_balance = 0
        balance_data = fetch_leave_balance_helper(target_employee)
        if balance_data:
            leave_balance = balance_data.get("summary", {}).get("remaining_leaves", 0)

        # Get employee list and target employee details
        emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers())
        all_employees = []
        display_name = target_employee
        display_emp_id = 'N/A'
        
        if emp_res.status_code == 200:
            emp_list = extract_list(emp_res.json(), 'employees', 'data')
            if user_role in ['hr', 'admin', 'manager']:
                all_employees = emp_list
            
            for emp in emp_list:
                if names_match(person_system_name(emp), target_employee):
                    display_name = person_system_name(emp) or target_employee
                    display_emp_id = pick(emp, 'employee_id', 'id', default='N/A')
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
            leaves_data = extract_list(leaves_res.json(), 'leaves', 'data')
            used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}
            quotas = {"casual": 12, "sick": 10, "earned": 8, "total": 30}

            for leave in leaves_data:
                emp = pick(leave, 'employee_name', 'teamMemberName', 'name')
                if names_match(emp, employee_name) and leave.get("status") == "approved":
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

@work_bp.route('/manager/timesheets/pending')
@role_required(['admin', 'hr', 'manager'])
def get_pending_timesheets():
    try:
        # Backend endpoint discovered: /timesheets/pending-approvals/
        res = requests.get(f"{BASE_URL}/timesheets/pending-approvals/", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify(res.json()), 200
        return jsonify({"success": False, "error": "Failed to fetch pending timesheets"}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/manager/timesheets/approve', methods=['POST'])
@role_required(['admin', 'hr', 'manager'])
def approve_timesheet():
    try:
        data = request.json
        ts_id = data.get('timesheet_id')
        if not ts_id:
            return jsonify({"success": False, "error": "Timesheet ID required"}), 400
            
        # Backend endpoint discovered: /timesheets/<id>/approve/
        res = requests.post(f"{BASE_URL}/timesheets/{ts_id}/approve/", headers=get_headers(), timeout=10)
        if res.status_code in [200, 201]:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/manager/timesheets/reject', methods=['POST'])
@role_required(['admin', 'hr', 'manager'])
def reject_timesheet():
    try:
        data = request.json
        ts_id = data.get('timesheet_id')
        reason = data.get('rejection_reason') or data.get('reason')
        if not ts_id:
            return jsonify({"success": False, "error": "Timesheet ID required"}), 400
            
        # Backend endpoint discovered: /timesheets/<id>/reject/
        payload = {"reason": reason}
        res = requests.post(f"{BASE_URL}/timesheets/{ts_id}/reject/", json=payload, headers=get_headers(), timeout=10)
        if res.status_code in [200, 201]:
            return jsonify({"success": True}), 200
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/api/timesheets/day')
@role_required(['admin', 'hr', 'manager', 'employee'])
def get_timesheet_day_details():
    try:
        date = request.args.get('date')
        employee_name = request.args.get('employee_name') or session.get('employee_name')
        
        # Backend endpoint discovered: /timesheets/day/
        params = {"date": date, "employee_name": employee_name}
        res = requests.get(f"{BASE_URL}/timesheets/day/", params=params, headers=get_headers(), timeout=10)
        
        if res.status_code == 200:
            return jsonify(res.json()), 200
        return jsonify({"success": False, "error": "Failed to fetch day details"}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@work_bp.route('/api/timesheets/calendar')
@role_required(['admin', 'hr', 'manager', 'employee'])
def get_timesheet_calendar():
    try:
        year = request.args.get('year', type=int)
        month = request.args.get('month', type=int)
        
        # Backend endpoint discovered: /timesheets/calendar/
        params = {"year": year, "month": month}
        res = requests.get(f"{BASE_URL}/timesheets/calendar/", params=params, headers=get_headers(), timeout=10)
        
        if res.status_code == 200:
            return jsonify(res.json()), 200
        return jsonify({"success": False, "error": "Failed to fetch calendar data"}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
