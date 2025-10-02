import os
from uuid import uuid4
from flask import render_template, request, redirect, url_for, current_app, flash
from . import properties_bp
from ..models import Property, PropertyImage
from ..extensions import db

@properties_bp.route("/")
def list_properties():
    props = Property.query.all()
    return render_template("dashboard.html", properties=props)


def _allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_IMAGE_EXTENSIONS", set())


@properties_bp.route("/new", methods=["GET", "POST"])
def create_property():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()

        if not title:
            flash("العنوان مطلوب", "warning")
            return redirect(url_for("properties.create_property"))

        try:
            price = float(price_raw) if price_raw else None
        except ValueError:
            flash("قيمة السعر غير صحيحة", "warning")
            return redirect(url_for("properties.create_property"))

        new_prop = Property(title=title, description=description, price=price)
        db.session.add(new_prop)
        db.session.flush()  # للحصول على ID قبل الحفظ النهائي

        files = request.files.getlist("images")
        upload_dir = current_app.config.get("UPLOAD_FOLDER")
        os.makedirs(upload_dir, exist_ok=True)
        saved_any = False
        for f in files:
            if not f or f.filename == "":
                continue
            if not _allowed_file(f.filename):
                flash(f"صيغة غير مدعومة: {f.filename}", "warning")
                continue
            ext = f.filename.rsplit(".", 1)[1].lower()
            unique_name = f"{uuid4().hex}.{ext}"
            dest_path = os.path.join(upload_dir, unique_name)
            f.save(dest_path)
            db.session.add(PropertyImage(property_id=new_prop.id, filename=unique_name))
            saved_any = True

        db.session.commit()
        flash("تم إضافة العقار بنجاح" + (" مع صور" if saved_any else ""), "success")
        return redirect(url_for("properties.list_properties"))

    return render_template("properties/new_property.html")


@properties_bp.route("/<int:property_id>")
def property_detail(property_id: int):
    prop = Property.query.get_or_404(property_id)
    share_url = url_for(
        "properties.property_detail", property_id=property_id, _external=True
    )
    return render_template(
        "properties/property_detail.html", property=prop, share_url=share_url
    )
