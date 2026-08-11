"""Authentication: register, verify, login, logout, account management."""
import re
import secrets
from flask import Blueprint, request, jsonify, session, redirect
from extensions import db
from models import User, log
from helpers import current_user, client_ip, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _strong(pw):
    return (len(pw) >= 8 and re.search(r"[A-Z]", pw) and re.search(r"[a-z]", pw)
            and re.search(r"\d", pw) and re.search(r"[^A-Za-z0-9]", pw))


# FR1 — Validate & submit registration
@auth_bp.post("/register")
def register():
    d = request.get_json(force=True, silent=True) or {}
    name = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    confirm = d.get("confirm") or ""
    slmc = (d.get("slmc") or "").strip()

    if not all([name, email, pw, confirm]):
        return jsonify(error="All fields are required."), 400
    if not EMAIL_RE.match(email):
        return jsonify(error="Invalid email format."), 400
    if pw != confirm:
        return jsonify(error="Passwords do not match."), 400
    if not _strong(pw):
        return jsonify(error="Password must be 8+ chars with upper, lower, digit and symbol."), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="Email is already registered."), 409

    u = User(name=name, email=email, slmc_no=slmc,
             specialization=d.get("specialization", "Dermatologist"),
             role="doctor", is_active=True, is_verified=False,
             verify_token=secrets.token_urlsafe(24))
    u.set_password(pw)
    db.session.add(u)
    db.session.commit()
    log(u.id, "REGISTER", f"New account {email}", client_ip())
    # No mail server in the demo -> return the verification link so the flow is testable.
    return jsonify(message="Account created. Verify your email to activate.",
                   verify_link=f"/verify/{u.verify_token}"), 201


# FR2 — Verify email & activate account
@auth_bp.get("/verify/<token>")
def verify_api(token):
    u = User.query.filter_by(verify_token=token).first()
    if not u:
        return jsonify(error="Invalid or expired verification link."), 400
    u.is_verified = True
    u.verify_token = None
    db.session.commit()
    log(u.id, "VERIFY", "Email verified", client_ip())
    return jsonify(message="Email verified. You can now sign in.")


# FR3 — Authenticate (sign in)
@auth_bp.post("/login")
def login():
    d = request.get_json(force=True, silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    u = User.query.filter_by(email=email).first()
    if not u or not u.check_password(pw):
        return jsonify(error="Invalid email or password."), 401
    if not u.is_active:
        return jsonify(error="Account is deactivated. Contact an administrator."), 403
    if not u.is_verified:
        return jsonify(error="Please verify your email before signing in.",
                       verify_link=f"/verify/{u.verify_token}" if u.verify_token else None), 403
    session["uid"] = u.id
    log(u.id, "LOGIN", "Signed in", client_ip())
    return jsonify(user=u.to_dict())


# FR4 — Log out
@auth_bp.post("/logout")
def logout():
    u = current_user()
    if u:
        log(u.id, "LOGOUT", "Signed out", client_ip())
    session.clear()
    return jsonify(message="Logged out.")


@auth_bp.get("/me")
def me():
    u = current_user()
    return jsonify(user=u.to_dict() if u else None)


# FR5 — Manage account
@auth_bp.put("/account")
@login_required
def account():
    u = current_user()
    d = request.get_json(force=True, silent=True) or {}
    if d.get("name"):
        u.name = d["name"].strip()
    if d.get("specialization"):
        u.specialization = d["specialization"]
    new_pw = d.get("new_password")
    if new_pw:
        if not u.check_password(d.get("current_password", "")):
            return jsonify(error="Current password is incorrect."), 400
        if not _strong(new_pw):
            return jsonify(error="New password does not meet complexity rules."), 400
        u.set_password(new_pw)
    db.session.commit()
    log(u.id, "ACCOUNT", "Updated account", client_ip())
    return jsonify(user=u.to_dict())
