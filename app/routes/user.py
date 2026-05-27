import requests
from flask import flash, Blueprint, render_template, redirect, url_for, session, request, jsonify
from app.utils import BASE_URL, get_headers, fetch_leave_balance_helper, role_required
from app.api_helpers import (
    names_match,
    extract_list,
    normalize_person,
    parse_profile_response,
    person_system_name,
    pick,
)

user_bp = Blueprint('user', __name__)

DOC_TYPES = (
    'pan_card', 'aadhar_card', 'tenth_cert', 'twelfth_cert',
    'graduation_cert', 'postgrad_cert',
)


def _normalize_upload_relative_path(file_path):
    """Turn /uploads/documents/x.pdf into documents/x.pdf for the proxy route."""
    if not file_path:
        return None
    path = str(file_path).strip().replace('\\', '/')
    if path.startswith('/uploads/'):
        return path[len('/uploads/'):]
    if path.startswith('uploads/'):
        return path[len('uploads/'):]
    return path.lstrip('/')


def _fetch_employee_documents(employee_name, headers):
    """Load uploaded documents map {doc_type: file_path} from the backend API."""
    documents = {}
    if not employee_name:
        return documents
    try:
        res = requests.get(
            f"{BASE_URL}/documents/status",
            headers=headers,
            params={'employee_name': employee_name},
            timeout=10,
        )
        if res.status_code == 200:
            rows = res.json().get('documents', [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get('doc_type') and row.get('file_path'):
                        documents[row['doc_type']] = row['file_path']
            return documents
    except Exception as e:
        print(f'Documents status fetch failed: {e}')

    # Fallback: legacy endpoint (current user only)
    try:
        res = requests.get(f"{BASE_URL}/documents/my-status", headers=headers, timeout=10)
        if res.status_code == 200:
            rows = res.json().get('documents', [])
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and row.get('doc_type') and row.get('file_path'):
                        documents[row['doc_type']] = row['file_path']
    except Exception as e:
        print(f'Documents my-status fetch failed: {e}')
    return documents


def _document_view_urls(documents):
    """Build browser-safe view URLs via authenticated frontend proxy."""
    urls = {}
    for doc_type, file_path in (documents or {}).items():
        rel = _normalize_upload_relative_path(file_path)
        if rel:
            urls[doc_type] = url_for('user.serve_upload', filename=rel)
    return urls

def _find_employee_by_name(employee_name, headers=None):
    """Look up employee record by system name (prefix-tolerant)."""
    if not employee_name:
        return {}
    headers = headers or get_headers()
    try:
        res = requests.get(f"{BASE_URL}/employees", headers=headers, timeout=10)
        if res.status_code == 200:
            for emp in extract_list(res.json(), 'employees', 'data'):
                if names_match(person_system_name(emp), employee_name):
                    return normalize_person(emp)
    except Exception as e:
        print(f"Employee lookup failed: {e}")
    return {}


@user_bp.route('/profile')
def profile():
    if 'employee_name' not in session:
        return redirect(url_for('auth.login'))
    
    headers = get_headers()
    employee_name = session.get('employee_name')
    employee = _find_employee_by_name(employee_name, headers)

    if not employee.get('email'):
        try:
            from urllib.parse import quote
            profile_res = requests.get(
                f"{BASE_URL}/profile/{quote(employee_name, safe='')}",
                headers=headers,
                timeout=10,
            )
            if profile_res.status_code == 200:
                profile, _docs = parse_profile_response(profile_res.json())
                if profile:
                    employee = {**employee, **profile}
        except Exception as e:
            print(f'Profile API fallback failed: {e}')

    # Cache employee table id for photo upload (session['employee_id'] is users.id from login)
    if employee.get('id'):
        session['employee_table_id'] = employee['id']
    
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
            bd = bank_res.json().get("bank_details", {})
            if isinstance(bd, list):
                bank_details = next(
                    (b for b in bd if names_match(b.get("employee_name"), employee_name)),
                    {},
                )
            elif isinstance(bd, dict):
                bank_details = bd
    except Exception:
        pass

    documents = _fetch_employee_documents(employee_name, headers)
    document_view_urls = _document_view_urls(documents)
    uploaded_count = sum(1 for doc_type in DOC_TYPES if documents.get(doc_type))
    percent = int((uploaded_count / len(DOC_TYPES)) * 100) if DOC_TYPES else 0

    return render_template(
        "profile.html",
        employee=employee,
        summary=summary,
        bank_details=bank_details,
        documents=documents,
        document_view_urls=document_view_urls,
        percent=percent,
        is_hr_view=False,
        is_own_profile=True,
        BASE_URL=BASE_URL,
    )

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
            for emp in extract_list(res.json(), 'employees', 'data'):
                if names_match(person_system_name(emp), emp_name):
                    url = pick(emp, 'photo_url', 'photo')
                    if url: session['photo_url'] = url
                    return jsonify({'photo_url': url}), 200
    except: pass
    return jsonify({'photo_url': None}), 200

from flask import Response

@user_bp.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Proxy uploaded files from the backend with the user's auth token."""
    if 'token' not in session:
        return '', 401
    try:
        safe_path = filename.lstrip('/').replace('..', '')
        res = requests.get(
            f"{BASE_URL}/uploads/{safe_path}",
            headers={'Authorization': f"Bearer {session.get('token', '')}"},
            stream=True,
            timeout=30,
        )
        if res.status_code == 200:
            content_type = res.headers.get(
                'Content-Type', 'application/octet-stream'
            )
            return Response(
                res.iter_content(chunk_size=8192),
                content_type=content_type,
                headers={'Content-Disposition': 'inline'},
            )
        return '', res.status_code
    except Exception as e:
        print(f'Upload proxy error: {e}')
        return '', 502

@user_bp.route('/upload-photo', methods=['POST'])
def upload_photo():
    if 'token' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        return redirect(url_for('auth.login'))

    file = request.files.get('photo')
    session_emp_name = session.get('employee_name')

    if not file or file.filename == '':
        msg = 'Please select a valid photo first.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'warning')
        return redirect(request.referrer or url_for('user.profile'))

    # Resolve employee table id by session name (not users.id from login)
    employee = _find_employee_by_name(session_emp_name)
    employee_id = employee.get('id') or session.get('employee_table_id')

    if not employee_id:
        msg = 'Could not determine employee identity. Please log in again.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect(url_for('auth.login'))

    # Optional: reject if form id does not match resolved id (tamper check)
    form_emp_id = request.form.get('employee_id')
    if form_emp_id and str(form_emp_id) not in ('', 'None', 'N/A') and str(form_emp_id) != str(employee_id):
        msg = 'Access denied. You can only update your own profile photo.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 403
        flash(msg, 'danger')
        return redirect(url_for('user.profile'))

    try:
        headers = get_headers(exclude_content_type=True)
        upload_data = {'photo': (file.filename, file.read(), file.mimetype)}
        res = requests.post(
            f"{BASE_URL}/employees/{employee_id}/photo",
            files=upload_data,
            headers=headers,
            timeout=15,
        )

        if res.status_code == 200:
            resp_data = res.json() if res.content else {}
            photo_url = (
                resp_data.get('photo_url')
                or resp_data.get('employee', {}).get('photo_url')
                or resp_data.get('employee', {}).get('photo')
            )
            if photo_url:
                session['photo_url'] = photo_url
            msg = 'Profile photo updated successfully!'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': msg, 'photo_url': photo_url}), 200
            flash(msg, 'success')
        else:
            try:
                error_msg = res.json().get('error', 'Upload failed on server')
            except Exception:
                error_msg = f'Upload failed (HTTP {res.status_code})'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), res.status_code
            flash(f'Upload failed: {error_msg}', 'danger')

    except Exception as e:
        print(f"Photo upload exception: {e}")
        msg = 'An error occurred while uploading your photo. Please try again.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 500
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('user.profile'))


@user_bp.route('/documents/upload', methods=['POST'])
@user_bp.route('/upload-document', methods=['POST'])  # legacy form action
def upload_document():
    """Proxy document upload to the backend API."""
    if 'token' not in session:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        return redirect(url_for('auth.login'))

    file = request.files.get('file')
    # Form uses hidden input name="type"; backend requires doc_type
    doc_type = (request.form.get('doc_type') or request.form.get('type') or '').strip()
    employee_id = (
        request.form.get('employee_id')
        or session.get('employee_table_id')
        or ''
    )

    if not doc_type:
        msg = "'doc_type' is required. Example: pan_card, aadhar_card"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('user.profile'))

    if not file or file.filename == '':
        msg = 'No file selected'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': msg}), 400
        flash(msg, 'danger')
        return redirect(request.referrer or url_for('user.profile'))

    payload_data = {
        'doc_type': doc_type,
        'type': doc_type,  # backward compatibility for older backends
        'employee_id': employee_id,
    }
    file_bytes = file.read()
    files = {
        'file': (file.filename, file_bytes, file.mimetype),
    }

    try:
        headers = get_headers(exclude_content_type=True)
        upload_urls = [
            f"{BASE_URL}/documents/upload",
            f"{BASE_URL}/upload-document",
        ]
        res = None
        for url in upload_urls:
            res = requests.post(
                url, data=payload_data, files=files, headers=headers, timeout=30
            )
            if res.status_code != 404:
                break
        print('UPLOAD RESPONSE STATUS:', res.status_code)
        print('UPLOAD RESPONSE TEXT:', res.text)

        if res.status_code in [200, 201]:
            view_url = None
            try:
                body = res.json()
                file_path = body.get('file_path')
                rel = _normalize_upload_relative_path(file_path)
                if rel:
                    view_url = url_for('user.serve_upload', filename=rel)
            except Exception:
                pass
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'Document uploaded successfully',
                    'doc_type': doc_type,
                    'view_url': view_url,
                })
            flash('Document uploaded successfully', 'success')
            return redirect(request.referrer or url_for('user.profile'))
        else:
            error_msg = None
            try:
                error_msg = res.json().get('error')
            except Exception:
                error_msg = res.text
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg or 'Upload failed'}), res.status_code
            flash(error_msg or 'Upload failed', 'danger')
            return redirect(request.referrer or url_for('user.profile'))
    except Exception as e:
        print('EXCEPTION during document upload:', e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Server error during upload'}), 500
        flash('Server error during upload', 'danger')
        return redirect(request.referrer or url_for('user.profile'))