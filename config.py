import os
from dotenv import load_dotenv

load_dotenv()
BASE = os.path.abspath(os.path.dirname(__file__))


def _db():
    u = os.getenv("DATABASE_URL", "sqlite:///study_mentor.db")
    if u.startswith("postgres://"):
        u = u.replace("postgres://", "postgresql://", 1)
    return u


class Config:
    PROD = os.getenv("FLASK_ENV", "development") == "production"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _db()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = os.path.abspath(os.getenv("UPLOAD_FOLDER", os.path.join(BASE, "uploads")))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 25))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024 * 4  # whole request (multi-file)
    MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", 300))
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", 60))
    MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", 18000))  # ~4.5k tokens of study material
    MAX_HISTORY_MESSAGES = 8
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PROD
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    CSRF_ENABLED = True
    PROCESS_SYNC = False
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    AI_LIMIT = os.getenv("AI_LIMIT", "30/minute")
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "")  # same-origin by default
