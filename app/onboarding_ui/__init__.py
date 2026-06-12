from flask import Blueprint

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

from app.onboarding_ui import routes