import os
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers, role_required

projects_bp = Blueprint('projects', __name__)

def load_projects():
    try:
        projects_file = os.path.join(os.getcwd(), 'projects.json')
        if os.path.exists(projects_file):
            with open(projects_file, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error loading projects.json: {e}")
    return []

def save_projects(db):
    projects_file = os.path.join(os.getcwd(), 'projects.json')
    with open(projects_file, 'w') as f:
        json.dump(db, f, indent=4)

@projects_bp.route('/projects')
@role_required(['admin', 'hr', 'manager', 'employee'])
def projects_list():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        projects_db = load_projects()
        user_role = session.get('role')
        user_name = session.get('employee_name')
        
        # Determine which projects to show based on role
        projects_to_show = []
        if user_role in ['hr', 'admin']:
            projects_to_show = projects_db
        elif user_role == 'manager':
            projects_to_show = [proj for proj in projects_db if proj.get('assigned_manager') == user_name]
        elif user_role == 'employee':
            for proj in projects_db:
                members = proj.get('team_members', [])
                if not isinstance(members, list): continue
                # Handle both string names and object-based team members safely
                for m in members:
                    m_name = m if isinstance(m, str) else (m.get('name') or m.get('employee_name'))
                    if m_name == user_name:
                        projects_to_show.append(proj)
                        break
        
        # Fetch managers list for the Edit Project modal (critical for template rendering)
        managers = []
        try:
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=5)
            if emp_res.status_code == 200:
                managers = [emp for emp in emp_res.json().get("employees", []) if emp.get('role') == 'manager']
        except Exception as e:
            print(f"Non-critical error fetching managers: {e}")

        return render_template('projects.html', 
                               projects=projects_to_show, 
                               user_role=user_role,
                               managers=managers)
                               
    except Exception as e:
        print(f"Projects List Crash: {e}")
        flash("Unable to load projects at this time.", "danger")
        return render_template('projects.html', projects=[], user_role=session.get('role'), managers=[])

@projects_bp.route('/create_project', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def create_project():
    if request.method == 'GET':
        try:
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
            employees = emp_res.json().get("employees", []) if emp_res.status_code == 200 else []
            managers = [emp for emp in employees if emp.get('role') == 'manager']     
            return render_template('create_project.html', managers=managers)
        except Exception as e:
            return render_template('create_project.html', managers=[])
    elif request.method == 'POST':
        try:
            data = request.get_json()
            projects_db = load_projects()
            max_id = max([p['id'] for p in projects_db], default=0)
            new_project = {
                'id': max_id + 1,
                'name': data.get('name'),
                'start_date': data.get('start_date'),
                'end_date': data.get('end_date'),
                'customer_name': data.get('customer_name'),
                'customer_contact': data.get('customer_contact'),
                'customer_phone': data.get('customer_phone'),
                'customer_email': data.get('customer_email'),
                'assigned_manager': data.get('assigned_manager'),
                'created_by': session.get('employee_name'),
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'active',
                'team_members': []
            }
            projects_db.append(new_project)
            save_projects(projects_db)
            return jsonify({"success": True, "message": "Project created successfully", "redirect": url_for('projects.projects_list')})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/project_details/<int:project_id>')
@role_required(['admin', 'manager', 'employee'])
def project_detail_view(project_id):
    project = next((p for p in load_projects() if p.get('id') == project_id), None)
    if not project:
        flash("Project not found", "danger")
        return redirect(url_for('projects.projects_list'))
    return render_template('project_details.html', project=project, user_role=session.get('role'))

@projects_bp.route('/get_project_details/<int:project_id>')
@role_required(['hr', 'manager', 'employee'])
def get_project_details(project_id):
    project = next((p for p in load_projects() if p.get('id') == project_id), None)
    if project: return jsonify({"success": True, "project": project})
    return jsonify({"success": False, "error": "Project not found"}), 404

@projects_bp.route('/api/employees_with_allocation')
@role_required(['admin', 'hr', 'manager'])
def api_employees_with_allocation():
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
        employees = res.json().get("employees", []) if res.status_code == 200 else []
        projects_db = load_projects()
        allocations = {}
        for proj in projects_db:
            if proj.get('status') == 'active':
                for member in proj.get('team_members', []):
                    name = member if isinstance(member, str) else (member.get('name') or member.get('employee_name'))
                    if not name: continue
                    alloc = int(member.get('allocation', 100) if isinstance(member, dict) else 100)
                    allocations[name] = allocations.get(name, 0) + alloc
        
        result = []
        for emp in employees:
            if emp.get('role') == 'employee':
                name = emp.get("name")
                total_alloc = allocations.get(name, 0)
                result.append({
                    "name": name, "employee_name": name, "role": emp.get("role"),
                    "workload": {"total_allocation": total_alloc},
                    "available_capacity": max(0, 150 - total_alloc),
                    "availability_status": "fully_allocated" if total_alloc >= 150 else "available"
                })
        return jsonify({"success": True, "employees": result})
    except Exception as e: return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/add_team_members', methods=['POST'])
@role_required(['admin', 'manager', 'hr'])
def add_team_members():
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        team_members = data.get('team_members', [])
        projects_db = load_projects()
        project = next((p for p in projects_db if p.get('id') == project_id), None)
        if project:
            project.setdefault('team_members', [])
            for m in team_members:
                m_name = m.get('name') if isinstance(m, dict) else m
                if not any((x if isinstance(x, str) else x.get('name')) == m_name for x in project['team_members']):
                    project['team_members'].append(m)
            save_projects(projects_db)
            return jsonify({"success": True, "message": "Team members added"})
        return jsonify({"success": False, "error": "Project not found"}), 404
    except Exception as e: return jsonify({"success": False, "error": str(e)}), 500

@projects_bp.route('/update_project', methods=['POST'])
@role_required(['admin', 'hr'])
def update_project():
    data = request.get_json()
    projects_db = load_projects()
    project = next((p for p in projects_db if p.get('id') == data.get('id')), None)
    if project:
        project.update({k: data.get(k) for k in ['name', 'start_date', 'end_date', 'customer_name', 'assigned_manager']})
        save_projects(projects_db)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Project not found"}), 404

@projects_bp.route('/delete_project/<int:project_id>', methods=['POST'])
@role_required(['admin', 'hr'])
def delete_project(project_id):
    projects_db = load_projects()
    projects_db = [p for p in projects_db if p.get('id') != project_id]
    save_projects(projects_db)
    return jsonify({"success": True})
