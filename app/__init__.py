import os
from app.ui_constants import UI_LABELS, UI_CONFIG

from flask import Flask
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../static')
    
    app.secret_key = os.getenv("SECRET_KEY", "mysecretkey123")
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')

    # Import blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.employees import employees_bp
    from app.routes.projects import projects_bp
    from app.routes.work_management import work_bp
    from app.routes.admin import admin_bp
    from app.routes.user import user_bp
    from app.routes.main import main_bp
    from app.onboarding_ui import onboarding_bp
    from app.offboarding_ui import offboarding_ui_bp
    from app.routes.superadmin import superadmin_bp

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(work_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(offboarding_ui_bp, url_prefix='/offboarding')

    @app.before_request
    def ensure_permissions():
        from flask import session, request
        if request.path.startswith('/static/'):
            return
        if session.get('token'):
            from app.utils import fetch_user_permissions
            fetch_user_permissions(force_refresh=True)

    @app.context_processor
    def inject_user():
        from flask import session
        from app.utils import can, has_permission
        return dict(
            current_user=session.get('employee_name'),
            role=session.get('role'),
            sidebar_photo_url=session.get('photo_url'),
            labels=UI_LABELS,
            config=UI_CONFIG,
            BASE_URL=os.getenv("BACKEND_URL", "http://127.0.0.1:5001"),
            can=can,
            has_permission=has_permission,
            user_permissions=session.get('permissions', {}),
            feature_actions=session.get('feature_actions', {}),
        )

    @app.template_filter('clean_name')
    def clean_name_filter(name):
        from app.api_helpers import strip_role_prefix
        return strip_role_prefix(name) or name

    @app.template_filter('names_match')
    def names_match_filter(name_a, name_b):
        from app.api_helpers import names_match
        return names_match(name_a, name_b)

    return app
