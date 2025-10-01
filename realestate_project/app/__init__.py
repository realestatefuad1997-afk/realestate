from flask import Flask, render_template
from .extensions import db
from .auth import auth_bp
from .properties import properties_bp
from .admin import admin_bp
from config import Config

def create_app(config_class=Config):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # Extensions
    db.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(properties_bp, url_prefix="/properties")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Simple route
    @app.route("/")
    def index():
        return render_template("index.html")

    # Create database if not exists
    with app.app_context():
        db.create_all()

    return app
