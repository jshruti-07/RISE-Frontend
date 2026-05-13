import os
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers, role_required

projects_bp = Blueprint('projects', __name__)

@projects_bp.route('/projects')
@role_required(['admin', 'hr', 'manager', 'employee'])
def projects_list():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        user_role = str(session.get('role', '')).lower().strip()
        user_name = session.get('employee_name')
        
        # 1. Fetch ALL projects from backend
        res = requests.get(f"{BASE_URL}/projects", headers=get_headers(), timeout=10)
        all_projects = []
        if res.status_code == 200:
            data = res.json()
            raw_projects = data.get("projects", []) if isinstance(data, dict) else data
            # Standardize project objects (ensure 'id' key exists)
            for p in raw_projects:
                if isinstance(p, dict):
                    if 'id' not in p and 'project_id' in p:
                        p['id'] = p['project_id']
                    all_projects.append(p)
        
        # 2. Filter projects based on role (Frontend side filtering to match current behavior)
        projects_to_show = []
        if user_role in ['hr', 'admin']:
            projects_to_show = all_projects
        elif user_role == 'manager':
            # Manager sees projects where they are assigned as manager
            projects_to_show = [p for p in all_projects if str(p.get('assigned_manager') or p.get('manager_name') or '').strip() == str(user_name).strip()]
        elif user_role == 'employee':
            # Employee sees projects where they are in team_members
            for proj in all_projects:
                members = proj.get('team_members', [])
                if not isinstance(members, list): continue
                for m in members:
                    m_name = m if isinstance(m, str) else (m.get('name') or m.get('employee_name'))
                    if str(m_name).strip() == str(user_name).strip():
                        projects_to_show.append(proj)
                        break
        
        # 3. Fetch managers list for modals
        managers = []
        try:
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=5)
            if emp_res.status_code == 200:
                emp_data = emp_res.json()
                all_emps = emp_data.get("employees", []) if isinstance(emp_data, dict) else emp_data
                managers = [emp for emp in all_emps if isinstance(emp, dict) and str(emp.get('role', '')).lower() == 'manager']
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
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=5)
            employees = []
            if emp_res.status_code == 200:
                data = emp_res.json()
                employees = data.get("employees", []) if isinstance(data, dict) else data
            managers = [emp for emp in employees if isinstance(emp, dict) and str(emp.get('role', '')).lower() == 'manager']     
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
                'customer_contact': data.get('customer_contact') or data.get('contact_person'),
                'customer_phone': data.get('customer_phone'),
                'customer_email': data.get('customer_email'),
                'assigned_manager': data.get('assigned_manager'),
                'status': 'active'
            }
            res = requests.post(f"{BASE_URL}/projects", json=payload, headers=get_headers(), timeout=10)
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
            data = res.json()
            project = data.get("project") if isinstance(data, dict) else data
            return jsonify({"success": True, "project": project})
        return jsonify({"success": False, "error": "Project not found on backend"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/api/employees_with_allocation')
@role_required(['admin', 'hr', 'manager'])
def api_employees_with_allocation():
    try:
        # 1. Fetch employees
        emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=5)
        employees = []
        if emp_res.status_code == 200:
            data = emp_res.json()
            employees = data.get("employees", []) if isinstance(data, dict) else data
            
        # 2. Fetch all projects to calculate allocations
        proj_res = requests.get(f"{BASE_URL}/projects", headers=get_headers(), timeout=10)
        all_projects = []
        if proj_res.status_code == 200:
            data = proj_res.json()
            all_projects = data.get("projects", []) if isinstance(data, dict) else data
            
        allocations = {}
        for proj in all_projects:
            if str(proj.get('status', '')).lower() == 'active':
                for member in proj.get('team_members', []):
                    name = member if isinstance(member, str) else (member.get('name') or member.get('employee_name'))
                    if not name: continue
                    alloc = int(member.get('allocation', 100) if isinstance(member, dict) else 100)
                    allocations[name] = allocations.get(name, 0) + alloc
        
        result = []
        for emp in employees:
            if str(emp.get('role', '')).lower() == 'employee':
                name = emp.get("name")
                total_alloc = allocations.get(name, 0)
                result.append({
                    "name": name, "employee_name": name, "role": emp.get("role"),
                    "workload": {"total_allocation": total_alloc},
                    "available_capacity": max(0, 100 - total_alloc),
                    "availability_status": "fully_allocated" if total_alloc >= 100 else "available"
                })
        return jsonify({"success": True, "employees": result})
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/add_team_members', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def add_team_members():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        team_members = data.get('team_members', [])
        
        # Backend might have a specific endpoint for assignment
        # For now, let's assume we can PUT to /projects/<id> to update members
        # Or if there is an /assignments endpoint
        payload = {"team_members": team_members}
        res = requests.put(f"{BASE_URL}/projects/{project_id}", json=payload, headers=get_headers(), timeout=10)
        
        if res.status_code == 200:
            return jsonify({"success": True, "message": "Team members updated on backend"})
        return jsonify({"success": False, "error": f"Backend failed: {res.text}"}), res.status_code
    except Exception as e: 
        return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/update_project', methods=['POST'])
@role_required(['admin', 'hr'])
def update_project():
    try:
        data = request.get_json()
        project_id = data.get('id')
        payload = {k: data.get(k) for k in ['name', 'start_date', 'end_date', 'customer_name', 'assigned_manager', 'status']}
        
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
