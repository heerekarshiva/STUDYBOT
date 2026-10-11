import functools
import re
import secrets
from datetime import date
from flask import session, jsonify, request, g
from .. import db
from ..models import User


class APIError(Exception):
    def __init__(self, msg, status=400, code="bad_request"):
        super().__init__(msg)
        self.msg, self.status, self.code = msg, status, code


def current_user():
    uid = session.get("uid")
    return db.session.get(User, uid) if uid else None


def login_required(f):
    @functools.wraps(f)
    def w(*a, **k):
        u = current_user()
        if not u:
            raise APIError("Please sign in.", 401, "unauthorized")
        g.user = u
        return f(*a, **k)
    return w


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise APIError("Expected a JSON object body.")
    return d


def owned(model, oid, uid):
    o = db.session.get(model, oid) if isinstance(oid, int) or str(oid).isdigit() else None
    if not o or o.user_id != uid:
        raise APIError("Not found.", 404, "not_found")
    return o


def s(v, maxlen=200, default=""):
    return (v if isinstance(v, str) else default).strip()[:maxlen]


def i(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def parse_date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        raise APIError("Invalid date (use YYYY-MM-DD).")


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_password_strength(p):
    if not isinstance(p, str) or len(p) < 8:
        raise APIError("Password must be at least 8 characters.")
