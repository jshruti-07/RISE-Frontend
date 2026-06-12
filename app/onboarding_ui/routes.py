from flask import render_template, redirect, url_for
from app.utils import role_required
from app.onboarding_ui import onboarding_bp


@onboarding_bp.route('/')
@role_required(['hr', 'admin'])
def dashboard():
    from app.utils import BASE_URL
    from flask import session
    return render_template('onboarding/dashboard.html', BASE_URL=BASE_URL, token=session.get('token'))


@onboarding_bp.route('/joinee-dashboard')
def joinee_dashboard():
    from flask import session
    from app.utils import BASE_URL
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    role = str(session.get('role', '')).lower().strip()
    if role != 'onboarding_candidate':
        return redirect(url_for('dashboard.dashboard'))
    return render_template(
        'joinee/dashboard.html',
        BASE_URL=BASE_URL,
        token=session.get('token'),
        joinee_name=session.get('full_name') or session.get('display_name') or session.get('employee_name', 'New Joinee')
    )