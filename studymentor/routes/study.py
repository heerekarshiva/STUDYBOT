from flask import Blueprint, g, request
from .. import db, limiter
from ..models import Note
from ..services import groq_service as ai, retrieval_service as rs
from ..services.prompts import SYSTEM, context, user_msg
from ..utils.security import APIError, login_required, body, s, owned
from .settings import get_settings
from flask import current_app

bp = Blueprint("study", __name__, url_prefix="/api/study")
AI_LIMIT = lambda: current_app.config["AI_LIMIT"]

NOTE_KINDS = {
    "chapter": "comprehensive chapter notes with ## sections, ### subsections, bullets and tables where useful",
    "revision": "short revision notes (crisp bullets, one idea per line)",
    "beginner": "beginner-friendly explanations using plain language and small examples",
    "topic": "topic-wise notes organised by topic",
    "exam": "exam-oriented notes highlighting what is commonly asked, mark-worthy points and common mistakes",
    "definitions": "a glossary of important definitions and key concepts",
    "facts": "important facts, dates and figures in a table",
    "derivations": "step-by-step derivations with every step justified",
    "examples": "worked examples and real-world applications",
    "mistakes": "common mistakes and misconceptions with corrections",
    "lastminute": "a last-minute revision summary that fits one page",
    "qa": "important questions with model answers",
}
MODES = {
    "beginner": "Explain Like I'm a Beginner: simple words, an analogy, no jargon without definition.",
    "standard": "Standard academic explanation with correct terminology.",
    "advanced": "Advanced technical explanation with rigour, edge cases and derivations.",
    "exam": "Exam-oriented explanation: key points, formulas, likely question patterns, common traps.",
    "examples": "Explain mainly through concrete, varied examples.",
    "steps": "Explain step by step in numbered stages.",
}


def _save(title, kind, content, chunks, subject=""):
    n = Note(user_id=g.user.id, title=title[:200], kind=kind, content=content, subject=subject[:100], sources=rs.sources(chunks))
    db.session.add(n)
    db.session.commit()
    return n


def _generate_notes(kind_key, d):
    pref = get_settings(g.user.id)
    topic = s(d.get("topic"), 200)
    chunks = context(g.user.id, d.get("doc_ids"), topic)
    task = (f"Create {NOTE_KINDS[kind_key]}.\nSubject: {s(d.get('subject'), 100) or 'as in the material'}\nChapter/topic: {topic or 'whole selected material'}\n"
            f"Academic level: {s(d.get('level'), 60) or 'undergraduate'}\nComplexity: {s(d.get('complexity'), 40) or 'medium'}\n"
            f"Length: {s(d.get('length'), 40) or 'medium'}\nExam type: {s(d.get('exam'), 60) or 'general'}\n"
            f"Output language: {s(d.get('language'), 40) or pref['language']}\n"
            "Structure with a # title then ## sections. Cite sources like (Doc name, p.N) only when shown in context. "
            "If a page cannot be cited, do not cite it.")
    text = ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg(task, chunks)}],
                   user_id=g.user.id, feature="notes", max_tokens=3000)
    return _save((topic or "Study") + " - " + kind_key, "notes", text, chunks, s(d.get("subject"), 100))


@bp.post("/notes")
@login_required
@limiter.limit(AI_LIMIT)
def notes():
    d = body()
    k = d.get("kind", "chapter")
    if k not in NOTE_KINDS:
        raise APIError("Unknown notes type.")
    return {"note": _generate_notes(k, d).to_dict()}


@bp.post("/summary")
@login_required
@limiter.limit(AI_LIMIT)
def summary():
    d = body()
    d.setdefault("length", "short")
    return {"note": _generate_notes("lastminute", d).to_dict()}


@bp.post("/notes/regenerate")
@login_required
@limiter.limit(AI_LIMIT)
def regen():
    d = body()
    section = s(d.get("section"), 6000)
    if not section:
        raise APIError("Nothing to regenerate.")
    chunks = context(g.user.id, d.get("doc_ids"), section[:300], required=False)
    task = f"Rewrite ONLY this section of study notes{', following this instruction: ' + s(d.get('instruction'), 300) if d.get('instruction') else ' with a clearer, improved explanation'}. Keep the same heading level and Markdown format.\n\nSECTION:\n{section}"
    return {"section": ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg(task, chunks)}],
                               user_id=g.user.id, feature="regen", max_tokens=1500)}


@bp.post("/concepts")
@login_required
@limiter.limit(AI_LIMIT)
def concepts():
    d = body()
    concept = s(d.get("concept"), 500)
    if not concept:
        raise APIError("Enter a concept or select text to explain.")
    mode = d.get("mode", "standard")
    if mode not in MODES:
        raise APIError("Unknown explanation mode.")
    chunks = context(g.user.id, d.get("doc_ids"), concept, required=False)
    task = (f"Explain: {concept}\nMode: {MODES[mode]}\nInclude (where relevant): simple explanation, detailed explanation, real-world example, analogy, "
            "step-by-step reasoning, key terminology, comparison with related concepts, advantages/disadvantages, applications, prerequisites & related topics, "
            "common misconceptions, and 3 follow-up questions. Separate document-derived points from '**General knowledge:**'.\n"
            + ("" if chunks else "No document is selected: answer from general knowledge and say so at the top."))
    text = ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg(task, chunks)}],
                   user_id=g.user.id, feature="concept", max_tokens=2500)
    return {"title": concept[:80], "content": text, "sources": rs.sources(chunks)}


@bp.post("/formulas")
@login_required
@limiter.limit(AI_LIMIT)
def formulas():
    d = body()
    topic = s(d.get("topic"), 200)
    chunks = context(g.user.id, d.get("doc_ids"), (topic + " formula equation"))
    task = (f"Build a formula sheet for: {topic or 'the selected material'}. Group by chapter/topic using ## headings. For each topic give a Markdown table with columns: "
            "Formula (LaTeX), Variables & units, When to use, Notes. Add a short worked example for key formulas, and a 'Relationships' list. "
            "Only include formulas present in or directly implied by the context. Source text may come from OCR: if an expression looks garbled or uncertain, "
            "include it but append '⚠ Verify against the source'. Do not claim exam frequency; mark commonly used ones with ⭐ only if they are foundational.")
    text = ai.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg(task, chunks)}],
                   user_id=g.user.id, feature="formulas", max_tokens=3000)
    ocr_used = any(c for c in chunks)  # warning surfaced client-side too
    return {"note": _save((topic or "Formula sheet"), "formula", text, chunks).to_dict(), "ocr_warning": ocr_used}


@bp.get("/notes")
@login_required
def list_notes():
    q = Note.query.filter_by(user_id=g.user.id)
    if request.args.get("kind"):
        q = q.filter(Note.kind == request.args["kind"])
    if request.args.get("q"):
        q = q.filter(Note.title.ilike(f"%{request.args['q'][:60]}%") | Note.content.ilike(f"%{request.args['q'][:60]}%"))
    return {"notes": [n.to_dict(False) for n in q.order_by(Note.updated_at.desc()).limit(100)]}


@bp.get("/notes/<int:nid>")
@login_required
def get_note(nid):
    return {"note": owned(Note, nid, g.user.id).to_dict()}


@bp.post("/notes/save")
@login_required
def save_note():
    d = body()
    n = Note(user_id=g.user.id, title=s(d.get("title"), 200) or "Untitled", kind=s(d.get("kind"), 30) or "notes",
             content=s(d.get("content"), 200000), sources=d.get("sources") if isinstance(d.get("sources"), list) else [])
    db.session.add(n)
    db.session.commit()
    return {"note": n.to_dict()}, 201


@bp.patch("/notes/<int:nid>")
@login_required
def patch_note(nid):
    n, d = owned(Note, nid, g.user.id), body()
    if "title" in d:
        n.title = s(d["title"], 200) or n.title
    if "content" in d:
        n.content = s(d["content"], 200000)
    if isinstance(d.get("bookmarks"), list):
        n.bookmarks = [s(x, 200) for x in d["bookmarks"]][:100]
    db.session.commit()
    return {"note": n.to_dict()}


@bp.delete("/notes/<int:nid>")
@login_required
def del_note(nid):
    db.session.delete(owned(Note, nid, g.user.id))
    db.session.commit()
    return {"ok": True}
