from flask import render_template
from app.utils import role_required
from app.onboarding_ui import onboarding_bp


@onboarding_bp.route('/')
@role_required(['hr'])
def dashboard():
    from app.utils import BASE_URL
    from flask import session
    return render_template('onboarding/dashboard.html', BASE_URL=BASE_URL, token=session.get('token'))