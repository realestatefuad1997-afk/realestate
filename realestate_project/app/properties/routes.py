from flask import render_template
from . import properties_bp
from ..models import Property

@properties_bp.route("/")
def list_properties():
    props = Property.query.all()
    return render_template("dashboard.html", properties=props)
