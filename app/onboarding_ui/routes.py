from flask import render_template, redirect, url_for, request, session, Response, abort, jsonify
from app.utils import role_required, BASE_URL, get_headers
from app.onboarding_ui import onboarding_bp
import requests


@onboarding_bp.route('/')
@role_required(['hr', 'admin', 'superadmin'])
def dashboard():
    return render_template('onboarding/dashboard.html', BASE_URL="", token=session.get('token'))


@onboarding_bp.route('/joinee-dashboard')
def joinee_dashboard():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    role = str(session.get('role', '')).lower().strip()
    if role != 'onboarding_candidate':
        return redirect(url_for('dashboard.dashboard'))
    return render_template(
        'joinee/dashboard.html',
        BASE_URL="",
        token=session.get('token'),
        joinee_name=session.get('full_name') or session.get('display_name') or session.get('employee_name', 'New Joinee')
    )


# ── PROXY ENDPOINTS (Forward browser calls to backend API on server localhost) ──

@onboarding_bp.route('/stats', methods=['GET'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_stats():
    try:
        res = requests.get(f"{BASE_URL}/onboarding/stats", headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/joinees', methods=['GET', 'POST'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_joinees():
    try:
        if request.method == 'POST':
            res = requests.post(f"{BASE_URL}/onboarding/joinees", json=request.get_json() or {}, headers=get_headers(), timeout=15)
        else:
            res = requests.get(f"{BASE_URL}/onboarding/joinees", params=request.args, headers=get_headers(), timeout=15)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/joinees/<int:joinee_id>', methods=['GET', 'DELETE'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_joinee_detail(joinee_id):
    try:
        if request.method == 'DELETE':
            res = requests.delete(f"{BASE_URL}/onboarding/joinees/{joinee_id}", headers=get_headers(), timeout=10)
        else:
            res = requests.get(f"{BASE_URL}/onboarding/joinees/{joinee_id}", headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/joinees/<int:joinee_id>/summary', methods=['GET'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_joinee_summary(joinee_id):
    try:
        res = requests.get(f"{BASE_URL}/onboarding/joinees/{joinee_id}/summary", headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/declaration/<int:joinee_id>/review', methods=['PUT'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_declaration_review(joinee_id):
    try:
        res = requests.put(f"{BASE_URL}/onboarding/declaration/{joinee_id}/review", json=request.get_json() or {}, headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/documents/<int:document_id>/verify', methods=['PUT'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_document_verify(document_id):
    try:
        res = requests.put(f"{BASE_URL}/onboarding/documents/{document_id}/verify", json=request.get_json() or {}, headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/joinees/<int:joinee_id>/migrate-login', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_migrate_login(joinee_id):
    try:
        res = requests.post(f"{BASE_URL}/onboarding/joinees/{joinee_id}/migrate-login", headers=get_headers(), timeout=15)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/joinees/<int:joinee_id>/prefill', methods=['GET'])
@role_required(['hr', 'admin', 'superadmin'])
def api_onboarding_prefill(joinee_id):
    try:
        res = requests.get(f"{BASE_URL}/onboarding/joinees/{joinee_id}/prefill", headers=get_headers(), timeout=10)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/json'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@onboarding_bp.route('/documents/<int:document_id>/view')
def view_document(document_id):
    token = session.get('token')
    if not token:
        return redirect(url_for('auth.login'))

    try:
        resp = requests.get(
            f"{BASE_URL}/onboarding/documents/{document_id}/file",
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            timeout=10
        )
        if resp.status_code != 200:
            return abort(resp.status_code)

        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        headers = {k: v for k, v in resp.headers.items() if k.lower() in ['content-type', 'content-disposition', 'content-length']}
        return Response(generate(), headers=headers)
        
    except requests.RequestException as e:
        return f"Error connecting to backend: {str(e)}", 502
    except Exception as e:
        return f"Error retrieving document: {str(e)}", 500