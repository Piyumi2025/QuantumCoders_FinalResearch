"""Admin console API (FR6): user management, audit log, system stats."""
from flask import Blueprint, request, jsonify
from extensions import db
from models import User, Assessment, Patient, AuditLog, log
from helpers import current_user, client_ip, admin_required

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").lower()
    rows = User.query.order_by(User.id.asc()).all()
    if q:
        rows = [u for u in rows if q in u.name.lower() or q in u.email.lower()]
    return jsonify(users=[u.to_dict() for u in rows])


@admin_bp.post("/users/<int:uid>/<action>")
@admin_required
def user_action(uid, action):
    u = User.query.get_or_404(uid)
    me = current_user()
    if action == "verify":
        u.is_verified = True; u.verify_token = None
    elif action == "activate":
        u.is_active = True
    elif action == "deactivate":
        u.is_active = False
    else:
        return jsonify(error="Unknown action."), 400
    db.session.commit()
    log(me.id, "USER_" + action.upper(), f"{action} {u.email}", client_ip())
    return jsonify(user=u.to_dict())


@admin_bp.delete("/users/<int:uid>")
@admin_required
def delete_user(uid):
    u = User.query.get_or_404(uid)
    me = current_user()
    if u.id == me.id:
        return jsonify(error="You cannot delete your own account."), 400
    email = u.email
    db.session.delete(u)
    db.session.commit()
    log(me.id, "USER_DELETE", f"Deleted {email}", client_ip())
    return jsonify(message="User deleted.")


@admin_bp.get("/audit")
@admin_required
def audit():
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(100).all()
    return jsonify(audit=[r.to_dict() for r in rows])


@admin_bp.get("/stats")
@admin_required
def stats():
    users = User.query.all()
    return jsonify(stats={
        "total_users": len(users),
        "active": sum(1 for u in users if u.is_active and u.is_verified),
        "pending": sum(1 for u in users if not u.is_verified),
        "deactivated": sum(1 for u in users if not u.is_active),
        "assessments": Assessment.query.count(),
        "patients": Patient.query.count(),
        "emergency": Assessment.query.filter_by(urgency="Emergency").count(),
        "reports": Assessment.query.count(),
    })
