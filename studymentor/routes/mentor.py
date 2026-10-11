from flask import Blueprint, g, request, current_app
from .. import db, limiter
from ..models import Conversation, Message
from ..services import groq_service as ai, retrieval_service as rs
from ..services.prompts import SYSTEM, LENGTH, context, owned_doc_ids
from ..utils.security import APIError, login_required, body, s, owned
from .settings import get_settings

bp = Blueprint("mentor", __name__, url_prefix="/api/mentor")
MODE = {"normal": "", "hint": "The student wants a HINT only. Do not reveal the full solution; give a nudge and a guiding question.",
        "steps": "Solve step by step, numbering each step and explaining why.",
        "example": "Give a concrete example and an analogy."}


@bp.post("/chat")
@login_required
@limiter.limit(lambda: current_app.config["AI_LIMIT"])
def chat():
    d = body()
    msg = s(d.get("message"), 4000)
    if not msg:
        raise APIError("Message is empty.")
    conv = owned(Conversation, d["conversation_id"], g.user.id) if d.get("conversation_id") else None
    if not conv:
        conv = Conversation(user_id=g.user.id, title=msg[:60], doc_ids=[])
        db.session.add(conv)
        db.session.flush()
    if isinstance(d.get("doc_ids"), list):
        conv.doc_ids = owned_doc_ids(g.user.id, d["doc_ids"])
    pref = get_settings(g.user.id)
    chunks = context(g.user.id, conv.doc_ids, msg, required=False)
    hist = Message.query.filter_by(conversation_id=conv.id).order_by(Message.id.desc()).limit(current_app.config["MAX_HISTORY_MESSAGES"]).all()[::-1]
    sys = (SYSTEM + f"\nPreferred language: {pref['language']}. Explanation style: {pref['explanation_style']}. {LENGTH[pref['answer_length']]}"
           + (" This is a spoken voice conversation: answer in short natural sentences, no tables or markdown symbols." if d.get("voice") else "")
           + (" " + MODE.get(d.get("mode"), "") if d.get("mode") else ""))
    note = ("" if chunks else "\n(No study material is selected or matched; answer from general knowledge and say so.)")
    ctx = f"<context>\n{rs.build_context(chunks)}\n</context>\n\n" if chunks else ""
    msgs = [{"role": "system", "content": sys}] + [{"role": m.role, "content": m.content[:2500]} for m in hist] + \
           [{"role": "user", "content": f"{ctx}Student question: {msg}{note}"}]
    answer = ai.chat(msgs, user_id=g.user.id, feature="mentor", max_tokens=1200)
    db.session.add(Message(conversation_id=conv.id, role="user", content=msg))
    srcs = rs.sources(chunks)
    am = Message(conversation_id=conv.id, role="assistant", content=answer, sources=srcs)
    db.session.add(am)
    db.session.commit()
    return {"conversation": conv.to_dict(), "message": am.to_dict()}


@bp.get("/conversations")
@login_required
def conversations():
    q = Conversation.query.filter_by(user_id=g.user.id)
    if request.args.get("q"):
        t = f"%{request.args['q'][:60]}%"
        ids = {m.conversation_id for m in Message.query.join(Conversation).filter(Conversation.user_id == g.user.id, Message.content.ilike(t))}
        q = q.filter(Conversation.title.ilike(t) | Conversation.id.in_(ids))
    return {"conversations": [c.to_dict() for c in q.order_by(Conversation.updated_at.desc()).limit(100)]}


@bp.get("/conversations/<int:cid>")
@login_required
def get_conv(cid):
    c = owned(Conversation, cid, g.user.id)
    return {"conversation": c.to_dict(), "messages": [m.to_dict() for m in c.messages]}


@bp.patch("/conversations/<int:cid>")
@login_required
def rename(cid):
    c = owned(Conversation, cid, g.user.id)
    c.title = s(body().get("title"), 200) or c.title
    db.session.commit()
    return {"conversation": c.to_dict()}


@bp.delete("/conversations/<int:cid>")
@login_required
def delete(cid):
    db.session.delete(owned(Conversation, cid, g.user.id))
    db.session.commit()
    return {"ok": True}


@bp.post("/messages/<int:mid>/save")
@login_required
def save_msg(mid):
    m = db.session.get(Message, mid)
    if not m or m.conversation.user_id != g.user.id:
        raise APIError("Not found.", 404)
    m.saved = not m.saved
    db.session.commit()
    return {"saved": m.saved}


@bp.post("/conversations/<int:cid>/summary")
@login_required
@limiter.limit(lambda: current_app.config["AI_LIMIT"])
def summarize(cid):
    c = owned(Conversation, cid, g.user.id)
    txt = "\n".join(f"{m.role}: {m.content[:600]}" for m in c.messages[-20:])
    if not txt:
        raise APIError("Conversation is empty.")
    out = ai.chat([{"role": "system", "content": "Summarise this tutoring conversation in 5 bullet points, then list topics to revise."},
                   {"role": "user", "content": txt}], user_id=g.user.id, feature="summary", max_tokens=500)
    return {"summary": out}
