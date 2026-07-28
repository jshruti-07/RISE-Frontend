from flask import Blueprint

offboarding_ui_bp = Blueprint('offboarding_ui', __name__)

from app.offboarding_ui import routes
