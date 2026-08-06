import os
import json
import requests
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session, flash, Response
from app.utils import BASE_URL, get_headers, role_required, token_required, fetch_leave_balance_helper

main_bp = Blueprint('main', __name__)

# --- NOTIFICATIONS ---
@main_bp.route('/notifications')
@role_required(['admin', 'employee', 'hr', 'manager'])
def notifications():
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    return render_template('notifications.html')

@main_bp.route('/api/notifications', methods=['GET'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_notifications():
    try:
        res = requests.get(f"{BASE_URL}/notifications/", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/notifications/<int:notification_id>/read', methods=['PUT'])
@role_required(['admin', 'employee', 'hr', 'manager'])
def api_notification_read(notification_id):
    try:
        res = requests.put(f"{BASE_URL}/notifications/{notification_id}/read", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- RENTAL INVOICES PROXIES ---
@main_bp.route('/api/rentals/invoices', methods=['GET'])
@role_required(['admin', 'hr'])
def api_list_invoices():
    try:
        res = requests.get(f"{BASE_URL}/rentals/invoices", params=request.args.to_dict(), headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/invoices/<int:invoice_id>/pay', methods=['POST'])
@role_required(['admin', 'hr'])
def api_pay_invoice(invoice_id):
    try:
        res = requests.post(f"{BASE_URL}/rentals/invoices/{invoice_id}/pay", json=request.get_json(), headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/invoices/dashboard-widgets', methods=['GET'])
@role_required(['admin', 'hr'])
def api_invoice_dashboard_widgets():
    try:
        res = requests.get(f"{BASE_URL}/rentals/invoices/dashboard-widgets", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/invoices/history/<device_id>', methods=['GET'])
@role_required(['admin', 'hr'])
def api_invoice_history(device_id):
    try:
        res = requests.get(f"{BASE_URL}/rentals/invoices/history/{device_id}", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/invoices/trigger-check', methods=['POST'])
@role_required(['admin', 'hr'])
def api_trigger_invoice_check():
    try:
        res = requests.post(f"{BASE_URL}/rentals/invoices/trigger-check", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>', methods=['GET'])
@role_required(['admin', 'hr'])
def api_get_vendor_invoice(vendor_name):
    try:
        res = requests.get(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/asset-payment', methods=['PUT'])
@role_required(['admin', 'hr'])
def api_update_vendor_asset_payment(vendor_name):
    try:
        res = requests.put(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/asset-payment", json=request.get_json(), headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/pay-all', methods=['POST'])
@role_required(['admin', 'hr'])
def api_pay_all_vendor_assets(vendor_name):
    try:
        res = requests.post(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/pay-all", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/upload', methods=['POST'])
@role_required(['admin', 'hr'])
def api_upload_vendor_invoice(vendor_name):
    try:
        files = {}
        if 'file' in request.files:
            f = request.files['file']
            files['file'] = (f.filename, f.read(), f.content_type)
        elif 'vendor_invoice' in request.files:
            f = request.files['vendor_invoice']
            files['file'] = (f.filename, f.read(), f.content_type)

        headers = get_headers()
        headers.pop('Content-Type', None)
        headers.pop('content-type', None)

        res = requests.post(
            f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/upload",
            files=files,
            headers=headers
        )
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/file', methods=['GET'])
@role_required(['admin', 'hr'])
def api_get_vendor_invoice_file(vendor_name):
    try:
        from flask import Response
        res = requests.get(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/file", headers=get_headers(), stream=True)
        return Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/octet-stream'))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/download', methods=['GET'])
@role_required(['admin', 'hr'])
def api_download_vendor_invoice_file(vendor_name):
    try:
        from flask import Response
        res = requests.get(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/download", headers=get_headers(), stream=True)
        resp = Response(res.content, status=res.status_code, content_type=res.headers.get('content-type', 'application/octet-stream'))
        if 'content-disposition' in res.headers:
            resp.headers['Content-Disposition'] = res.headers['content-disposition']
        return resp
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@main_bp.route('/api/rentals/vendor-invoice/<path:vendor_name>/upload', methods=['DELETE'])
@role_required(['admin', 'hr'])
def api_delete_vendor_invoice_file(vendor_name):
    try:
        res = requests.delete(f"{BASE_URL}/rentals/vendor-invoice/{vendor_name}/upload", headers=get_headers())
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# End of main routes
