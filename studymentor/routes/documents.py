import os
import uuid
from flask import Blueprint, g, request, current_app, send_file
from .. import db
from ..models import Document, Chunk
from ..services import document_service, ocr_service
from ..utils.security import APIError, login_required, owned, body, s

bp = Blueprint("documents", __name__, url_prefix="/api/documents")
EXT = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def sniff(head):
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def _dir(uid):
    p = os.path.join(current_app.config["UPLOAD_FOLDER"], str(uid))
    os.makedirs(p, exist_ok=True)
    return p


@bp.post("/upload")
@login_required
def upload():
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        raise APIError("No files received.")
    subject, topic = s(request.form.get("subject"), 100), s(request.form.get("topic"), 100)
    limit = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    done, errors = [], []
    for f in files[:10]:
        name = os.path.basename(f.filename or "file")
        ext = os.path.splitext(name)[1].lower()
        if ext not in EXT:
            errors.append(f"{name}: unsupported type (PDF, PNG, JPG, JPEG only).")
            continue
        head = f.stream.read(16)
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        mime = sniff(head)
        if mime is None or mime != EXT[ext] and not (mime == "image/jpeg" and ext in (".jpg", ".jpeg")):
            errors.append(f"{name}: file contents do not match its type.")
            continue
        if size > limit:
            errors.append(f"{name}: larger than {current_app.config['MAX_UPLOAD_MB']} MB.")
            continue
        if size == 0:
            errors.append(f"{name}: empty file.")
            continue
        stored = uuid.uuid4().hex + ext
        f.save(os.path.join(_dir(g.user.id), stored))
        d = Document(user_id=g.user.id, name=name, original_name=name, stored_name=stored, mime=mime, size=size,
                     subject=subject, topic=topic, status="processing")
        db.session.add(d)
        db.session.commit()
        document_service.start(current_app._get_current_object(), d.id)
        db.session.refresh(d)
        done.append(d.to_dict())
    if not done and errors:
        raise APIError(" ".join(errors), 400, "invalid_file")
    return {"documents": done, "errors": errors, "ocr_available": ocr_service.available()}, 201


@bp.get("")
@login_required
def listing():
    q = Document.query.filter_by(user_id=g.user.id)
    if request.args.get("q"):
        q = q.filter(Document.name.ilike(f"%{request.args['q'][:60]}%"))
    if request.args.get("subject"):
        q = q.filter(Document.subject == request.args["subject"])
    return {"documents": [d.to_dict() for d in q.order_by(Document.created_at.desc()).all()],
            "ocr_available": ocr_service.available()}


@bp.get("/<int:did>")
@login_required
def get(did):
    d = owned(Document, did, g.user.id)
    out = d.to_dict()
    if request.args.get("text"):
        chunks = Chunk.query.filter_by(document_id=d.id).order_by(Chunk.idx).limit(400).all()
        out["chunks"] = [{"page": c.page, "heading": c.heading, "text": c.text, "ocr": c.ocr} for c in chunks]
    return {"document": out}


@bp.get("/<int:did>/file")
@login_required
def file(did):
    d = owned(Document, did, g.user.id)
    return send_file(os.path.join(_dir(g.user.id), d.stored_name), mimetype=d.mime, download_name=d.name)


@bp.patch("/<int:did>")
@login_required
def patch(did):
    d, b = owned(Document, did, g.user.id), body()
    for k, n in (("name", 255), ("subject", 100), ("topic", 100)):
        if k in b:
            setattr(d, k, s(b[k], n) or (d.name if k == "name" else ""))
    db.session.commit()
    return {"document": d.to_dict()}


@bp.delete("/<int:did>")
@login_required
def delete(did):
    d = owned(Document, did, g.user.id)
    try:
        os.remove(os.path.join(_dir(g.user.id), d.stored_name))
    except OSError:
        pass
    db.session.delete(d)
    db.session.commit()
    return {"ok": True}


@bp.post("/<int:did>/process")
@login_required
def reprocess(did):
    d = owned(Document, did, g.user.id)
    if d.status == "processing":
        raise APIError("Already processing.", 409)
    d.status, d.progress = "processing", 0
    db.session.commit()
    document_service.start(current_app._get_current_object(), d.id)
    db.session.refresh(d)
    return {"document": d.to_dict()}
