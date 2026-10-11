from flask import Blueprint, g
from .. import db
from ..models import (Setting, Document, Note, Conversation, Quiz, QuizAttempt, Flashcard, Task, Subject, StudySession)
from ..utils.security import APIError, login_required, body

bp = Blueprint("settings", __name__, url_prefix="/api/settings")
DEFAULTS = {"theme": "system", "explanation_style": "standard", "answer_length": "medium", "language": "English",
            "default_subject": "", "exam_pref": "", "voice_enabled": True, "continuous": True, "spoken": True,
            "speech_rate": 1.0, "voice_name": "", "push_to_talk": False, "daily_card_goal": 20}
ENUMS = {"theme": {"light", "dark", "system"}, "explanation_style": {"beginner", "standard", "advanced", "exam"},
         "answer_length": {"short", "medium", "detailed"}}


def get_settings(uid):
    row = Setting.query.filter_by(user_id=uid).first()
    return {**DEFAULTS, **((row.data if row else {}) or {})}


@bp.get("")
@login_required
def read():
    return {"settings": get_settings(g.user.id)}


@bp.patch("")
@login_required
def update():
    d = body()
    row = Setting.query.filter_by(user_id=g.user.id).first() or Setting(user_id=g.user.id, data={})
    cur = dict(row.data or {})
    for k, v in d.items():
        if k not in DEFAULTS:
            continue
        if type(v) is not type(DEFAULTS[k]) and not (isinstance(DEFAULTS[k], float) and isinstance(v, int)):
            raise APIError(f"Invalid value for {k}.")
        if k in ENUMS and v not in ENUMS[k]:
            raise APIError(f"Invalid value for {k}.")
        if k == "speech_rate":
            v = max(0.5, min(2.0, float(v)))
        if k == "daily_card_goal":
            v = max(1, min(500, v))
        cur[k] = v[:100] if isinstance(v, str) else v
    row.data = cur
    db.session.add(row)
    db.session.commit()
    return {"settings": {**DEFAULTS, **cur}}


@bp.get("/export")
@login_required
def export():
    u = g.user.id
    return {
        "user": g.user.to_dict(), "settings": get_settings(u),
        "documents": [d.to_dict() for d in Document.query.filter_by(user_id=u)],
        "notes": [n.to_dict() for n in Note.query.filter_by(user_id=u)],
        "conversations": [{**c.to_dict(), "messages": [m.to_dict() for m in c.messages]} for c in Conversation.query.filter_by(user_id=u)],
        "quiz_attempts": [{"quiz": a.quiz.title, "score": a.score, "total": a.total, "at": a.created_at.isoformat()} for a in QuizAttempt.query.filter_by(user_id=u)],
        "flashcards": [c.to_dict() for c in Flashcard.query.filter_by(user_id=u)],
        "tasks": [t.to_dict() for t in Task.query.filter_by(user_id=u)],
        "subjects": [x.to_dict() for x in Subject.query.filter_by(user_id=u)],
    }
