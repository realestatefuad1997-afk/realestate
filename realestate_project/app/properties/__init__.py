from flask import Blueprint

properties_bp = Blueprint("properties", __name__, template_folder="templates")

from . import routes  # noqa
