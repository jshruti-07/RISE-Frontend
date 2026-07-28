import requests
from flask import render_template, session, redirect, url_for, flash, request
from app.offboarding_ui import offboarding_ui_bp
from app.utils import get_headers, BASE_URL, role_required

@offboarding_ui_bp.route('/')
@role_required(['hr', 'manager', 'accounts'])
def dashboard():
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/offboarding/", headers=headers)
    if response.status_code == 200:
        data = response.json().get('data', [])
        return render_template('offboarding/dashboard.html', requests=data)
    else:
        error_msg = response.json().get('error', 'Failed to fetch offboarding requests.') if response.headers.get('content-type') == 'application/json' else f"Failed to fetch offboarding requests. Status: {response.status_code}"
        flash(error_msg, "danger")
        return redirect(url_for('dashboard.dashboard'))

@offboarding_ui_bp.route('/<int:id>')
@role_required(['hr', 'manager', 'accounts'])
def detail(id):
    headers = get_headers()
    response = requests.get(f"{BASE_URL}/offboarding/{id}", headers=headers)
    if response.status_code == 200:
        data = response.json().get('data', {})
        return render_template('offboarding/detail.html', offboarding_data=data)
    else:
        flash("Failed to fetch offboarding details.", "danger")
        return redirect(url_for('offboarding_ui.dashboard'))

@offboarding_ui_bp.route('/<int:id>/approve', methods=['POST'])
@role_required(['hr', 'manager', 'accounts'])
def approve(id):
    headers = get_headers()
    payload = request.form.to_dict()
    response = requests.post(f"{BASE_URL}/offboarding/{id}/approve", json=payload, headers=headers)
    if response.status_code == 200:
        flash("Successfully approved.", "success")
    else:
        flash(response.json().get('error', 'Failed to approve.'), "danger")
    return redirect(url_for('offboarding_ui.detail', id=id))

@offboarding_ui_bp.route('/<int:id>/reject', methods=['POST'])
@role_required(['hr', 'manager', 'accounts'])
def reject(id):
    headers = get_headers()
    payload = request.form.to_dict()
    response = requests.post(f"{BASE_URL}/offboarding/{id}/reject", json=payload, headers=headers)
    if response.status_code == 200:
        flash("Successfully rejected.", "success")
    else:
        flash(response.json().get('error', 'Failed to reject.'), "danger")
    return redirect(url_for('offboarding_ui.detail', id=id))

@offboarding_ui_bp.route('/<int:id>/checklist/<item_type>', methods=['POST'])
@role_required(['hr'])
def mark_done(id, item_type):
    headers = get_headers()
    payload = {'status': 'DONE', 'notes': request.form.get('notes', '')}
    response = requests.patch(f"{BASE_URL}/offboarding/{id}/checklist/{item_type}", json=payload, headers=headers)
    if response.status_code == 200:
        flash("Checklist item updated.", "success")
    else:
        flash(response.json().get('error', 'Failed to update item.'), "danger")
    return redirect(url_for('offboarding_ui.detail', id=id))

@offboarding_ui_bp.route('/initiate', methods=['POST'])
@role_required(['hr'])
def initiate():
    headers = get_headers()
    payload = request.form.to_dict()
    # convert employee_id to int if necessary, but backend might handle string.
    response = requests.post(f"{BASE_URL}/offboarding/", json=payload, headers=headers)
    if response.status_code in [200, 201]:
        flash("Offboarding initiated successfully.", "success")
        return redirect(url_for('offboarding_ui.dashboard'))
    else:
        flash(response.json().get('error', 'Failed to initiate offboarding.'), "danger")
        return redirect(request.referrer or url_for('employees.all_employees'))
