from datetime import datetime, date
from flask import Blueprint, g, request
from sqlalchemy import func
from .. import db
from ..models import (Task, Subject, StudySession, Document, Note, QuizAttempt, Flashcard, FlashcardReview, Conversation)
from ..services import stats
from ..utils.security import APIError, login_required, body, s, i, owned, parse_date

bp = Blueprint("planner", __name__, url_prefix="/api")


@bp.post("/planner/tasks")
@login_required
def add_task():
    d = body()
    t = s(d.get("title"), 200)
    if not t:
        raise APIError("Task title is required.")
    task = Task(user_id=g.user.id, title=t, subject=s(d.get("subject"), 100), minutes=i(d.get("minutes"), 30, 5, 600), due=parse_date(d.get("due")))
    db.session.add(task)
    db.session.commit()
    return {"task": task.to_dict()}, 201


@bp.get("/planner/tasks")
@login_required
def tasks():
    rows = Task.query.filter_by(user_id=g.user.id).order_by(Task.done, Task.due.is_(None), Task.due).all()
    return {"tasks": [t.to_dict() for t in rows]}


@bp.patch("/planner/tasks/<int:tid>")
@login_required
def patch_task(tid):
    t, d = owned(Task, tid, g.user.id), body()
    if "done" in d:
        t.done = bool(d["done"])
        if t.done:
            db.session.add(StudySession(user_id=g.user.id, kind="task", minutes=t.minutes))
    if "title" in d:
        t.title = s(d["title"], 200) or t.title
    if "due" in d:
        t.due = parse_date(d["due"])
    db.session.commit()
    return {"task": t.to_dict()}


@bp.delete("/planner/tasks/<int:tid>")
@login_required
def del_task(tid):
    db.session.delete(owned(Task, tid, g.user.id))
    db.session.commit()
    return {"ok": True}


@bp.route("/planner/subjects", methods=["GET", "POST"])
@login_required
def subjects():
    if request.method == "POST":
        d = body()
        n = s(d.get("name"), 100)
        if not n:
            raise APIError("Subject name is required.")
        sub = Subject(user_id=g.user.id, name=n, exam_date=parse_date(d.get("exam_date")), daily_goal_min=i(d.get("daily_goal_min"), 60, 5, 720))
        db.session.add(sub)
        db.session.commit()
        return {"subject": sub.to_dict()}, 201
    return {"subjects": [x.to_dict() for x in Subject.query.filter_by(user_id=g.user.id).order_by(Subject.exam_date)]}


@bp.delete("/planner/subjects/<int:sid>")
@login_required
def del_subject(sid):
    db.session.delete(owned(Subject, sid, g.user.id))
    db.session.commit()
    return {"ok": True}


@bp.post("/planner/sessions")
@login_required
def log_session():
    d = body()
    db.session.add(StudySession(user_id=g.user.id, kind=s(d.get("kind"), 30) or "study", minutes=max(0.1, min(600, float(d.get("minutes") or 1)))))
    db.session.commit()
    return {"ok": True}


@bp.get("/progress")
@login_required
def progress():
    u = g.user.id
    wk = stats.weekly_minutes(u)
    goal = sum(x.daily_goal_min for x in Subject.query.filter_by(user_id=u)) or 60
    today_min = db.session.query(func.coalesce(func.sum(StudySession.minutes), 0)).filter(
        StudySession.user_id == u, StudySession.created_at >= datetime.combine(date.today(), datetime.min.time())).scalar()
    att = QuizAttempt.query.filter_by(user_id=u).order_by(QuizAttempt.created_at).all()
    return {"weekly": wk, "subject_performance": stats.subject_perf(u), "weak_topics": stats.weak_topics(u),
            "score_trend": [round(100 * a.score / a.total) for a in att[-15:] if a.total], "daily_goal_min": goal, "today_min": round(today_min, 1)}


@bp.get("/dashboard")
@login_required
def dashboard():
    u = g.user.id
    att = QuizAttempt.query.filter_by(user_id=u).all()
    avg = round(100 * sum(a.score for a in att) / max(1, sum(a.total for a in att))) if att else None
    sess = StudySession.query.filter_by(user_id=u)
    return {
        "stats": {"documents": Document.query.filter_by(user_id=u).count(), "notes": Note.query.filter_by(user_id=u).count(),
                  "quizzes": len(att), "avg_score": avg, "cards_reviewed": FlashcardReview.query.filter_by(user_id=u).count(),
                  "sessions": sess.count(), "cards_due": Flashcard.query.filter(Flashcard.user_id == u, Flashcard.due <= date.today()).count()},
        "recent_documents": [d.to_dict() for d in Document.query.filter_by(user_id=u).order_by(Document.created_at.desc()).limit(5)],
        "recent_conversations": [c.to_dict() for c in Conversation.query.filter_by(user_id=u).order_by(Conversation.updated_at.desc()).limit(5)],
        "upcoming_tasks": [t.to_dict() for t in Task.query.filter_by(user_id=u, done=False).order_by(Task.due.is_(None), Task.due).limit(5)],
        "weak_topics": stats.weak_topics(u), "weekly": stats.weekly_minutes(u),
        "exams": [x.to_dict() for x in Subject.query.filter(Subject.user_id == u, Subject.exam_date >= date.today()).order_by(Subject.exam_date).limit(3)],
    }
