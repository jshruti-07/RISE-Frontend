import requests
import os
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify, Response
from app.utils import BASE_URL, get_headers, role_required
from app.api_helpers import extract_list, with_list_key

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
        try:
            body = with_list_key(res.json(), 'tickets', 'data')
            return jsonify(body), res.status_code
        except Exception:
            pass
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
        try:
            body = with_list_key(res.json(), 'reimbursements', 'data')
            return jsonify(body), res.status_code
        except Exception:
            pass
    
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
    policies_list = extract_list(data, 'policies', 'data')
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
                assets = data if isinstance(data, list) else extract_list(data, 'assets', 'devices', 'data')
                return jsonify({"success": True, "assets": assets})
            return jsonify({"success": False, "error": res.text}), res.status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    else: # POST
        try:
            # Always extract text fields into a clean dict regardless of content type
            # The backend /devices API expects JSON — never send raw form-data to it
            if request.content_type and 'multipart' in request.content_type:
                payload = request.form.to_dict()
            else:
                payload = request.get_json(force=True) or {}

            # Build clean JSON payload — skip None/empty values
            create_data = {k: v for k, v in {
                "device_name": payload.get("device_name"),
                "device_type": payload.get("device_type"),
                "serial_number": payload.get("serial_number"),
                "asset_id": payload.get("asset_id"),
                "brand": payload.get("brand") or payload.get("device_name"),
                "model": payload.get("model") or payload.get("device_type"),
                "status": "Available",
                "processor": payload.get("processor"),
                "ram": payload.get("ram"),
                "storage": payload.get("storage"),
                "purchase_date": payload.get("purchase_date"),
                "warranty_expiry": payload.get("warranty_expiry"),
                "condition_notes": payload.get("notes")
            }.items() if v}

            # Step 1: Create Device — always send as JSON
            res = requests.post(f"{BASE_URL}/devices", json=create_data, headers=get_headers(), timeout=10)

            if res.status_code not in [200, 201]:
                try:
                    err_detail = res.json()
                except Exception:
                    err_detail = res.text
                return jsonify({"success": False, "error": f"Creation failed: {err_detail}"}), res.status_code

            data = res.json()
            device_id = data.get("device_id") or data.get("id")

            # Step 2: Upload images if present (separate request per file)
            if device_id and request.files:
                img_headers = get_headers(exclude_content_type=True)
                for key in request.files:
                    for file in request.files.getlist(key):
                        if not file or not file.filename:
                            continue
                        file.seek(0)
                        f_data = {'image': (file.filename, file.read(), file.content_type)}
                        requests.post(
                            f"{BASE_URL}/devices/{device_id}/upload-image",
                            files=f_data,
                            headers=img_headers,
                            timeout=15
                        )
                        break  # Backend supports one primary image

            return jsonify({
                "success": True,
                "asset": {
                    "id": device_id,
                    "device_name": create_data.get("device_name"),
                    "serial_number": create_data.get("serial_number")
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
        data = request.get_json(force=True) or {}
        # Only pass non-empty values to the backend
        assign_payload = {k: v for k, v in data.items() if v not in [None, '', []]}
        res = requests.post(f"{BASE_URL}/devices/{id}/assign", json=assign_payload, headers=get_headers(), timeout=10)
        if res.status_code in [200, 201]:
            return jsonify({"success": True})
        try:
            err_detail = res.json()
        except Exception:
            err_detail = res.text
        return jsonify({"success": False, "error": err_detail}), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>/return', methods=['POST'])
@role_required(['admin', 'hr'])
def api_return_asset(id):
    try:
        res = requests.post(f"{BASE_URL}/devices/{id}/return", headers=get_headers(), timeout=10)
        if res.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Asset returned successfully", "asset_status": "AVAILABLE"})
        try:
            err_detail = res.json()
        except Exception:
            err_detail = res.text
        return jsonify({"success": False, "error": err_detail}), res.status_code
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

# --- AGREEMENT PAGE ---
@admin_bp.route('/assets/agreement/<id>')
@role_required(['admin', 'hr', 'manager', 'employee', 'team_member'])
def asset_agreement_page(id):
    """Render the device usage agreement signing page."""
    from app.ui_constants import UI_LABELS
    return render_template('agreement.html', asset_id=id, labels=UI_LABELS, BASE_URL=BASE_URL)

@admin_bp.route('/api/assets/<id>/agreement')
@role_required(['admin', 'hr', 'manager', 'employee', 'team_member'])
def api_asset_agreement(id):
    """Fetch agreement/assignment details for a device."""
    try:
        res = requests.get(f"{BASE_URL}/devices/{id}", headers=get_headers(), timeout=10)
        if res.status_code != 200:
            return jsonify({"success": False, "error": res.text}), res.status_code
        data = res.json()
        # Flatten: backend may nest inside .device
        device = data.get('device') or data
        agreement = {
            "assignment_id": device.get('assignment_id') or device.get('id'),
            "assigned_date": device.get('assigned_date') or device.get('created_at', ''),
            "employee_name": device.get('employee_name') or device.get('assigned_to', ''),
            "employee_id": device.get('employee_id', ''),
            "device": {
                "brand": device.get('brand') or device.get('device_name', ''),
                "model": device.get('model') or device.get('device_type', ''),
                "serial_number": device.get('serial_number', ''),
            }
        }
        return jsonify({"success": True, "agreement": agreement})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@admin_bp.route('/api/assets/<id>/accept', methods=['POST'])
@role_required(['admin', 'hr', 'manager', 'employee', 'team_member'])
def api_accept_agreement(id):
    """Submit signed agreement."""
    try:
        files = {}
        if 'signature' in request.files:
            sig = request.files['signature']
            if sig.filename:
                files['signature'] = (sig.filename, sig.read(), sig.content_type)

        form_data = request.form.to_dict()
        
        if files:
            res = requests.post(
                f"{BASE_URL}/devices/{id}/accept",
                data=form_data,
                files=files,
                headers=get_headers(exclude_content_type=True),
                timeout=15
            )
        else:
            res = requests.post(
                f"{BASE_URL}/devices/{id}/accept",
                data=form_data,
                headers=get_headers(exclude_content_type=True),
                timeout=15
            )
            
        try:
            body = res.json()
        except Exception:
            body = {"success": res.status_code in [200, 201]}
        return jsonify(body), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- ANNOUNCEMENTS ---


@admin_bp.route('/api/announcements', methods=['GET', 'POST'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_announcements():
    if request.method == 'POST':
        if str(session.get('role', '')).lower().strip() != 'hr':
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        print("--- DEBUG ANNOUNCEMENTS PROXY ---")
        print("CONTENT TYPE:", request.content_type)
        print("FORM DATA:", request.form.to_dict())
        print("FILES:", request.files)
        
        if request.content_type and 'multipart' in request.content_type:
            form_data = request.form.to_dict()
            files = {}
            if 'attachment' in request.files:
                attachment_file = request.files['attachment']
                if attachment_file.filename:
                    files['attachment'] = (attachment_file.filename, attachment_file.read(), attachment_file.content_type)
            
            if files:
                print("SENDING MULTIPART TO BACKEND. FILES:", list(files.keys()))
                res = requests.post(f"{BASE_URL}/announcements/", data=form_data, files=files, headers=get_headers(exclude_content_type=True))
            else:
                print("SENDING JSON FALLBACK TO BACKEND:", form_data)
                res = requests.post(f"{BASE_URL}/announcements/", json=form_data, headers=get_headers())
        else:
            print("SENDING JSON TO BACKEND:", request.get_json())
            res = requests.post(f"{BASE_URL}/announcements/", json=request.get_json(), headers=get_headers())
            
        print("BACKEND RESPONSE STATUS:", res.status_code)
        print("BACKEND RESPONSE BODY:", res.content)
        print("---------------------------------")
    else:
        res = requests.get(f"{BASE_URL}/announcements/", params=request.args.to_dict(), headers=get_headers())
    
    try:
        return jsonify(res.json()), res.status_code
    except:
        return Response(res.content, status=res.status_code, headers=dict(res.headers))

@admin_bp.route('/api/announcements/dashboard', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_announcements_dashboard():
    res = requests.get(f"{BASE_URL}/announcements/dashboard", headers=get_headers())
    try:
        return jsonify(res.json()), res.status_code
    except:
        return Response(res.content, status=res.status_code, headers=dict(res.headers))

@admin_bp.route('/api/announcements/<int:announcement_id>', methods=['GET', 'PUT', 'DELETE'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_announcement_detail(announcement_id):
    if request.method == 'PUT':
        if str(session.get('role', '')).lower().strip() != 'hr':
            return jsonify({"success": False, "error": "Access denied"}), 403
        
        print("--- DEBUG ANNOUNCEMENT DETAIL PUT PROXY ---")
        print("CONTENT TYPE:", request.content_type)
        print("FORM DATA:", request.form.to_dict())
        print("FILES:", request.files)
        
        if request.content_type and 'multipart' in request.content_type:
            form_data = request.form.to_dict()
            files = {}
            if 'attachment' in request.files:
                attachment_file = request.files['attachment']
                if attachment_file.filename:
                    files['attachment'] = (attachment_file.filename, attachment_file.read(), attachment_file.content_type)
            
            if files:
                print("SENDING MULTIPART PUT TO BACKEND. FILES:", list(files.keys()))
                res = requests.put(f"{BASE_URL}/announcements/{announcement_id}", data=form_data, files=files, headers=get_headers(exclude_content_type=True))
            else:
                print("SENDING JSON PUT FALLBACK TO BACKEND:", form_data)
                res = requests.put(f"{BASE_URL}/announcements/{announcement_id}", json=form_data, headers=get_headers())
        else:
            print("SENDING JSON PUT TO BACKEND:", request.get_json())
            res = requests.put(f"{BASE_URL}/announcements/{announcement_id}", json=request.get_json(), headers=get_headers())
            
        print("BACKEND PUT RESPONSE STATUS:", res.status_code)
        print("BACKEND PUT RESPONSE BODY:", res.content)
        print("--------------------------------------------")
    elif request.method == 'DELETE':
        if str(session.get('role', '')).lower().strip() != 'hr':
            return jsonify({"success": False, "error": "Access denied"}), 403
        res = requests.delete(f"{BASE_URL}/announcements/{announcement_id}", headers=get_headers())
    else:
        res = requests.get(f"{BASE_URL}/announcements/{announcement_id}", headers=get_headers())
        
    try:
        return jsonify(res.json()), res.status_code
    except:
        return Response(res.content, status=res.status_code, headers=dict(res.headers))

@admin_bp.route('/api/announcements/<int:announcement_id>/attachment', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_announcement_attachment(announcement_id):
    res = requests.get(f"{BASE_URL}/announcements/{announcement_id}/attachment", headers=get_headers(), stream=True)
    return Response(res.content, status=res.status_code, headers=dict(res.headers))

