import os
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers, role_required
from app.api_helpers import (
    names_match,
    extract_list,
    normalize_people_list,
    parse_project_response,
    person_system_name,
    person_role,
    person_display_name,
    pick,
    project_team_members,
)

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/projects')
@role_required(['admin', 'hr', 'manager', 'employee'])
def projects_list():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        user_role = str(session.get('role', '')).lower().strip()
        user_name = session.get('employee_name') or session.get('user') or session.get('username')
        
        # 1. Fetch ALL projects from backend (trailing slash required)
        res = requests.get(f"{BASE_URL}/projects/", headers=get_headers(), timeout=10)
        all_projects = []
        if res.status_code == 200:
            data = res.json()
            raw_projects = extract_list(data, 'projects', 'data')
            
            # Load local projects.json for team_members and manager lookups
            # The README specifies projects.json is used for lookups across the dashboard and projects.
            local_projects = {}
            if os.path.exists('projects.json'):
                try:
                    with open('projects.json', 'r') as f:
                        for lp in json.load(f):
                            pid = str(lp.get('id') or lp.get('project_id', ''))
                            if pid:
                                local_projects[pid] = lp
                except Exception as e:
                    print(f"Failed to load projects.json: {e}")

            # Standardize project objects (ensure 'id' key exists)
            for p in raw_projects:
                if isinstance(p, dict):
                    pid = str(p.get('id') or p.get('project_id', ''))
                    p['id'] = p.get('id') or p.get('project_id')
                    
                    # Merge missing lookup fields from projects.json
                    if pid in local_projects:
                        lp = local_projects[pid]
                        if not p.get('team_members') and lp.get('team_members'):
                            p['team_members'] = lp['team_members']
                        if not p.get('assigned_manager') and lp.get('assigned_manager'):
                            p['assigned_manager'] = lp['assigned_manager']
                            
                    all_projects.append(p)
        
        # 2. Filter projects based on role (Frontend side filtering to match current behavior)
        projects_to_show = []
        if user_role in ['hr', 'admin']:
            projects_to_show = all_projects
        elif user_role in ['manager', 'employee']:
            for proj in all_projects:
                # Check if user is the manager
                is_manager = names_match(pick(proj, 'assigned_manager', 'manager_name', 'assigned_manager_name', 'manager'), user_name)
                # Check if user is a team member
                is_team_member = any(names_match(m.get('employee_name') or m.get('name'), user_name) for m in project_team_members(proj))
                
                if is_manager or is_team_member:
                    projects_to_show.append(proj)
        
        # 3. Fetch managers list for modals
        managers = []
        try:
            emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers(), timeout=5)
            if emp_res.status_code == 200:
                emp_data = emp_res.json()
                all_emps = extract_list(emp_data, 'employees', 'data')
                managers = [emp for emp in all_emps if person_role(emp) == 'manager']
        except: pass

        return render_template('projects.html', 
                               projects=projects_to_show, 
                               user_role=user_role,
                               managers=managers)
                               
    except Exception as e:
        print(f"Projects List API Error: {e}")
        flash("Connection to backend projects failed.", "danger")
        return render_template('projects.html', projects=[], user_role=session.get('role'), managers=[])

@projects_bp.route('/create_project', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def create_project():
    if request.method == 'GET':
        try:
            emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers(), timeout=5)
            employees = []
            if emp_res.status_code == 200:
                data = emp_res.json()
                employees = extract_list(data, 'employees', 'data')
            managers = [emp for emp in employees if person_role(emp) == 'manager']     
            return render_template('create_project.html', managers=managers)
        except:
            return render_template('create_project.html', managers=[])
            
    elif request.method == 'POST':
        try:
            data = request.get_json()
            # Prepare payload for backend
            payload = {
                'name': data.get('name'),
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
                'customer_name': data.get('customer_name'),
                
                # Contact person keys
                'contact_person': data.get('customer_contact') or data.get('contact_person'),
                'customer_contact': data.get('customer_contact') or data.get('contact_person'),
                
                # Phone keys
                'phone': data.get('customer_phone') or data.get('phone'),
                'customer_phone': data.get('customer_phone') or data.get('phone'),
                
                # Email keys
                'email': data.get('customer_email') or data.get('email'),
                'customer_email': data.get('customer_email') or data.get('email'),
                
                # Manager keys
                'assigned_manager': data.get('assigned_manager'),
                'assigned_manager_name': data.get('assigned_manager'),
                'manager_name': data.get('assigned_manager'),
                
                'status': 'active'
            }
            res = requests.post(f"{BASE_URL}/projects/", json=payload, headers=get_headers(), timeout=10)
            if res.status_code in [200, 201]:
                return jsonify({"success": True, "message": "Project created on backend", "redirect": url_for('projects.projects_list')})
            else:
                return jsonify({"success": False, "error": f"Backend error: {res.text}"}), res.status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/get_project_details/<int:project_id>')
@role_required(['hr', 'manager', 'employee', 'admin'])
def get_project_details(project_id):
    try:
        res = requests.get(f"{BASE_URL}/projects/{project_id}", headers=get_headers(), timeout=5)
        if res.status_code == 200:
            project = parse_project_response(res.json())
            project['team_members'] = project_team_members(project)
            return jsonify({"success": True, "project": project})
        return jsonify({"success": False, "error": "Project not found on backend"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/api/employees_with_allocation')
@role_required(['admin', 'hr', 'manager'])
def api_employees_with_allocation():
    try:
        # Use total_utilization from employee object  Eno need for a second /projects call
        emp_res = requests.get(f"{BASE_URL}/employees/", headers=get_headers(), timeout=8)
        employees = []
        if emp_res.status_code == 200:
            data = emp_res.json()
            employees = extract_list(data, 'employees', 'data')

        result = []
        for emp in employees:
            if person_role(emp) == 'employee':
                name = person_system_name(emp)
                total_alloc = int(emp.get('total_utilization', 0) or 0)
                result.append({
                    "name": name,
                    "employee_name": name,
                    "display_name": person_display_name(emp) or name,
                    "role": person_role(emp),
                    "workload": {
                        "total_allocation": total_alloc,
                        "projects": []
                    },
                    "available_capacity": max(0, 100 - total_alloc),
                    "availability_status": "fully_allocated" if total_alloc >= 100 else "available"
                })
        return jsonify({"success": True, "employees": result})
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/add_team_members', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def add_team_members():
    """Add or update a team member on a project via POST /projects/assign."""
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        team_members = data.get('team_members', [])

        errors = []
        for member in team_members:
            employee_name = member.get('name') or member.get('employee_name')
            payload = {
                "project_id": project_id,
                "employee_name": employee_name,
                "is_billable": member.get('is_billable', True),
                "billable_percentage": member.get('billable_percentage', member.get('allocation', 100))
            }
            res = requests.post(f"{BASE_URL}/projects/assign/", json=payload, headers=get_headers(), timeout=10)
            if res.status_code not in [200, 201]:
                errors.append(f"{employee_name}: {res.text}")

        if errors:
            return jsonify({"success": False, "error": "; ".join(errors)}), 400
        return jsonify({"success": True, "message": "Team members assigned successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/remove_team_member', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def remove_team_member():
    """Remove a team member from a project via DELETE /projects/assign."""
    try:
        data = request.get_json()
        payload = {
            "project_id": data.get('project_id'),
            "employee_name": data.get('employee_name')
        }
        res = requests.delete(f"{BASE_URL}/projects/assign/", json=payload, headers=get_headers(), timeout=10)
        if res.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Member removed successfully"})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@projects_bp.route('/update_member_billing', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def update_member_billing():
    """Update billing status/percentage for a team member via PUT /projects/assign."""
    try:
        data = request.get_json()
        payload = {
            "project_id": data.get('project_id'),
            "employee_name": data.get('employee_name'),
            "is_billable": data.get('is_billable'),
            "billable_percentage": data.get('billable_percentage')
        }
        res = requests.put(f"{BASE_URL}/projects/assign/", json=payload, headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "message": "Billing updated successfully"})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/update_project', methods=['POST'])
@role_required(['admin', 'hr'])
def update_project():
    try:
        data = request.get_json()
        project_id = data.get('id')
        payload = {
            'name': data.get('name'),
            'start_date': data.get('start_date'),
            'end_date': data.get('end_date'),
            'customer_name': data.get('customer_name'),
            
            # Contact person keys
            'contact_person': data.get('customer_contact') or data.get('contact_person'),
            'customer_contact': data.get('customer_contact') or data.get('contact_person'),
            
            # Phone keys
            'phone': data.get('customer_phone') or data.get('phone'),
            'customer_phone': data.get('customer_phone') or data.get('phone'),
            
            # Email keys
            'email': data.get('customer_email') or data.get('email'),
            'customer_email': data.get('customer_email') or data.get('email'),
            
            # Manager keys
            'assigned_manager': data.get('assigned_manager'),
            'assigned_manager_name': data.get('assigned_manager'),
            'manager_name': data.get('assigned_manager'),
            
            'status': data.get('status', 'active')
        }
        
        res = requests.put(f"{BASE_URL}/projects/{project_id}", json=payload, headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "message": "Project updated on backend"})
        return jsonify({"success": False, "error": f"Backend failed: {res.text}"}), res.status_code
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/delete_project/<int:project_id>', methods=['POST'])
@role_required(['admin', 'hr'])
def delete_project(project_id):
    try:
        res = requests.delete(f"{BASE_URL}/projects/{project_id}", headers=get_headers(), timeout=10)
        if res.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Project deleted on backend"})
        return jsonify({"success": False, "error": f"Backend failed: {res.text}"}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
