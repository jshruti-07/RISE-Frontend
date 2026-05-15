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

# End of main routes
