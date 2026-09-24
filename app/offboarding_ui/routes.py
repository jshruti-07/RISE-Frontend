import requests
from flask import render_template, session, redirect, url_for, flash, request, jsonify
from app.offboarding_ui import offboarding_ui_bp
from app.utils import get_headers, BASE_URL, role_required, normalize_role
from datetime import date

@offboarding_ui_bp.route('/')
def dashboard():
    role = normalize_role(session.get('role', 'employee'))
    headers = get_headers()

    # Regular Employees / Team Members -> My Offboarding Portal
    if role in ('employee', 'team_member'):
        try:
            resp = requests.get(f"{BASE_URL}/offboarding/my-case", headers=headers)
            data = resp.json() if resp.status_code == 200 else {}
            my_case = data.get('case')
            assigned_assets = data.get('assigned_assets', [])
            active_employees = data.get('active_employees', [])
            employee = data.get('employee', {})
        except Exception:
            my_case = None
            assigned_assets = []
            active_employees = []
            employee = {}

        return render_template(
            'offboarding/employee_portal.html', 
            my_case=my_case,
            assigned_assets=assigned_assets,
            active_employees=active_employees,
            employee=employee,
            today=date.today().isoformat()
        )

    # HR, Admin, Superadmin, Manager -> Management Dashboard
    try:
        cases_resp = requests.get(f"{BASE_URL}/offboarding/cases", headers=headers)
        cases = cases_resp.json().get('cases', []) if cases_resp.status_code == 200 else []
        
        metrics_resp = requests.get(f"{BASE_URL}/offboarding/metrics", headers=headers)
        metrics = metrics_resp.json().get('metrics', {}) if metrics_resp.status_code == 200 else {}
    except Exception as e:
        cases = []
        metrics = {}
        flash("Could not connect to backend offboarding service.", "danger")

    return render_template('offboarding/hr_dashboard.html', cases=cases, metrics=metrics)

@offboarding_ui_bp.route('/my-portal')
def employee_portal():
    headers = get_headers()
    try:
        resp = requests.get(f"{BASE_URL}/offboarding/my-case", headers=headers)
        data = resp.json() if resp.status_code == 200 else {}
        my_case = data.get('case')
        assigned_assets = data.get('assigned_assets', [])
        active_employees = data.get('active_employees', [])
        employee = data.get('employee', {})
    except Exception:
        my_case = None
        assigned_assets = []
        active_employees = []
        employee = {}

    return render_template(
        'offboarding/employee_portal.html', 
        my_case=my_case,
        assigned_assets=assigned_assets,
        active_employees=active_employees,
        employee=employee,
        today=date.today().isoformat()
    )

@offboarding_ui_bp.route('/submit-resignation', methods=['POST'])
def submit_resignation():
    headers = get_headers()

    personal_email = (request.form.get('personal_email') or '').strip()
    confirm_personal_email = (request.form.get('confirm_personal_email') or '').strip()
    if personal_email.lower() != confirm_personal_email.lower():
        flash("Personal email addresses do not match.", "danger")
        return redirect(url_for('offboarding_ui.dashboard'))

    # Check declaration checkboxes
    c1 = request.form.get('confirm_accurate')
    c2 = request.form.get('confirm_active_account')
    c3 = request.form.get('confirm_approval')
    c4 = request.form.get('confirm_property_return')
    if not (c1 and c2 and c3 and c4):
        flash("All confirmation declarations must be accepted before submitting.", "danger")
        return redirect(url_for('offboarding_ui.dashboard'))

    payload = {
        'resignation_date': request.form.get('resignation_date'),
        'proposed_last_working_day': request.form.get('proposed_last_working_day'),
        'exit_type': request.form.get('exit_type', 'Voluntary Resignation'),
        'other_exit_type': request.form.get('other_exit_type'),
        'reason': request.form.get('reason'),
        'other_reason': request.form.get('other_reason'),
        'reason_notes': request.form.get('reason_notes'),
        'handover_required': request.form.get('handover_required', 'Yes'),
        'handover_to': request.form.get('handover_to'),
        'handover_projects': request.form.get('handover_projects'),
        'handover_notes': request.form.get('handover_notes'),
        'personal_email': personal_email,
        'personal_phone': request.form.get('personal_phone'),
        'alternate_phone': request.form.get('alternate_phone'),
        'preferred_communication': request.form.get('preferred_communication', 'Personal Email'),
        'post_employment_contact_consent': request.form.get('post_employment_contact_consent', 'Yes'),
        'declarations_confirmed': True
    }

    # If resignation letter was uploaded
    doc_file = request.files.get('resignation_doc')
    if doc_file and doc_file.filename:
        try:
            upload_resp = requests.post(
                f"{BASE_URL}/documents/upload",
                files={'file': (doc_file.filename, doc_file.stream, doc_file.content_type)},
                data={'doc_type': 'other'},
                headers=headers
            )
            if upload_resp.status_code in (200, 201):
                payload['resignation_doc_path'] = upload_resp.json().get('file_path')
        except Exception:
            pass

    # If additional supporting document was uploaded
    supp_file = request.files.get('supporting_doc')
    if supp_file and supp_file.filename:
        try:
            upload_resp = requests.post(
                f"{BASE_URL}/documents/upload",
                files={'file': (supp_file.filename, supp_file.stream, supp_file.content_type)},
                data={'doc_type': 'other'},
                headers=headers
            )
            if upload_resp.status_code in (200, 201):
                payload['supporting_doc_path'] = upload_resp.json().get('file_path')
        except Exception:
            pass

    try:
        resp = requests.post(f"{BASE_URL}/offboarding/resign", json=payload, headers=headers)
        if resp.status_code in (200, 201):
            flash("Your resignation request has been submitted successfully and is awaiting manager approval.", "success")
        else:
            flash(resp.json().get('error', 'Failed to submit resignation.'), "danger")
    except Exception as e:
        flash(f"Connection error: {e}", "danger")

    return redirect(url_for('offboarding_ui.dashboard'))

@offboarding_ui_bp.route('/initiate', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def initiate():
    headers = get_headers()
    payload = request.form.to_dict()
    try:
        response = requests.post(f"{BASE_URL}/offboarding/initiate", json=payload, headers=headers)
        if response.status_code in [200, 201]:
            flash("Offboarding initiated successfully.", "success")
            offb_id = response.json().get('offboarding_id')
            if offb_id:
                return redirect(url_for('offboarding_ui.case_detail', id=offb_id))
            return redirect(url_for('offboarding_ui.dashboard'))
        else:
            err = response.json().get('error', 'Failed to initiate offboarding.') if response.headers.get('content-type') == 'application/json' else response.text
            flash(err, "danger")
    except Exception as e:
        flash(f"Server error: {e}", "danger")
    return redirect(request.referrer or url_for('offboarding_ui.dashboard'))

@offboarding_ui_bp.route('/cases/<int:id>')
def case_detail(id):
    headers = get_headers()
    try:
        resp = requests.get(f"{BASE_URL}/offboarding/cases/{id}", headers=headers)
        if resp.status_code == 200:
            case_data = resp.json().get('case', {})
            return render_template('offboarding/case_detail.html', case=case_data)
        else:
            flash("Failed to fetch offboarding case details.", "danger")
            return redirect(url_for('offboarding_ui.dashboard'))
    except Exception as e:
        flash(f"Error: {e}", "danger")
        return redirect(url_for('offboarding_ui.dashboard'))

@offboarding_ui_bp.route('/cases/<int:id>/manager-review', methods=['POST'])
@role_required(['manager', 'admin', 'hr', 'superadmin'])
def manager_review(id):
    headers = get_headers()
    payload = {
        'decision': request.form.get('decision'),
        'rejection_reason': request.form.get('rejection_reason')
    }
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/manager-review", json=payload, headers=headers)
        if resp.status_code == 200:
            flash(resp.json().get('message', 'Decision recorded.'), "success")
        else:
            flash(resp.json().get('error', 'Failed to process decision.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.case_detail', id=id))

@offboarding_ui_bp.route('/cases/<int:id>/consent', methods=['POST'])
def submit_consent(id):
    headers = get_headers()
    payload = {
        'signature_text': request.form.get('signature_text'),
        'resignation_confirmed': True,
        'last_working_day_confirmed': True,
        'asset_return_acknowledged': True,
        'confidential_info_acknowledged': True,
        'data_handling_acknowledged': True,
        'access_termination_acknowledged': True,
        'final_clearance_acknowledged': True
    }
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/consent", json=payload, headers=headers)
        if resp.status_code == 200:
            flash("Your offboarding consent has been successfully submitted.", "success")
        else:
            flash(resp.json().get('error', 'Failed to submit consent.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.dashboard'))

@offboarding_ui_bp.route('/cases/<int:id>/kt', methods=['POST'])
@role_required(['manager', 'hr', 'admin', 'superadmin'])
def update_kt(id):
    headers = get_headers()
    payload = {
        'replacement_employee_name': request.form.get('replacement_employee_name'),
        'status': request.form.get('status'),
        'pending_responsibilities': request.form.get('pending_responsibilities'),
        'documents_transferred': request.form.get('documents_transferred'),
        'remarks': request.form.get('remarks')
    }
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/knowledge-transfer", json=payload, headers=headers)
        if resp.status_code == 200:
            flash("Knowledge transfer details updated.", "success")
        else:
            flash(resp.json().get('error', 'Failed to update knowledge transfer.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.case_detail', id=id))

@offboarding_ui_bp.route('/cases/<int:id>/assets/<int:device_id>/return', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def return_asset(id, device_id):
    headers = get_headers()
    payload = {
        'return_status': request.form.get('return_status', 'Returned'),
        'condition': request.form.get('condition'),
        'remarks': request.form.get('remarks')
    }
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/assets/{device_id}/return", json=payload, headers=headers)
        if resp.status_code == 200:
            flash("Asset returned successfully.", "success")
        else:
            flash(resp.json().get('error', 'Failed to return asset.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.case_detail', id=id))

@offboarding_ui_bp.route('/cases/<int:id>/it-access/<path:system_name>', methods=['PATCH'])
@role_required(['system_admin', 'superadmin', 'admin'])
def update_it_system(id, system_name):
    headers = get_headers()
    payload = request.get_json() or {}
    try:
        resp = requests.patch(f"{BASE_URL}/offboarding/cases/{id}/it-access/{system_name}", json=payload, headers=headers)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@offboarding_ui_bp.route('/cases/<int:id>/it-deactivation', methods=['POST'])
@role_required(['system_admin', 'superadmin', 'admin'])
def it_deactivation(id):
    headers = get_headers()
    payload = {
        'checklist': {
            'corporate_account_disabled': bool(request.form.get('corporate_account_disabled')),
            'corporate_email_disabled': bool(request.form.get('corporate_email_disabled')),
            'application_access_revoked': bool(request.form.get('application_access_revoked')),
            'vpn_access_revoked': bool(request.form.get('vpn_access_revoked')),
            'github_access_revoked': bool(request.form.get('github_access_revoked')),
            'groups_removed': bool(request.form.get('groups_removed')),
            'sessions_revoked': bool(request.form.get('sessions_revoked')),
            'licenses_removed': bool(request.form.get('licenses_removed')),
        },
        'notes': request.form.get('notes')
    }
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/it-deactivation", json=payload, headers=headers)
        if resp.status_code == 200:
            flash("Corporate account disabled and system access revoked successfully.", "success")
        else:
            flash(resp.json().get('error', 'Failed to perform IT deactivation.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.case_detail', id=id))

@offboarding_ui_bp.route('/cases/<int:id>/complete', methods=['POST'])
@role_required(['hr', 'admin', 'superadmin'])
def complete_case(id):
    headers = get_headers()
    try:
        resp = requests.post(f"{BASE_URL}/offboarding/cases/{id}/hr-clearance", json={}, headers=headers)
        if resp.status_code == 200:
            flash("Offboarding completed successfully. Employee status is now OFFBOARDED.", "success")
        else:
            flash(resp.json().get('error', 'Failed to complete offboarding.'), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for('offboarding_ui.case_detail', id=id))
