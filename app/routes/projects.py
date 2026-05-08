import os
import json
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
from app.utils import BASE_URL, get_headers, role_required

projects_bp = Blueprint('projects', __name__)

def load_projects():
    projects_file = os.path.join(os.getcwd(), 'projects.json')
    if os.path.exists(projects_file):
        with open(projects_file, 'r') as f:
            return json.load(f)
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
    
    projects_db = load_projects()
    user_role = session.get('role')
    user_name = session.get('employee_name')
    
    if user_role in ['hr', 'admin']:
        projects_to_show = projects_db
    elif user_role == 'manager':
        projects_to_show = [proj for proj in projects_db if proj.get('assigned_manager') == user_name]
    elif user_role == 'employee':
        projects_to_show = [proj for proj in projects_db if user_name in proj.get('team_members', [])]
    else:
        projects_to_show = []
        
    return render_template('projects.html', projects=projects_to_show, user_role=user_role)

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

# (Other project routes: update, delete, add_team_members can be added here)
