from flask import render_template
from . import admin_bp

@admin_bp.route("/")
def admin_index():
    return render_template("dashboard.html")
