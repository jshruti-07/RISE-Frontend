import os
import requests
import inspect
from functools import wraps
from flask import session, redirect, url_for, flash, request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:5001")

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

            # Role Bypass for Super Admin
            if user_role == 'superadmin':
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
                    "total_leaves": bs.get("total_leaves") or bs.get("total_quota") or 18,
                    "used_leaves": bs.get("used_leaves") or bs.get("total_used") or 0,
                    "remaining_leaves": bs.get("remaining_leaves") or bs.get("total_remaining") or 0,
                    "planned_used": bs.get("planned_used") or bs.get("planned_leaves_used") or 0,
                    "planned_total": bs.get("planned_total") or bs.get("planned_quota") or 12,
                    "unplanned_used": bs.get("unplanned_used") or bs.get("unplanned_leaves_used") or 0,
                    "unplanned_total": bs.get("unplanned_total") or bs.get("unplanned_quota") or 4,
                    "optional_used": bs.get("optional_used") or bs.get("optional_leaves_used") or 0,
                    "optional_total": bs.get("optional_total") or bs.get("optional_quota") or 2,
                    # Backward compatibility aliases
                    "planned_leaves": 0,
                    "unplanned_leaves": 0,
                    "optional_leaves": 0
                }
                
                # Try to fill missing from balances array
                for b in balances:
                    if not isinstance(b, dict): continue
                    ltype = (b.get("leave_type") or "").lower()
                    used = b.get("used_leaves") or b.get("used") or 0
                    total = b.get("total_leaves") or b.get("total") or (used + (b.get("remaining") or 0))
                    rem = b.get("remaining_leaves") or b.get("remaining") or (total - used)
                    
                    if "planned" in ltype and "unplanned" not in ltype:
                        std_summary["planned_used"] = used
                        std_summary["planned_total"] = total
                        std_summary["planned_leaves"] = rem
                    elif "unplanned" in ltype:
                        std_summary["unplanned_used"] = used
                        std_summary["unplanned_total"] = total
                        std_summary["unplanned_leaves"] = rem
                    elif "optional" in ltype:
                        std_summary["optional_used"] = used
                        std_summary["optional_total"] = total
                        std_summary["optional_leaves"] = rem
                    elif "casual" in ltype:
                        std_summary["planned_used"] = used
                        std_summary["planned_total"] = total
                        std_summary["planned_leaves"] = rem
                    elif "sick" in ltype:
                        std_summary["unplanned_used"] = used
                        std_summary["unplanned_total"] = total
                        std_summary["unplanned_leaves"] = rem
                    elif "earned" in ltype:
                        std_summary["optional_used"] = used
                        std_summary["optional_total"] = total
                        std_summary["optional_leaves"] = rem
                
                # Final calculation for remaining if needed
                std_summary["remaining_leaves"] = std_summary["total_leaves"] - std_summary["used_leaves"]
                if not std_summary["planned_leaves"]:
                    std_summary["planned_leaves"] = max(0, std_summary["planned_total"] - std_summary["planned_used"])
                if not std_summary["unplanned_leaves"]:
                    std_summary["unplanned_leaves"] = max(0, std_summary["unplanned_total"] - std_summary["unplanned_used"])
                if not std_summary["optional_leaves"]:
                    std_summary["optional_leaves"] = max(0, std_summary["optional_total"] - std_summary["optional_used"])
                
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
            used_stats = {"planned": 0, "unplanned": 0, "optional": 0, "total": 0}
            quotas = {"planned": 12, "unplanned": 4, "optional": 2, "total": 18}
            
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
                        if "planned" in ltype and "unplanned" not in ltype:
                            used_stats["planned"] += days
                        elif "unplanned" in ltype or "sick" in ltype:
                            used_stats["unplanned"] += days
                        elif "optional" in ltype or "earned" in ltype:
                            used_stats["optional"] += days
                        elif "casual" in ltype:
                            used_stats["planned"] += days
                        
                        used_stats["total"] += days
                    except Exception as e:
                        print(f"Error parsing leave dates: {e}")
                        continue

            remaining_planned = max(0, quotas["planned"] - used_stats["planned"])
            remaining_unplanned = max(0, quotas["unplanned"] - used_stats["unplanned"])
            remaining_optional = max(0, quotas["optional"] - used_stats["optional"])
            total_remaining = remaining_planned + remaining_unplanned + remaining_optional

            std_summary = {
                "total_leaves": quotas["total"],
                "used_leaves": used_stats["total"],
                "remaining_leaves": total_remaining,
                "planned_used": used_stats["planned"],
                "planned_total": quotas["planned"],
                "unplanned_used": used_stats["unplanned"],
                "unplanned_total": quotas["unplanned"],
                "optional_used": used_stats["optional"],
                "optional_total": quotas["optional"],
                "planned_leaves": remaining_planned,
                "unplanned_leaves": remaining_unplanned,
                "optional_leaves": remaining_optional
            }

            balances = [
                {"leave_type": "Planned", "used_leaves": used_stats["planned"], "total_leaves": quotas["planned"], "remaining_leaves": remaining_planned},
                {"leave_type": "Unplanned", "used_leaves": used_stats["unplanned"], "total_leaves": quotas["unplanned"], "remaining_leaves": remaining_unplanned},
                {"leave_type": "Optional", "used_leaves": used_stats["optional"], "total_leaves": quotas["optional"], "remaining_leaves": remaining_optional}
            ]

            return {"success": True, "summary": std_summary, "balances": balances}
    except Exception as ex:
        print(f"Error in dynamic fallback leave calculation: {ex}")

    return None
