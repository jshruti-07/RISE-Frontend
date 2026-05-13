import os
import requests
import inspect
from functools import wraps
from flask import session, redirect, url_for, flash, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://13.205.90.13:5001")

def get_headers(exclude_content_type=False):
    token = session.get('token')
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    if not exclude_content_type:
        headers["Content-Type"] = "application/json"
    
    return headers

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'role' not in session:
                return redirect(url_for('auth.login')) # Note: changed to auth.login
            if session.get('role') not in allowed_roles:
                flash("Access denied", "danger")
                return redirect(url_for('dashboard.dashboard')) # Note: changed to dashboard.dashboard
            
            sig = inspect.signature(f)
            if 'current_user' in sig.parameters:
                current_user = {
                    'user_id': session.get('user_id'),
                    'username': session.get('username'),
                    'role': session.get('role'),
                    'employee_name': session.get('employee_name')
                }
                return f(current_user, *args, **kwargs)
            else:
                return f(*args, **kwargs)
        return wrapper
    return decorator

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'token' not in session:
            return redirect(url_for('auth.login'))
        
        sig = inspect.signature(f)
        if 'current_user' in sig.parameters:
            current_user = {
                'user_id': session.get('user_id'),
                'username': session.get('username'),
                'role': session.get('role'),
                'employee_name': session.get('employee_name')
            }
            return f(current_user, *args, **kwargs)
        return f(*args, **kwargs)
    return decorated

def fetch_leave_balance_helper(employee_name):
    if not employee_name:
        return None
    
    headers = get_headers()
    names_to_try = [employee_name]
    if len(employee_name) > 2 and employee_name[1] == '_':
        names_to_try.append(employee_name[2:].strip())

    for name in names_to_try:
        try:
            res = requests.get(f"{BASE_URL}/leave-balance/{name}", headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if not data or not (data.get("balances") or data.get("summary")):
                    continue
                
                # Standardize summary keys for template consistency
                bs = data.get("summary", {})
                std_summary = {
                    "total_leaves": bs.get("total_leaves") or bs.get("total_quota") or 30,
                    "used_leaves": bs.get("used_leaves") or bs.get("total_used") or 0,
                    "remaining_leaves": bs.get("remaining_leaves") or bs.get("total_remaining") or 0,
                    "casual_used": bs.get("casual_used") or bs.get("casual_leaves_used") or 0,
                    "casual_total": bs.get("casual_total") or bs.get("casual_quota") or 12,
                    "sick_used": bs.get("sick_used") or bs.get("sick_leaves_used") or 0,
                    "sick_total": bs.get("sick_total") or bs.get("sick_quota") or 10,
                    "earned_used": bs.get("earned_used") or bs.get("earned_leaves_used") or 0,
                    "earned_total": bs.get("earned_total") or bs.get("earned_quota") or 8
                }
                
                # Try to fill missing from balances array
                balances = data.get("balances", [])
                for b in balances:
                    ltype = (b.get("leave_type") or "").lower()
                    used = b.get("used_leaves") or b.get("used") or 0
                    total = b.get("total_leaves") or b.get("total") or (used + (b.get("remaining") or 0))
                    
                    if "casual" in ltype:
                        std_summary["casual_used"] = used
                        std_summary["casual_total"] = total
                    elif "sick" in ltype:
                        std_summary["sick_used"] = used
                        std_summary["sick_total"] = total
                    elif "earned" in ltype:
                        std_summary["earned_used"] = used
                        std_summary["earned_total"] = total
                
                # Final calculation for remaining if needed
                std_summary["remaining_leaves"] = std_summary["total_leaves"] - std_summary["used_leaves"]
                
                return {"success": True, "summary": std_summary, "balances": balances}
        except Exception as e:
            print(f"Error fetching balance for {name}: {e}")
            
    return None
