import io
import pytest
from studymentor import create_app, db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "UPLOAD_FOLDER": str(tmp_path),
                      "CSRF_ENABLED": False, "PROCESS_SYNC": True, "RATELIMIT_ENABLED": False, "GROQ_API_KEY": "test",
                      "SQLALCHEMY_ENGINE_OPTIONS": {}})
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def register(c, email="a@x.com"):
    r = c.post("/api/auth/register", json={"name": "A", "email": email, "password": "password123"})
    assert r.status_code == 201
    return r


def make_pdf(text="Newton's second law states F = ma. Force equals mass times acceleration. " * 10):
    import fitz
    d = fitz.open()
    p = d.new_page()
    p.insert_textbox(fitz.Rect(40, 40, 550, 800), text)
    return d.tobytes()


def upload(c, data=None, name="physics.pdf"):
    return c.post("/api/documents/upload", data={"files": (io.BytesIO(data or make_pdf()), name), "subject": "Physics"},
                  content_type="multipart/form-data")
