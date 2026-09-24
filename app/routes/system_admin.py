import requests
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from app.utils import BASE_URL, get_headers, role_required

system_admin_bp = Blueprint('system_admin', __name__, url_prefix='/system-admin')

@system_admin_bp.route('/system-access')
@role_required(['system_admin', 'superadmin', 'admin'])
def system_access():
    headers = get_headers()
    try:
        resp = requests.get(f"{BASE_URL}/offboarding/cases", headers=headers)
        cases = resp.json().get('cases', []) if resp.status_code == 200 else []
    except Exception as e:
        cases = []
        flash("Could not connect to backend service.", "danger")
    return render_template('system_admin/system_access.html', cases=cases)

@system_admin_bp.route('/user-accounts')
@role_required(['system_admin', 'superadmin', 'admin'])
def user_accounts():
    headers = get_headers()
    try:
        resp = requests.get(f"{BASE_URL}/auth/admin/user-accounts", headers=headers)
        users = resp.json().get('users', []) if resp.status_code == 200 else []
    except Exception as e:
        users = []
        flash("Could not connect to backend service.", "danger")
    return render_template('system_admin/user_accounts.html', users=users)

@system_admin_bp.route('/user-accounts/<int:user_id>/toggle', methods=['POST'])
@role_required(['system_admin', 'superadmin', 'admin'])
def toggle_user_account(user_id):
    headers = get_headers()
    try:
        resp = requests.post(f"{BASE_URL}/auth/admin/users/{user_id}/toggle-status", headers=headers)
        if resp.status_code == 200:
            flash(resp.json().get('message', 'Account status updated.'), 'success')
        else:
            flash(resp.json().get('error', 'Failed to toggle account.'), 'danger')
    except Exception as e:
        flash(f"Error toggling account: {e}", 'danger')
    return redirect(url_for('system_admin.user_accounts'))

@system_admin_bp.route('/audit-logs')
@role_required(['system_admin', 'superadmin', 'admin'])
def audit_logs():
    headers = get_headers()
    try:
        resp = requests.get(f"{BASE_URL}/auth/admin/audit-logs", headers=headers)
        logs = resp.json().get('logs', []) if resp.status_code == 200 else []
    except Exception as e:
        logs = []
        flash("Could not fetch audit logs.", "danger")
    return render_template('system_admin/audit_logs.html', logs=logs)
