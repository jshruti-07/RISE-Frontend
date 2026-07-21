import os
import requests
import inspect
from functools import wraps
from flask import session, redirect, url_for, flash, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://192.168.1.6:5001")

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
            # Redirect to login if no session
            if not session.get('token'):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Not authenticated"}), 401
                return redirect(url_for('auth.login'))

            user_role = str(session.get('role', '')).lower().strip()
            allowed_roles_lower = [r.lower().strip() for r in allowed_roles]

            if user_role not in allowed_roles_lower:
                # Return JSON for API/AJAX calls instead of HTML redirect
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Access denied"}), 403
                # Onboarding candidates always go to their own dashboard
                if user_role == 'onboarding_candidate':
                    return redirect(url_for('onboarding.joinee_dashboard'))
                flash("Access denied", "danger")
                return redirect(url_for('dashboard.dashboard'))

            sig = inspect.signature(f)
            if 'current_user' in sig.parameters:
                current_user = {
                    'user_id': session.get('user_id'),
                    'username': session.get('username'),
                    'role': user_role,
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
        
        user_role = str(session.get('role', '')).lower().strip()
        sig = inspect.signature(f)
        if 'current_user' in sig.parameters:
            current_user = {
                'user_id': session.get('user_id'),
                'username': session.get('username'),
                'role': user_role,
                'employee_name': session.get('employee_name')
            }
            return f(current_user, *args, **kwargs)
        return f(*args, **kwargs)
    return decorated

def fetch_leave_balance_helper(employee_name):
    if not employee_name:
        return None

    from app.api_helpers import names_match

    headers = get_headers()

    balance_urls = [
        f"{BASE_URL}/leaves/balance/{employee_name}",
        f"{BASE_URL}/leave-balance/{employee_name}",
    ]

    for url in balance_urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if not data:
                    continue
                
                # Handle dictionary response
                if isinstance(data, dict):
                    bs = data.get("summary", {})
                    balances = data.get("balances", [])
                # Handle list response (if API returns balances array directly)
                elif isinstance(data, list):
                    bs = {}
                    balances = data
                else:
                    continue
                
                # Standardize summary keys for template consistency
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
                for b in balances:
                    if not isinstance(b, dict): continue
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
            print(f"Error fetching balance for {employee_name}: {e}")
    # === Fallback: Calculate from approved leaves dynamically ===
    try:
        from datetime import datetime
        leaves_res = requests.get(f"{BASE_URL}/leaves", headers=headers, timeout=10)
        if leaves_res.status_code == 200:
            from app.api_helpers import extract_list
            leaves_data = extract_list(leaves_res.json(), 'leaves', 'data')
            used_stats = {"casual": 0, "sick": 0, "earned": 0, "total": 0}
            quotas = {"casual": 12, "sick": 10, "earned": 8, "total": 30}
            
            for leave in leaves_data:
                if not isinstance(leave, dict): continue
                emp_name = leave.get("employee_name") or leave.get("name") or leave.get("emp_name")
                if names_match(emp_name, employee_name) and str(leave.get("status", "")).lower() == "approved":
                    try:
                        s_str = leave.get("start_date", "")[:10]
                        e_str = leave.get("end_date", "")[:10]
                        s_date = datetime.strptime(s_str, "%Y-%m-%d")
                        e_date = datetime.strptime(e_str, "%Y-%m-%d")
                        days = (e_date - s_date).days + 1
                        
                        ltype = (leave.get("leave_type") or "").lower()
                        if "casual" in ltype:
                            used_stats["casual"] += days
                        elif "sick" in ltype:
                            used_stats["sick"] += days
                        elif "earned" in ltype:
                            used_stats["earned"] += days
                        
                        used_stats["total"] += days
                    except Exception as e:
                        print(f"Error parsing leave dates: {e}")
                        continue

            remaining_casual = max(0, quotas["casual"] - used_stats["casual"])
            remaining_sick = max(0, quotas["sick"] - used_stats["sick"])
            remaining_earned = max(0, quotas["earned"] - used_stats["earned"])
            total_remaining = remaining_casual + remaining_sick + remaining_earned

            std_summary = {
                "total_leaves": quotas["total"],
                "used_leaves": used_stats["total"],
                "remaining_leaves": total_remaining,
                "casual_used": used_stats["casual"],
                "casual_total": quotas["casual"],
                "sick_used": used_stats["sick"],
                "sick_total": quotas["sick"],
                "earned_used": used_stats["earned"],
                "earned_total": quotas["earned"]
            }

            balances = [
                {"leave_type": "Casual", "used_leaves": used_stats["casual"], "total_leaves": quotas["casual"], "remaining_leaves": remaining_casual},
                {"leave_type": "Sick", "used_leaves": used_stats["sick"], "total_leaves": quotas["sick"], "remaining_leaves": remaining_sick},
                {"leave_type": "Earned", "used_leaves": used_stats["earned"], "total_leaves": quotas["earned"], "remaining_leaves": remaining_earned}
            ]

            return {"success": True, "summary": std_summary, "balances": balances}
    except Exception as ex:
        print(f"Error in dynamic fallback leave calculation: {ex}")

    return None
