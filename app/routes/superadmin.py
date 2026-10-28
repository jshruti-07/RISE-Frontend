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
    try:
        backend_url = f"{BASE_URL.rstrip('/')}/admin/permissions"
        res = requests.get(backend_url, headers=get_headers(), timeout=10)
        try:
            data = res.json()
        except Exception:
            data = {"success": False, "error": res.text or f"Backend responded with HTTP {res.status_code}"}
        return jsonify(data), res.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Backend server connection error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@superadmin_bp.route('/api/admin/permissions/<int:permission_id>/role/<string:role>', methods=['PATCH', 'POST', 'PUT'])
@role_required(['superadmin'])
def api_toggle_permission(permission_id, role):
    try:
        backend_url = f"{BASE_URL.rstrip('/')}/admin/permissions/{permission_id}/role/{role}"
        payload = request.get_json(silent=True) or {}
        res = requests.patch(
            backend_url,
            json=payload,
            headers=get_headers(),
            timeout=10
        )
        try:
            data = res.json()
        except Exception:
            data = {"success": False, "error": res.text or f"Backend responded with HTTP {res.status_code}"}
        return jsonify(data), res.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Backend server connection error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@superadmin_bp.route('/api/admin/permissions/reset-defaults', methods=['POST'])
@role_required(['superadmin'])
def api_reset_defaults():
    try:
        backend_url = f"{BASE_URL.rstrip('/')}/admin/permissions/reset-defaults"
        payload = request.get_json(silent=True) or {}
        res = requests.post(
            backend_url,
            json=payload,
            headers=get_headers(),
            timeout=15
        )
        try:
            data = res.json()
        except Exception:
            data = {"success": False, "error": res.text or f"Backend responded with HTTP {res.status_code}"}
        return jsonify(data), res.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Backend server connection error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@superadmin_bp.route('/api/admin/permissions/audit-log', methods=['GET'])
@role_required(['superadmin'])
def api_get_audit_log():
    try:
        backend_url = f"{BASE_URL.rstrip('/')}/admin/permissions/audit-log"
        res = requests.get(backend_url, headers=get_headers(), timeout=10)
        try:
            data = res.json()
        except Exception:
            data = {"success": False, "error": res.text or f"Backend responded with HTTP {res.status_code}"}
        return jsonify(data), res.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"success": False, "error": f"Backend server connection error: {str(e)}"}), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
