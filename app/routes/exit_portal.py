import requests
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from app.utils import BASE_URL

exit_portal_bp = Blueprint('exit_portal_ui', __name__, url_prefix='/exit-portal')

@exit_portal_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('exit_portal_token'):
        return redirect(url_for('exit_portal_ui.dashboard'))
    return render_template('offboarding/exit_portal.html', mode='login')

@exit_portal_bp.route('/api/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json() or {}
    personal_email = data.get('personal_email')
    try:
        resp = requests.post(f"{BASE_URL}/exit-portal/request-otp", json={"personal_email": personal_email})
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@exit_portal_bp.route('/api/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json() or {}
    personal_email = data.get('personal_email')
    otp = data.get('otp')
    try:
        resp = requests.post(f"{BASE_URL}/exit-portal/verify-otp", json={"personal_email": personal_email, "otp": otp})
        if resp.status_code == 200:
            res_data = resp.json()
            session['exit_portal_token'] = res_data.get('token')
            session['exit_portal_user'] = res_data.get('employee')
            return jsonify({"success": True, "redirect": url_for('exit_portal_ui.dashboard')})
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@exit_portal_bp.route('/dashboard')
def dashboard():
    token = session.get('exit_portal_token')
    if not token:
        flash("Please log in using your personal email and verification code.", "info")
        return redirect(url_for('exit_portal_ui.login'))
    
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{BASE_URL}/exit-portal/status", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return render_template('offboarding/exit_portal.html', mode='dashboard', exit_data=data)
        elif resp.status_code == 401:
            session.pop('exit_portal_token', None)
            flash("Session expired. Please request a new verification code.", "warning")
            return redirect(url_for('exit_portal_ui.login'))
        else:
            flash(resp.json().get('error', 'Failed to retrieve exit records.'), "danger")
            return redirect(url_for('exit_portal_ui.login'))
    except Exception as e:
        flash(f"Connection error: {e}", "danger")
        return redirect(url_for('exit_portal_ui.login'))

@exit_portal_bp.route('/logout')
def logout():
    session.pop('exit_portal_token', None)
    session.pop('exit_portal_user', None)
    flash("You have been signed out of the Exit Portal.", "info")
    return redirect(url_for('exit_portal_ui.login'))
