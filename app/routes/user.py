import requests
from flask import flash, Blueprint, render_template, redirect, url_for, session, request, jsonify
from app.utils import BASE_URL, get_headers, fetch_leave_balance_helper, role_required

user_bp = Blueprint('user', __name__)

@user_bp.route('/profile')
def profile():
    if 'employee_name' not in session:
        return redirect(url_for('auth.login'))
    
    headers = get_headers()
    employee_name = session.get('employee_name')
    
    # Get employee details
    res = requests.get(f"{BASE_URL}/employees", headers=headers)
    employee = {}
    if res.status_code == 200:
        for emp in res.json().get("employees", []):
            if emp.get("name") == employee_name:
                employee = emp
                break
    
    # Get leave balance
    summary = {'remaining_leaves': 0}
    balance_data = fetch_leave_balance_helper(employee_name)
    if balance_data:
        summary = balance_data.get("summary", {})

    # Get bank details
    bank_details = {}
    try:
        bank_res = requests.get(f"{BASE_URL}/bank-details/", headers=headers)
        if bank_res.status_code == 200:
            bank_details = bank_res.json().get("bank_details", {})
    except: pass

    return render_template("profile.html", employee=employee, summary=summary, bank_details=bank_details, percent=0, is_hr_view=False, BASE_URL=BASE_URL)

@user_bp.route('/bank-verification')
@role_required(['admin', 'hr'])
def bank_verification():
    res = requests.get(f"{BASE_URL}/bank-details/", headers=get_headers())
    bank_details = res.json().get("bank_details", []) if res.status_code == 200 else []
    return render_template("bank_admin.html", bank_details=bank_details)

# --- PAYSLIPS ---
@user_bp.route('/payslips')
@role_required(['admin', 'manager', 'employee'])
def payslips():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    try:
        res = requests.get(f"{BASE_URL}/reports/payslips", headers=get_headers(), timeout=10)
        payslips_list = res.json().get("payslips", []) if res.status_code == 200 else []
        return render_template("payslips.html", payslips=payslips_list)
    except Exception as e:
        print(f"Error in payslips route: {e}")
        return render_template("payslips.html", payslips=[], error="Failed to fetch payslips")

# --- PHOTO & UPLOADS ---
@user_bp.route('/api/my-photo')
def api_my_photo():
    if 'token' not in session:
        return jsonify({'photo_url': None}), 200
    if session.get('photo_url'):
        return jsonify({'photo_url': session['photo_url']}), 200
    try:
        emp_name = session.get('employee_name')
        res = requests.get(f"{BASE_URL}/employees", headers=get_headers(), timeout=4)
        if res.status_code == 200:
            for emp in res.json().get('employees', []):
                if emp.get('name') == emp_name:
                    url = emp.get('photo_url') or emp.get('photo') or None
                    if url: session['photo_url'] = url
                    return jsonify({'photo_url': url}), 200
    except: pass
    return jsonify({'photo_url': None}), 200

from flask import Response
@user_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    try:
        res = requests.get(f"{BASE_URL}/uploads/{filename}", 
                          headers={'Authorization': f"Bearer {session.get('token', '')}"}, 
                          stream=True, timeout=10)
        if res.status_code == 200:
            return Response(res.iter_content(chunk_size=8192), 
                           content_type=res.headers.get('Content-Type', 'application/octet-stream'))
        return '', res.status_code
    except: return '', 502

@user_bp.route('/upload-photo', methods=['POST'])
def upload_photo():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    
    file = request.files.get('photo')
    employee_id = request.form.get('employee_id')
    
    # 1. Validate file exists and has a filename
    if not file or file.filename == '':
        flash('Please select a valid photo first.', 'warning')
        return redirect(request.referrer or url_for('user.profile'))

    # 2. Ensure we have an employee ID
    if not employee_id or employee_id == 'None' or employee_id == '':
        try:
            name = session.get('employee_name')
            emp_res = requests.get(f"{BASE_URL}/employees", headers=get_headers())
            if emp_res.status_code == 200:
                employees = emp_res.json().get('employees', [])
                employee_id = next((e.get('id') for e in employees if e.get('name') == name), None)
        except Exception as e:
            print(f"Error fetching employee ID: {e}")

    if not employee_id:
        flash('Could not determine employee identity. Please log in again.', 'danger')
        return redirect(url_for('auth.login'))

    # 3. Process the upload
    try:
        # We use exclude_content_type=True because 'requests' sets the boundary automatically for files
        headers = get_headers(exclude_content_type=True)
        
        upload_data = {'photo': (file.filename, file.read(), file.mimetype)}
        res = requests.post(
            f"{BASE_URL}/employees/{employee_id}/photo",
            files=upload_data,
            headers=headers,
            timeout=15
        )

        if res.status_code == 200:
            resp_data = res.json()
            session['photo_url'] = resp_data.get('photo_url')
            flash('Profile photo updated successfully!', 'success')
        else:
            error_msg = res.json().get('error', 'Upload failed on server')
            flash(f'Upload failed: {error_msg}', 'danger')
            
    except Exception as e:
        print(f"Photo upload exception: {e}")
        flash('An error occurred while uploading your photo. Please try again.', 'danger')

    return redirect(request.referrer or url_for('user.profile'))