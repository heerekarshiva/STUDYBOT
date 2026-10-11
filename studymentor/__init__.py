import logging
import os
from flask import Flask, jsonify, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
limiter = Limiter(key_func=get_remote_address, default_limits=["600/hour"])


def create_app(overrides=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object("config.Config")
    if overrides:
        app.config.update(overrides)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.init_app(app)
    limiter.init_app(app)

    from .utils.security import APIError, csrf_token
    from .routes import auth, documents, study, mentor, quizzes, flashcards, planner, settings
    for m in (auth, documents, study, mentor, quizzes, flashcards, planner, settings):
        app.register_blueprint(m.bp)

    @app.before_request
    def csrf_guard():
        if (app.config["CSRF_ENABLED"] and request.path.startswith("/api/") and request.method in
                ("POST", "PUT", "PATCH", "DELETE") and request.path not in ("/api/auth/login", "/api/auth/register")):
            if request.headers.get("X-CSRF-Token") != session.get("csrf"):
                return jsonify(error="Security token missing or expired. Refresh the page.", code="csrf"), 403

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "SAMEORIGIN"
        r.headers["Referrer-Policy"] = "same-origin"
        r.headers["Permissions-Policy"] = "microphone=(self)"
        if app.config["CORS_ORIGIN"] and request.path.startswith("/api/"):
            r.headers["Access-Control-Allow-Origin"] = app.config["CORS_ORIGIN"]
            r.headers["Access-Control-Allow-Credentials"] = "true"
            r.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
        return r

    @app.errorhandler(APIError)
    def api_err(e):
        return jsonify(error=e.msg, code=e.code), e.status

    from .services.groq_service import AIError

    @app.errorhandler(AIError)
    def ai_err(e):
        return jsonify(error=e.msg, code=e.code), e.status

    @app.errorhandler(413)
    def too_big(e):
        return jsonify(error="Upload too large.", code="too_large"), 413

    @app.errorhandler(429)
    def limited(e):
        return jsonify(error="Too many requests. Please slow down and try again shortly.", code="rate_limit"), 429

    @app.errorhandler(404)
    def nf(e):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found.", code="not_found"), 404
        return render_template("index.html"), 404

    @app.errorhandler(Exception)
    def boom(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return jsonify(error=e.description, code="http"), e.code
        app.logger.exception("Unhandled error")
        return jsonify(error="Something went wrong on the server.", code="server_error"), 500

    @app.get("/")
    def landing():
        return render_template("index.html")

    @app.get("/app")
    def spa():
        return render_template("app.html")

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    with app.app_context():
        db.create_all()
    return app
