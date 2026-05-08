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

# --- REIMBURSEMENTS ---
@admin_bp.route('/reimbursement')
@role_required(['admin', 'employee', 'hr', 'manager'])
def reimbursement():
    return render_template('reimbursement.html', BASE_URL=BASE_URL)

# --- ASSETS ---
@admin_bp.route('/assets')
@role_required(['admin', 'hr'])
def assets():
    return render_template('assets.html')

# --- POLICIES ---
@admin_bp.route('/policies')
@role_required(['admin', 'employee', 'hr', 'manager'])
def policies():
    res = requests.get(f"{BASE_URL}/reports/policies", headers=get_headers())
    data = res.json() if res.status_code == 200 else {}
    policies_list = data.get("policies", [])
    categories = sorted(list(set(p.get('category', 'General') for p in policies_list)))
    return render_template("policies.html", policies=policies_list, categories=categories, BASE_URL=BASE_URL)
