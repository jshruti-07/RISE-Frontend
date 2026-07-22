import requests
from flask import Blueprint, render_template, request, jsonify, session
from app.utils import BASE_URL, get_headers, role_required

superadmin_bp = Blueprint('superadmin', __name__)

@superadmin_bp.route('/access-control', methods=['GET'])
@role_required(['superadmin'])
def access_control():
    """Render the Access Control UI for Superadmin."""
    return render_template('access_control.html')

@superadmin_bp.route('/api/admin/permissions', methods=['GET'])
@role_required(['superadmin'])
def api_get_permissions():
    res = requests.get(f"{BASE_URL}/admin/permissions", headers=get_headers())
    return jsonify(res.json()), res.status_code

@superadmin_bp.route('/api/admin/permissions/<int:permission_id>/role/<string:role>', methods=['PATCH'])
@role_required(['superadmin'])
def api_toggle_permission(permission_id, role):
    res = requests.patch(
        f"{BASE_URL}/admin/permissions/{permission_id}/role/{role}",
        json=request.get_json(),
        headers=get_headers()
    )
    return jsonify(res.json()), res.status_code

@superadmin_bp.route('/api/admin/permissions/reset-defaults', methods=['POST'])
@role_required(['superadmin'])
def api_reset_defaults():
    res = requests.post(
        f"{BASE_URL}/admin/permissions/reset-defaults",
        json=request.get_json(),
        headers=get_headers()
    )
    return jsonify(res.json()), res.status_code

@superadmin_bp.route('/api/admin/permissions/audit-log', methods=['GET'])
@role_required(['superadmin'])
def api_get_audit_log():
    res = requests.get(f"{BASE_URL}/admin/permissions/audit-log", headers=get_headers())
    return jsonify(res.json()), res.status_code
