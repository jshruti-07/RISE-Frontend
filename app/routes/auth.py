from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash
import requests
import re
from app.utils import BASE_URL, get_headers, role_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if 'token' in session:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('_flashes', None)
    
    if request.method == 'POST':
        payload = {
            "username": request.form.get("username"),
            "password": request.form.get("password")
        }
        try:
            res = requests.post(f"{BASE_URL}/auth/login", json=payload, timeout=10)
            data = res.json()
        except requests.exceptions.Timeout:
            print("LOGIN TIMEOUT: The authentication service took too long to respond.")
            error_msg = "Authentication service timed out. Please try again."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 504
            flash(error_msg, "danger")
            return render_template('login.html')
        except requests.exceptions.ConnectionError:
            print("LOGIN CONNECTION ERROR: Unable to connect to backend server.")
            error_msg = "Unable to connect to backend server. Please contact support if the issue persists."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 503
            flash(error_msg, "danger")
            return render_template('login.html')
        except Exception as e:
            print("LOGIN ERROR:", e)
            error_msg = "Authentication service temporarily unavailable."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": error_msg}), 500
            flash(error_msg, "danger")
            return render_template('login.html')

        if res.status_code == 200 and data.get("success"):
            if 'token' in data and data['token']:
                session['token'] = data['token']
                session['user'] = data['user']['username']
                session['role'] = data['user']['role']
                session['employee_name'] = data['user'].get('employee_name')
                session['original_name'] = data['user'].get('original_name')
                session['full_name'] = data['user'].get('full_name')
                session['display_name'] = data['user'].get('display_name')
                session['employee_id'] = data['user'].get('employee_id') or data['user'].get('id', 'N/A')

                is_superadmin = str(data['user'].get('role', '')).lower() == 'superadmin'
                is_onboarding = data['user'].get('is_onboarding', False) or str(data['user'].get('role', '')).lower() == 'onboarding_candidate'
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({
                        "success": True,
                        "password_change_required": data['user'].get("password_change_required", False),
                        "is_onboarding": is_onboarding,
                        "is_superadmin": is_superadmin
                    })
                
                if data['user'].get('password_change_required'):
                    flash("Password change required. Please set a new password to continue.", "warning")
                    return redirect(url_for('auth.change_password'))

                is_onboarding = data['user'].get('is_onboarding', False) or str(data['user'].get('role', '')).lower() == 'onboarding_candidate'
                if is_superadmin:
                    return redirect(url_for('superadmin.access_control'))
                if is_onboarding:
                    return redirect(url_for('onboarding.joinee_dashboard'))

                session.pop('_flashes', None)
                return redirect(url_for('dashboard.dashboard'))

            else:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "error": "Authentication failed - no token received"}), 200
                flash("Authentication failed - no token received", "danger")
                return redirect(url_for('auth.login'))
        else:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": False, "error": data.get("error", "Invalid login")}), 200
            flash(data.get("error", "Invalid login"), "danger")

    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET'])
def forgot_password():
    return render_template('forgot_password.html')

@auth_bp.route('/forgot-password', methods=['POST'])
def handle_forgot_password():
    try:
        data = request.get_json() or {}
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400
        
        res = requests.post(
            f"{BASE_URL}/auth/forgot-password",
            json={'email': email},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        response_data = res.json()
        return jsonify(response_data), res.status_code
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Authentication service timed out. Please try again.'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Unable to connect to backend server.'}), 503
    except Exception as e:
        print("Forgot password error:", e)
        return jsonify({'success': False, 'error': 'Authentication service temporarily unavailable'}), 500

@auth_bp.route('/reset-password', methods=['GET'])
def reset_password():
    token = request.args.get('token', '')
    return render_template('reset_password.html', token=token)

@auth_bp.route('/reset-password', methods=['POST'])
def handle_reset_password():
    try:
        data = request.get_json() or {}
        token = data.get('token', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        if not all([token, new_password, confirm_password]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        if new_password != confirm_password:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
        
        if len(new_password) < 8 or not re.search(r"[A-Z]", new_password) or not re.search(r"[@$!%*?&]", new_password):
            return jsonify({'success': False, 'error': 'Password must be 8+ chars and include a capital and a special character'}), 400
        
        res = requests.post(
            f"{BASE_URL}/auth/reset-password",
            json={
                'token': token,
                'new_password': new_password,
                'confirm_password': confirm_password
            },
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        response_data = res.json()
        return jsonify(response_data), res.status_code
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Authentication service timed out. Please try again.'}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'error': 'Unable to connect to backend server.'}), 503
    except Exception as e:
        print("Reset password error:", e)
        return jsonify({'success': False, 'error': 'Authentication service temporarily unavailable'}), 500

@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        payload = {
            "new_password": request.form.get("new_password"),
            "confirm_password": request.form.get("confirm_password")
        }
        try:
            res = requests.post(f"{BASE_URL}/auth/change-password", json=payload, headers=get_headers(), timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                if data.get("token"):
                    session['token'] = data['token']
                flash("Password changed successfully!", "success")
                return redirect(url_for('dashboard.dashboard'))
            else:
                flash(data.get("error", "Failed to change password"), "danger")
        except requests.exceptions.Timeout:
            flash("Authentication service timed out. Please try again.", "danger")
        except requests.exceptions.ConnectionError:
            flash("Unable to connect to backend server.", "danger")
        except Exception as e:
            print("Password change error:", e)
            flash("Authentication service temporarily unavailable", "danger")
    return render_template('change_password.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
