import os
import shutil
from flask import Blueprint, jsonify, session, g, current_app
from .. import db, limiter
from ..models import User, Setting
from ..utils.security import (APIError, body, s, EMAIL, login_required, current_user, csrf_token, check_password_strength)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _login(u):
    session.clear()
    session["uid"] = u.id
    session.permanent = True
    csrf_token()


@bp.get("/csrf")
def csrf():
    return {"csrf": csrf_token()}


@bp.post("/register")
@limiter.limit("10/hour")
def register():
    d = body()
    name, email, pw = s(d.get("name"), 120), s(d.get("email"), 255).lower(), d.get("password")
    if not name or not EMAIL.match(email):
        raise APIError("Enter a valid name and email.")
    check_password_strength(pw)
    if User.query.filter_by(email=email).first():
        raise APIError("An account with this email already exists.", 409, "exists")
    u = User(name=name, email=email)
    u.set_password(pw)
    db.session.add(u)
    db.session.flush()
    db.session.add(Setting(user_id=u.id, data={}))
    db.session.commit()
    _login(u)
    return {"user": u.to_dict(), "csrf": session["csrf"]}, 201


@bp.post("/login")
@limiter.limit("10/minute")
def login():
    d = body()
    u = User.query.filter_by(email=s(d.get("email"), 255).lower()).first()
    if not u or not u.check_password(d.get("password") or ""):
        raise APIError("Incorrect email or password.", 401, "bad_credentials")
    _login(u)
    return {"user": u.to_dict(), "csrf": session["csrf"]}


@bp.post("/logout")
def logout():
    session.clear()
    return {"ok": True}


@bp.get("/me")
def me():
    u = current_user()
    return {"user": u.to_dict() if u else None, "csrf": csrf_token()}


@bp.patch("/profile")
@login_required
def profile():
    d = body()
    u = g.user
    if "name" in d:
        u.name = s(d["name"], 120) or u.name
    if "email" in d:
        e = s(d["email"], 255).lower()
        if not EMAIL.match(e):
            raise APIError("Invalid email.")
        if e != u.email and User.query.filter_by(email=e).first():
            raise APIError("Email already in use.", 409)
        u.email = e
    db.session.commit()
    return {"user": u.to_dict()}


@bp.post("/password")
@login_required
def password():
    d = body()
    if not g.user.check_password(d.get("current") or ""):
        raise APIError("Current password is incorrect.", 403)
    check_password_strength(d.get("new"))
    g.user.set_password(d["new"])
    db.session.commit()
    return {"ok": True}


@bp.delete("/account")
@login_required
def delete_account():
    d = body()
    if not g.user.check_password(d.get("password") or ""):
        raise APIError("Password is incorrect.", 403)
    shutil.rmtree(os.path.join(current_app.config["UPLOAD_FOLDER"], str(g.user.id)), ignore_errors=True)
    db.session.delete(g.user)
    db.session.commit()
    session.clear()
    return {"ok": True}
