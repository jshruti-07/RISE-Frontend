from flask import render_template
from app.utils import role_required
from app.onboarding_ui import onboarding_bp


@onboarding_bp.route('/')
@role_required(['hr'])
def dashboard():
    return render_template('onboarding/dashboard.html')