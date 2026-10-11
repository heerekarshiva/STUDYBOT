import io
from unittest.mock import patch
from studymentor.services.groq_service import AIError
from studymentor.services import quiz_service as qs
from conftest import register, upload, make_pdf


def test_auth_flow(client):
    register(client)
    assert client.get("/api/auth/me").json["user"]["email"] == "a@x.com"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json["user"] is None
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"}).status_code == 200
    assert client.post("/api/auth/register", json={"name": "b", "email": "a@x.com", "password": "password123"}).status_code == 409


def test_requires_login(client):
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/dashboard").status_code == 401


def test_upload_extract_and_validation(client):
    register(client)
    r = upload(client)
    d = r.json["documents"][0]
    assert d["status"] == "ready" and d["pages"] == 1
    full = client.get(f"/api/documents/{d['id']}?text=1").json["document"]
    assert "Newton" in full["chunks"][0]["text"]
    assert client.post("/api/documents/upload", data={"files": (io.BytesIO(b"MZ evil"), "x.pdf")}, content_type="multipart/form-data").status_code == 400
    assert client.post("/api/documents/upload", data={"files": (io.BytesIO(b"hi"), "x.exe")}, content_type="multipart/form-data").status_code == 400


def test_ocr_unavailable_scanned_pdf_fails_gracefully(client):
    import fitz
    register(client)
    doc = fitz.open(); doc.new_page()
    r = upload(client, doc.tobytes(), "blank.pdf")
    d = r.json["documents"][0]
    assert d["status"] == "failed" and d["error"]


def test_isolation_and_delete(app, client):
    register(client)
    did = upload(client).json["documents"][0]["id"]
    c2 = app.test_client()
    register(c2, "b@x.com")
    assert c2.get(f"/api/documents/{did}").status_code == 404
    assert c2.delete(f"/api/documents/{did}").status_code == 404
    assert client.delete(f"/api/documents/{did}").status_code == 200
    assert client.get("/api/documents").json["documents"] == []


def test_notes_and_groq_errors(client):
    register(client)
    did = upload(client).json["documents"][0]["id"]
    with patch("studymentor.services.groq_service.chat", return_value="# Notes\n## Force\nF=ma (physics.pdf, p.1)"):
        r = client.post("/api/study/notes", json={"doc_ids": [did], "topic": "force", "kind": "revision"})
        assert r.status_code == 200 and "F=ma" in r.json["note"]["content"]
    with patch("studymentor.services.groq_service.chat", side_effect=AIError("Groq rate limit", 429, "ai_rate_limit")):
        r = client.post("/api/study/notes", json={"doc_ids": [did], "kind": "revision"})
        assert r.status_code == 429 and "rate limit" in r.json["error"].lower()
    assert client.post("/api/study/notes", json={"doc_ids": [], "kind": "revision"}).status_code == 400
    assert len(client.get("/api/study/notes").json["notes"]) == 1


def test_mentor_continuity(client):
    register(client)
    did = upload(client).json["documents"][0]["id"]
    seen = []

    def fake(messages, **kw):
        seen.append(messages)
        return "Answer"
    with patch("studymentor.services.groq_service.chat", side_effect=fake):
        r1 = client.post("/api/mentor/chat", json={"message": "What is Newton's second law?", "doc_ids": [did]}).json
        cid = r1["conversation"]["id"]
        assert r1["message"]["sources"][0]["page"] == 1
        client.post("/api/mentor/chat", json={"message": "and an example?", "conversation_id": cid})
    assert any("Newton" in m["content"] for m in seen[1])  # history carried over
    assert len(client.get(f"/api/mentor/conversations/{cid}").json["messages"]) == 4
    assert client.delete(f"/api/mentor/conversations/{cid}").status_code == 200


QJSON = {"questions": [
    {"type": "mcq", "question": "What does F = ma relate?", "options": ["a", "b", "c", "d"], "answer": 1, "explanation": "e", "topic": "Dynamics", "page": 1},
    {"type": "fill", "question": "Force equals mass times ____.", "answer": "Acceleration", "accepted": ["accel"], "explanation": "e", "topic": "Dynamics"},
    {"type": "numeric", "question": "Mass 2 kg, a = 3 m/s2. Force?", "answer": 6, "tolerance": 0.01, "explanation": "e", "topic": "Dynamics"},
    {"type": "mcq", "question": "Broken question", "options": ["a"], "answer": 9, "topic": "x"}]}


def test_quiz_generate_validate_and_evaluate(client):
    register(client)
    did = upload(client).json["documents"][0]["id"]
    with patch("studymentor.services.groq_service.chat", return_value=__import__("json").dumps(QJSON)):
        r = client.post("/api/quizzes/generate", json={"doc_ids": [did], "count": 3, "types": ["mcq", "fill", "numeric"]})
    q = r.json["quiz"]
    assert len(q["questions"]) == 3 and "answer" not in q["questions"][0]
    ans = {"0": 1, "1": "  ACCELERATION ", "2": "6.0"}
    res = client.post(f"/api/quizzes/{q['id']}/submit", json={"answers": ans, "duration": 60}).json["attempt"]
    assert res["score"] == 3 and res["topics"]["Dynamics"] == 100
    assert client.get("/api/quizzes/history").json["attempts"][0]["total"] == 3
    assert client.get("/api/progress").json["subject_performance"]


def test_quiz_eval_units():
    assert qs.evaluate({"type": "fill", "answer": "Mitochondria", "accepted": ["the mitochondrion"]}, "The  Mitochondrion") == 1
    assert qs.evaluate({"type": "match", "answer": [1, 0]}, [1, 0]) == 1 and qs.evaluate({"type": "match", "answer": [1, 0]}, [0, 0]) == 0.5
    assert qs.validate({"type": "tf", "question": "Water boils at 100C at sea level", "answer": "true"}, {"tf"})["answer"] == 0


def test_flashcards_spaced_repetition(client):
    register(client)
    did = upload(client).json["documents"][0]["id"]
    with patch("studymentor.services.groq_service.chat", return_value='{"cards":[{"front":"F=?","back":"ma","topic":"Dyn"}]}'):
        cid = client.post("/api/flashcards/generate", json={"doc_ids": [did]}).json["cards"][0]["id"]
    c = client.post(f"/api/flashcards/{cid}/review", json={"rating": "easy"}).json["card"]
    assert c["interval"] == 4
    assert client.get("/api/flashcards?due=1").json["cards"] == []


def test_settings_persist_and_validate(client):
    register(client)
    assert client.patch("/api/settings", json={"theme": "dark", "speech_rate": 1.5, "voice_enabled": False}).status_code == 200
    s = client.get("/api/settings").json["settings"]
    assert s["theme"] == "dark" and s["voice_enabled"] is False and s["speech_rate"] == 1.5
    assert client.patch("/api/settings", json={"theme": "neon"}).status_code == 400


def test_planner_and_dashboard(client):
    register(client)
    t = client.post("/api/planner/tasks", json={"title": "Read ch1", "minutes": 45}).json["task"]
    client.patch(f"/api/planner/tasks/{t['id']}", json={"done": True})
    d = client.get("/api/dashboard").json
    assert d["stats"]["sessions"] == 1 and d["upcoming_tasks"] == []


def test_rate_limit(tmp_path):
    from studymentor import create_app
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "UPLOAD_FOLDER": str(tmp_path),
                      "CSRF_ENABLED": False, "RATELIMIT_ENABLED": True, "SQLALCHEMY_ENGINE_OPTIONS": {}})
    c = app.test_client()
    codes = [c.post("/api/auth/login", json={"email": "x@y.com", "password": "z"}).status_code for _ in range(12)]
    assert 429 in codes


def test_csrf_enforced(app):
    app.config["CSRF_ENABLED"] = True
    c = app.test_client()
    register(c)
    assert c.post("/api/planner/tasks", json={"title": "x"}).status_code == 403
    tok = c.get("/api/auth/csrf").json["csrf"]
    assert c.post("/api/planner/tasks", json={"title": "x"}, headers={"X-CSRF-Token": tok}).status_code == 201


def test_delete_account(client):
    register(client)
    upload(client)
    assert client.delete("/api/auth/account", json={"password": "password123"}).status_code == 200
    assert client.get("/api/auth/me").json["user"] is None
