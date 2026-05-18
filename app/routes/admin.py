import requests
import os
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, Response
from app.utils import BASE_URL, get_headers, role_required

admin_bp = Blueprint('admin', __name__)

# --- HELPDESK ---
@admin_bp.route('/helpdesk')
@role_required(['admin', 'employee', 'hr', 'manager'])
def helpdesk():
    return render_template('helpdesk.html', BASE_URL=BASE_URL)

@admin_bp.route('/api/helpdesk/', methods=['GET', 'POST'])
def api_helpdesk_list():
    if request.method == 'POST':
        res = requests.post(f"{BASE_URL}/helpdesk/", json=request.get_json(), headers=get_headers())
    else:
        res = requests.get(f"{BASE_URL}/helpdesk/", params=request.args.to_dict(), headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/helpdesk/<int:ticket_id>', methods=['GET'])
def api_helpdesk_detail(ticket_id):
    res = requests.get(f"{BASE_URL}/helpdesk/{ticket_id}", headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/helpdesk/<int:ticket_id>/status', methods=['PATCH'])
@role_required(['admin', 'hr'])
def api_helpdesk_status(ticket_id):
    res = requests.patch(f"{BASE_URL}/helpdesk/{ticket_id}/status", json=request.get_json(), headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/helpdesk/<int:ticket_id>/assign', methods=['PATCH'])
@role_required(['admin', 'hr'])
def api_helpdesk_assign(ticket_id):
    res = requests.patch(f"{BASE_URL}/helpdesk/{ticket_id}/assign", json=request.get_json(), headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/reimbursement')
@role_required(['admin', 'employee', 'hr', 'manager'])
def reimbursement():
    return render_template('reimbursement.html', BASE_URL=BASE_URL)

@admin_bp.route('/api/reimbursements', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursements():
    if request.method == 'POST':
        # Handle multipart form data for file upload
        if request.content_type and 'multipart' in request.content_type:
            form_data = request.form.to_dict()
            files = {}
            if 'receipt' in request.files:
                receipt_file = request.files['receipt']
                if receipt_file.filename:
                    files['receipt'] = (receipt_file.filename, receipt_file.read(), receipt_file.content_type)
            
            res = requests.post(f"{BASE_URL}/reimbursements/", data=form_data, files=files, headers=get_headers(exclude_content_type=True))
        else:
            res = requests.post(f"{BASE_URL}/reimbursements/", json=request.get_json(), headers=get_headers())
    else:
        res = requests.get(f"{BASE_URL}/reimbursements/", params=request.args.to_dict(), headers=get_headers())
    
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/reimbursements/<int:record_id>', methods=['GET', 'DELETE'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursement_detail(record_id):
    if request.method == 'DELETE':
        res = requests.delete(f"{BASE_URL}/reimbursements/{record_id}", headers=get_headers())
    else:
        res = requests.get(f"{BASE_URL}/reimbursements/{record_id}", headers=get_headers())
        if res.status_code == 200:
            data = res.json()
            # Try to fetch history too
            h_res = requests.get(f"{BASE_URL}/reimbursements/{record_id}/history", headers=get_headers())
            if h_res.status_code == 200:
                data['history'] = h_res.json().get('history', [])
            return jsonify(data)
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/reimbursements/<int:record_id>/approve', methods=['PATCH'])
@role_required(['admin', 'hr', 'manager'])
def api_approve_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/approve", json=request.get_json() or {}, headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/reimbursements/<int:record_id>/reject', methods=['PATCH'])
@role_required(['admin', 'hr', 'manager'])
def api_reject_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/reject", json=request.get_json() or {}, headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/reimbursements/<int:record_id>/pay', methods=['PATCH'])
@role_required(['admin'])
def api_pay_reimbursement(record_id):
    res = requests.patch(f"{BASE_URL}/reimbursements/{record_id}/pay", json=request.get_json() or {}, headers=get_headers())
    return jsonify(res.json()), res.status_code

@admin_bp.route('/api/reimbursements/<int:record_id>/receipt', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_reimbursement_receipt(record_id):
    res = requests.get(f"{BASE_URL}/reimbursements/{record_id}/receipt", headers=get_headers(), stream=True)
    from flask import Response
    return Response(res.content, status=res.status_code, headers=dict(res.headers))

# --- ASSETS ---
@admin_bp.route('/assets')
@role_required(['admin', 'hr'])
def assets():
    return render_template('assets.html', BASE_URL=BASE_URL)

# --- POLICIES ---
@admin_bp.route('/policies')
@role_required(['admin', 'employee', 'hr', 'manager'])
def policies():
    res = requests.get(f"{BASE_URL}/reports/policies", headers=get_headers())
    data = res.json() if res.status_code == 200 else {}
    policies_list = data.get("policies", [])
    categories = sorted(list(set(p.get('category', 'General') for p in policies_list)))
    return render_template("policies.html", policies=policies_list, categories=categories, BASE_URL=BASE_URL)

@admin_bp.route('/api/policies/<int:policy_id>', methods=['PUT'])
@role_required(['admin', 'hr'])
def api_update_policy(policy_id):
    try:
        data = request.get_json()
        res = requests.put(
            f"{BASE_URL}/reports/policies/{policy_id}",
            json=data,
            headers=get_headers()
        )
        if res.status_code == 200:
            return jsonify(res.json()), 200
        else:
            try:
                return jsonify(res.json()), res.status_code
            except:
                return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        print(f"ERROR in policy update API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/bank-details/<int:detail_id>/<action>', methods=['PATCH'])
@role_required(['admin', 'hr'])
def verify_bank_admin(detail_id, action):
    if action not in ['approve', 'reject']:
        return jsonify({"success": False, "error": "Invalid action"}), 400
    try:
        res = requests.patch(f"{BASE_URL}/bank-details/{detail_id}/{action}", 
                           json=request.get_json() or {}, headers=get_headers(), timeout=5)
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets', methods=['GET', 'POST'])
@role_required(['admin', 'hr'])
def api_assets():
    if request.method == 'GET':
        try:
            res = requests.get(f"{BASE_URL}/devices", headers=get_headers(), timeout=10)
            if res.status_code == 200:
                data = res.json()
                assets = data if isinstance(data, list) else (data.get("assets") or data.get("devices") or [])
                return jsonify({"success": True, "assets": assets})
            return jsonify({"success": False, "error": res.text}), res.status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    else: # POST
        try:
            payload = request.form.to_dict() if request.files else (request.get_json(force=True) or {})
            
            # Match the backend data structure
            create_data = {
                "device_name": payload.get("device_name"),
                "device_type": payload.get("device_type"),
                "serial_number": payload.get("serial_number"),
                "brand": payload.get("device_name"), 
                "model": payload.get("device_type"),
                "status": "Available",
                "processor": payload.get("processor"),
                "ram": payload.get("ram"),
                "storage": payload.get("storage"),
                "purchase_date": payload.get("purchase_date"),
                "warranty_expiry": payload.get("warranty_expiry"),
                "notes": payload.get("notes")
            }
            
            # Step 1: Create Device (JSON)
            res = requests.post(f"{BASE_URL}/devices", json=create_data, headers=get_headers(), timeout=10)
            
            if res.status_code not in [200, 201]:
                return jsonify({"success": False, "error": f"Creation failed: {res.text}"}), res.status_code
            
            data = res.json()
            device_id = data.get("device_id") or data.get("id")
            
            # Step 2: Upload Image if present
            if request.files and device_id:
                for key in request.files:
                    for file in request.files.getlist(key):
                        # Reset file pointer after reading in potential previous loops
                        file.seek(0)
                        f_data = {'image': (file.filename, file.read(), file.content_type)}
                        requests.post(f"{BASE_URL}/devices/{device_id}/upload-image", 
                                      files=f_data, 
                                      headers=get_headers(exclude_content_type=True),
                                      timeout=15)
                        # The current backend seems to support one primary image via this endpoint
                        break 
            
            return jsonify({
                "success": True, 
                "asset": {
                    "id": device_id, 
                    "device_name": create_data["device_name"],
                    "serial_number": create_data["serial_number"]
                }
            })
            
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>', methods=['GET', 'DELETE'])
@role_required(['admin', 'hr'])
def api_asset_detail(id):
    if request.method == 'GET':
        try:
            res = requests.get(f"{BASE_URL}/devices/{id}", headers=get_headers(), timeout=10)
            if res.status_code == 200:
                return jsonify({"success": True, "asset": res.json()})
            return jsonify({"success": False, "error": res.text}), res.status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    else: # DELETE
        try:
            res = requests.delete(f"{BASE_URL}/devices/{id}", headers=get_headers(), timeout=10)
            if res.status_code == 200:
                return jsonify({"success": True})
            return jsonify({"success": False, "error": res.text}), res.status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>/history')
@role_required(['admin', 'hr'])
def api_asset_history(id):
    try:
        res = requests.get(f"{BASE_URL}/devices/{id}/history", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "history": res.json()})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>/assign', methods=['POST'])
@role_required(['admin', 'hr'])
def api_assign_asset(id):
    try:
        data = request.get_json(force=True)
        headers = get_headers(exclude_content_type=True)
        headers["Content-Type"] = "application/json"
        res = requests.post(f"{BASE_URL}/devices/{id}/assign", json=data, headers=headers, timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>/acceptance-status')
@role_required(['admin', 'hr'])
def api_asset_acceptance(id):
    try:
        res = requests.get(f"{BASE_URL}/devices/{id}/acceptance-status", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "status": res.json()})
        return jsonify({"success": False, "error": res.text}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
