from flask import render_template, Blueprint, redirect, url_for, request, flash
from . import auth_bp

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # مبدأي: لا تصادف المصادقة الحقيقية هنا — استخدمها كمثال
        username = request.form.get("username")
        flash(f"تم تسجيل الدخول كمثال: {username}")
        return redirect(url_for("index"))
    return render_template("login.html")
