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

def fetch_user_permissions(force_refresh=False):
    """
    Fetch the latest dynamic permissions and feature actions from the backend API.
    Caches the results in session['permissions'] and session['feature_actions'].
    """
    if not session.get('token'):
        return {"permissions": {}, "feature_actions": {}}
        
    if not force_refresh and session.get('permissions') is not None and session.get('feature_actions') is not None:
        return {
            "permissions": session.get('permissions', {}),
            "feature_actions": session.get('feature_actions', {})
        }
        
    try:
        res = requests.get(f"{BASE_URL}/auth/permissions", headers=get_headers(), timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("success"):
                session['permissions'] = data.get('permissions', {})
                session['feature_actions'] = data.get('feature_actions', {})
                return data
    except Exception as e:
        print(f"Error fetching user permissions from backend: {e}")
        
    return {
        "permissions": session.get('permissions', {}),
        "feature_actions": session.get('feature_actions', {})
    }

FEATURE_ALIASES = {
    'employees': 'employees',
    'team_members': 'team_members',
    'employee_team_management': 'employee_team_management',
    'departments': 'departments',
    'designations': 'designations',
    'devices': 'devices',
    'devices_assets': 'devices_assets',
    'assets': 'devices',
    'software': 'software',
    'inventory': 'inventory',
    'inventory_stock': 'inventory_stock',
    'leave': 'leave',
    'leaves': 'leaves',
    'leave_management': 'leave_management',
    'timesheets': 'projects',
    'expenses': 'expenses',
    'reimbursement': 'reimbursements',
    'reimbursements': 'reimbursements',
    'user_accounts': 'user_accounts',
    'auth': 'auth',
    'bank_details': 'bank_details',
    'bank': 'bank',
    'documents': 'documents',
    'helpdesk': 'helpdesk',
    'policies': 'policies',
    'holidays': 'holidays',
    'announcements': 'announcements',
    'projects': 'projects',
    'project_records': 'project_records',
    'project_assignments': 'project_assignments',
    'reports': 'reports',
}

def has_permission(feature_or_key, action=None) -> bool:
    """
    Evaluates whether the current logged-in user has permission for a feature/action or direct permission key.
    Always uses the dynamic permissions configured by Super Admin.
    """
    if not session.get('token'):
        return False
        
    # If permissions are not in session, fetch them
    if session.get('permissions') is None or session.get('feature_actions') is None:
        fetch_user_permissions()
        
    perms = session.get('permissions') or {}
    feature_actions = session.get('feature_actions') or {}
    
    fk = str(feature_or_key).lower().strip()
    act = str(action).lower().strip() if action else None

    # Check direct permission key (e.g. 'employees.update' or 'devices.view_all')
    if fk in perms:
        return bool(perms[fk])

    # Special handling for devices/assets: strictly requires devices.view_all for view
    if fk in ['devices', 'devices_assets', 'assets'] and (act is None or act == 'view'):
        return bool(perms.get('devices.view_all', False))

    if fk == 'software' and (act is None or act == 'view'):
        return bool(perms.get('devices.catalog_view', False))

    if fk in ['inventory', 'inventory_stock'] and (act is None or act == 'view'):
        return bool(perms.get('devices.inventory_dashboard', False))

    canonical_feature = FEATURE_ALIASES.get(fk, fk)
    act_key = act if act else "view"

    if canonical_feature in feature_actions:
        return bool(feature_actions[canonical_feature].get(act_key, False))
        
    if fk in feature_actions:
        return bool(feature_actions[fk].get(act_key, False))

    # Cross-check for compound aliases
    if canonical_feature in ['employees', 'employee_team_management', 'team_members']:
        for alias in ['employees', 'employee_team_management', 'team_members']:
            if alias in feature_actions and feature_actions[alias].get(act_key):
                return True

    if canonical_feature in ['leave', 'leaves', 'leave_management']:
        for alias in ['leave', 'leaves', 'leave_management']:
            if alias in feature_actions and feature_actions[alias].get(act_key):
                return True

    if canonical_feature in ['reimbursements', 'expenses']:
        for alias in ['reimbursements', 'expenses']:
            if alias in feature_actions and feature_actions[alias].get(act_key):
                return True

    if canonical_feature in ['bank', 'bank_details']:
        for alias in ['bank', 'bank_details']:
            if alias in feature_actions and feature_actions[alias].get(act_key):
                return True

    # Fail secure
    return False

def normalize_role(role):
    if not role:
        return 'employee'
    r = str(role).lower().strip().replace(' ', '').replace('_', '')
    if r in ['superadmin', 'super_admin', 'super admin']:
        return 'superadmin'
    if r in ['teammember', 'team_member']:
        return 'employee'
    if r in ['onboardingcandidate', 'onboarding_candidate']:
        return 'onboarding_candidate'
    return str(role).lower().strip()

def can(feature_or_key, action=None) -> bool:
    """Convenience alias for template evaluation: can('employee_team_management', 'manage')"""
    # Superadmin always has access to all UI features
    if normalize_role(session.get('role', '')) == 'superadmin':
        return True
    return has_permission(feature_or_key, action)

def permission_required(feature_or_key, action=None):
    """
    Route decorator: strictly requires dynamic permission granted in DB.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get('token'):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Not authenticated"}), 401
                return redirect(url_for('auth.login'))

            user_role = normalize_role(session.get('role', ''))
            # Superadmin bypass
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

            if not has_permission(feature_or_key, action):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Access denied"}), 403
                
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

def role_required(allowed_roles, permission_key=None, action=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Redirect to login if no session
            if not session.get('token'):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Not authenticated"}), 401
                return redirect(url_for('auth.login'))

            user_role = normalize_role(session.get('role', ''))
            allowed_roles_norm = [normalize_role(r) for r in allowed_roles]

            # Superadmin bypass
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

            # If dynamic permission is specified, check permission
            if permission_key and not has_permission(permission_key, action):
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Access denied"}), 403
                return redirect(url_for('dashboard.dashboard'))

            if user_role not in allowed_roles_norm:
                # Return JSON for API/AJAX calls instead of HTML redirect
                if request.path.startswith('/api/') or request.is_json:
                    from flask import jsonify
                    return jsonify({"success": False, "error": "Access denied"}), 403
                # Onboarding candidates always go to their own dashboard
                if user_role == 'onboarding_candidate':
                    return redirect(url_for('onboarding.joinee_dashboard'))
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
