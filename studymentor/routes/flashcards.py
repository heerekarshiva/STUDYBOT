from datetime import date, timedelta, datetime
from flask import Blueprint, g, request, current_app
from .. import db, limiter
from ..models import Flashcard, FlashcardReview, StudySession, Note
from ..services import groq_service as ai, retrieval_service as rs
from ..services.prompts import SYSTEM, context, user_msg
from ..utils.security import APIError, login_required, body, s, i, owned
from .settings import get_settings

bp = Blueprint("flashcards", __name__, url_prefix="/api/flashcards")


def schedule(c, rating):
    if rating == "hard":
        c.interval, c.ease, c.reps = 1, max(1.3, c.ease - 0.2), 0
    elif rating == "medium":
        c.interval = 2 if c.reps == 0 else max(2, round(c.interval * c.ease))
        c.reps += 1
    else:
        c.interval = 4 if c.reps == 0 else max(4, round(c.interval * c.ease * 1.3))
        c.ease, c.reps = c.ease + 0.1, c.reps + 1
    c.due = date.today() + timedelta(days=c.interval)


@bp.post("/generate")
@login_required
@limiter.limit(lambda: current_app.config["AI_LIMIT"])
def generate():
    d = body()
    n, topic = i(d.get("count"), 15, 3, 40), s(d.get("topic"), 150)
    if d.get("note_id"):
        note = owned(Note, d["note_id"], g.user.id)
        chunks, ctx = [], f"<context>\n[Saved note: {note.title}]\n{note.content[:12000]}\n</context>\n\n"
    else:
        chunks = context(g.user.id, d.get("doc_ids"), topic)
        ctx = f"<context>\n{rs.build_context(chunks)}\n</context>\n\n"
    task = (f"Create {n} flashcards{' about ' + topic if topic else ''}. Return ONLY JSON: "
            '{"cards":[{"front":"question or term","back":"concise answer/explanation","topic":"short topic tag"}]}. No duplicates.')
    data = ai.chat_json([{"role": "system", "content": SYSTEM}, {"role": "user", "content": ctx + task}], user_id=g.user.id, feature="flashcards", max_tokens=3000, temperature=0.4)
    src = ", ".join(sorted({c["doc"] for c in chunks}))[:200]
    made = []
    for c in data.get("cards") or []:
        if isinstance(c, dict) and isinstance(c.get("front"), str) and isinstance(c.get("back"), str) and c["front"].strip() and c["back"].strip():
            made.append(Flashcard(user_id=g.user.id, front=c["front"][:1000], back=c["back"][:2000], topic=s(c.get("topic"), 100), source=src))
    if not made:
        raise ai.AIError("No valid flashcards were produced. Try again.", 502, "invalid_response")
    db.session.add_all(made)
    db.session.commit()
    return {"cards": [c.to_dict() for c in made]}, 201


@bp.get("")
@login_required
def listing():
    q = Flashcard.query.filter_by(user_id=g.user.id)
    if request.args.get("due"):
        q = q.filter(Flashcard.due <= date.today())
    if request.args.get("bookmarked"):
        q = q.filter(Flashcard.bookmarked.is_(True))
    cards = q.order_by(Flashcard.due, Flashcard.id).limit(300).all()
    today = datetime.utcnow().date()
    done = FlashcardReview.query.filter(FlashcardReview.user_id == g.user.id, FlashcardReview.created_at >= datetime.combine(today, datetime.min.time())).count()
    return {"cards": [c.to_dict() for c in cards], "reviewed_today": done, "daily_goal": get_settings(g.user.id)["daily_card_goal"],
            "total": Flashcard.query.filter_by(user_id=g.user.id).count(),
            "due_count": Flashcard.query.filter(Flashcard.user_id == g.user.id, Flashcard.due <= date.today()).count()}


@bp.post("/<int:cid>/review")
@login_required
def review(cid):
    c, d = owned(Flashcard, cid, g.user.id), body()
    if d.get("rating") not in ("easy", "medium", "hard"):
        raise APIError("Rating must be easy, medium or hard.")
    schedule(c, d["rating"])
    db.session.add(FlashcardReview(user_id=g.user.id, card_id=c.id, rating=d["rating"]))
    db.session.add(StudySession(user_id=g.user.id, kind="flashcards", minutes=0.5))
    db.session.commit()
    return {"card": c.to_dict()}


@bp.patch("/<int:cid>")
@login_required
def patch(cid):
    c, d = owned(Flashcard, cid, g.user.id), body()
    if "bookmarked" in d:
        c.bookmarked = bool(d["bookmarked"])
    db.session.commit()
    return {"card": c.to_dict()}


@bp.delete("/<int:cid>")
@login_required
def delete(cid):
    db.session.delete(owned(Flashcard, cid, g.user.id))
    db.session.commit()
    return {"ok": True}
