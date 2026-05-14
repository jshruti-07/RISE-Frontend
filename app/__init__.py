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

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(work_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(main_bp)

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

    return app
