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

    @app.before_request
    def restrict_superadmin_navigation():
        from flask import session, request, redirect, url_for
        if session.get('role') != 'superadmin':
            return  # not superadmin, nothing to do here

        allowed_endpoints = {
            'superadmin.access_control',
            'superadmin.api_get_permissions',
            'superadmin.api_toggle_permission',
            'superadmin.api_reset_defaults',
            'superadmin.api_get_audit_log',
            'auth.logout',
            'auth.login',
            'auth.change_password',
            'static',
        }
        if request.endpoint not in allowed_endpoints:
            return redirect(url_for('superadmin.access_control'))

    @app.context_processor
    def inject_user():
        from flask import session
        return dict(
            current_user=session.get('employee_name'),
            role=session.get('role'),
            sidebar_photo_url=session.get('photo_url'),
            labels=UI_LABELS,
            config=UI_CONFIG
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
