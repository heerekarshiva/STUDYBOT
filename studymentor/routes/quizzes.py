from flask import Blueprint, g, current_app
from .. import db, limiter
from ..models import Quiz, QuizAttempt, StudySession, Document
from ..services import quiz_service as qs, groq_service as ai
from ..services.prompts import SYSTEM, context, user_msg
from ..services import retrieval_service as rs
from ..services.stats import weak_topics
from ..utils.security import APIError, login_required, body, s, i, owned, parse_date
from .settings import get_settings

bp = Blueprint("quizzes", __name__, url_prefix="/api")
LIM = lambda: current_app.config["AI_LIMIT"]


def _client(q):
    return {"id": q.id, "title": q.title, "mode": q.mode, "time_limit": q.time_limit, "category": q.category,
            "subject": q.subject, "difficulty": q.difficulty, "ai_generated": True,
            "questions": [qs.public(x) for x in q.questions]}


@bp.post("/quizzes/generate")
@login_required
@limiter.limit(LIM)
def generate():
    d = body()
    types = [t for t in (d.get("types") or ["mcq"]) if t in qs.TYPES] or ["mcq"]
    n, topic, category = i(d.get("count"), 10, 1, 30), s(d.get("topic"), 150), s(d.get("category"), 60)
    ids = d.get("doc_ids") or []
    chunks = context(g.user.id, ids, topic, required=False)
    if not chunks and not (topic and category):
        raise APIError("Select documents, or give an exam category and topic/syllabus for syllabus-based practice.")
    ctx = f"<context>\n{rs.build_context(chunks)}\n</context>" if chunks else \
        f"No study documents were provided. Base questions on the standard public syllabus for {category}, topic: {topic}. These are original AI-generated practice questions, not official past papers."
    qn = qs.generate(g.user.id, SYSTEM, ctx, n, s(d.get("difficulty"), 20) or "medium", types, topic, category)
    if chunks:
        known = {(c["doc"], c["page"]) for c in chunks}
        names = {c["doc_id"]: c["doc"] for c in chunks}
        for x in qn:
            x["source"] = (list(names.values())[0] + (f", p.{x['page']}" if x["page"] and any(p == x["page"] for _, p in known) else "")) if names else ""
            if x["page"] and not any(p == x["page"] for _, p in known):
                x["page"] = None
    else:
        for x in qn:
            x["page"], x["source"] = None, "AI-generated from general syllabus"
    mode = "timed" if d.get("mode") == "timed" else "practice"
    q = Quiz(user_id=g.user.id, title=s(d.get("title"), 200) or (topic or category or "Quiz") + " quiz", subject=s(d.get("subject"), 100),
             category=category, mode=mode, difficulty=s(d.get("difficulty"), 20) or "medium",
             time_limit=i(d.get("time_limit"), max(5, len(qn)), 1, 240) if mode == "timed" else 0, questions=qn)
    db.session.add(q)
    db.session.commit()
    return {"quiz": _client(q)}, 201


def _own_quiz(qid):
    return owned(Quiz, qid, g.user.id)


@bp.get("/quizzes/<int:qid>")
@login_required
def get_quiz(qid):
    return {"quiz": _client(_own_quiz(qid))}


@bp.post("/quizzes/<int:qid>/check")
@login_required
def check(qid):
    q, d = _own_quiz(qid), body()
    idx = i(d.get("index"), -1, -1, 999)
    if not 0 <= idx < len(q.questions):
        raise APIError("Bad question index.")
    x = q.questions[idx]
    sc = qs.evaluate(x, d.get("answer"))
    return {"score": sc, "correct": sc >= 1, "correct_answer": qs.display_answer(x), "explanation": x["explanation"], "source": x.get("source", "")}


@bp.post("/quizzes/<int:qid>/submit")
@login_required
def submit(qid):
    q, d = _own_quiz(qid), body()
    answers = d.get("answers") if isinstance(d.get("answers"), dict) else {}
    results, topics, total = [], {}, 0.0
    for idx, x in enumerate(q.questions):
        a = answers.get(str(idx))
        sc = qs.evaluate(x, a)
        total += sc
        t = topics.setdefault(x["topic"], [0.0, 0])
        t[0] += sc
        t[1] += 1
        results.append({"index": idx, "question": x["question"], "type": x["type"], "your_answer": a, "score": sc,
                        "correct_answer": qs.display_answer(x), "explanation": x["explanation"], "source": x.get("source", ""),
                        "topic": x["topic"], "options": x.get("options"), "answered": a not in (None, "", [])})
    dur = i(d.get("duration"), 0, 0, 86400)
    att = QuizAttempt(quiz_id=q.id, user_id=g.user.id, score=round(total, 2), total=len(q.questions), answers=answers,
                      results=results, topic_stats=topics, duration=dur)
    db.session.add(att)
    db.session.add(StudySession(user_id=g.user.id, kind="quiz", minutes=max(1, dur / 60)))
    db.session.commit()
    return {"attempt": {"id": att.id, "score": att.score, "total": att.total, "results": results,
                        "topics": {k: round(100 * v[0] / v[1]) for k, v in topics.items()}, "duration": dur}}


@bp.get("/quizzes/history")
@login_required
def history():
    rows = QuizAttempt.query.filter_by(user_id=g.user.id).order_by(QuizAttempt.created_at.desc()).limit(50).all()
    return {"attempts": [{"id": a.id, "quiz_id": a.quiz_id, "title": a.quiz.title, "category": a.quiz.category, "score": a.score,
                          "total": a.total, "duration": a.duration, "at": a.created_at.isoformat() + "Z"} for a in rows]}


@bp.get("/quizzes/attempts/<int:aid>")
@login_required
def attempt(aid):
    a = owned(QuizAttempt, aid, g.user.id)
    return {"attempt": {"id": a.id, "score": a.score, "total": a.total, "results": a.results,
                        "topics": {k: round(100 * v[0] / v[1]) for k, v in (a.topic_stats or {}).items()}}}


@bp.post("/exams/analyze")
@login_required
@limiter.limit(LIM)
def analyze():
    d = body()
    chunks = context(g.user.id, d.get("doc_ids"), "question marks paper section topic")
    task = ("These are uploaded previous-year/practice question papers. Analyse them: list topics by number of questions (count only what you can see), "
            "question patterns, difficulty distribution, and recommended revision priorities. Do not claim anything about future exams.")
    return {"analysis": ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg(task, chunks)}],
                                user_id=g.user.id, feature="paper_analysis", max_tokens=1800), "sources": rs.sources(chunks)}


@bp.post("/exams/schedule")
@login_required
@limiter.limit(LIM)
def schedule():
    d = body()
    cat = s(d.get("category"), 80) or get_settings(g.user.id)["exam_pref"] or "my exam"
    exam = parse_date(d.get("exam_date"))
    weak = weak_topics(g.user.id)
    task = (f"Create a realistic weekly study schedule (Markdown table) for {cat}. Exam date: {exam or 'not set'}. Hours per day: {i(d.get('hours'), 2, 1, 12)}. "
            f"Weak topics from the student's quiz history: {weak or 'none recorded yet'}. Include revision, mock tests and rest. Note that this is a suggestion, not official guidance.")
    return {"plan": ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}], user_id=g.user.id, feature="schedule", max_tokens=1500)}
