"""Shared request helpers: session auth + decorators."""
from functools import wraps
from flask import session, jsonify, request
from models import User


def current_user():
    uid = session.get("uid")
    return User.query.get(uid) if uid else None


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "")


def login_required(fn):
    @wraps(fn)
    def wrap(*a, **k):
        if not current_user():
            return jsonify(error="Authentication required"), 401
        return fn(*a, **k)
    return wrap


def admin_required(fn):
    @wraps(fn)
    def wrap(*a, **k):
        u = current_user()
        if not u:
            return jsonify(error="Authentication required"), 401
        if u.role != "admin":
            return jsonify(error="Admin privileges required"), 403
        return fn(*a, **k)
    return wrap
