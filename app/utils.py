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
    
    try:
        res = requests.get(f"{BASE_URL}/leave-balance/{employee_name}", headers=get_headers(), timeout=10)
        if res.status_code == 200:
            return res.json()
        
        if len(employee_name) > 2:
            clean_name = employee_name[2:].strip()
            res2 = requests.get(f"{BASE_URL}/leave-balance/{clean_name}", headers=get_headers(), timeout=10)
            if res2.status_code == 200:
                return res2.json()
    except Exception as e:
        print(f"Error fetching leave balance for {employee_name}: {e}")
    return None
