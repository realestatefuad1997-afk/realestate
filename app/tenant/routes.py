from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from flask_babel import gettext as _
from ..models import Contract, Payment


tenant_bp = Blueprint("tenant", __name__)


def tenant_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_tenant:
            return abort(403)
        return func(*args, **kwargs)

    return wrapper


@tenant_bp.route("/")
@login_required
@tenant_required
def dashboard():
    contracts = Contract.query.filter_by(tenant_id=current_user.id).all()
    payments = (
        Payment.query.join(Contract, Payment.contract_id == Contract.id)
        .filter(Contract.tenant_id == current_user.id)
        .all()
    )
    return render_template("tenant/dashboard.html", contracts=contracts, payments=payments)

