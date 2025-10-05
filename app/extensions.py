from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_babel import Babel


"""
Application extensions.

db: Single SQLAlchemy instance with multiple binds.
- Default bind (None) points to the active TENANT database; switched per-request
  in the app.before_request hook.
- Named bind 'master' points to the MASTER database (companies registry).
"""

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
babel = Babel()
