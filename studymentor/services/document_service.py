"""PDF/image text extraction, OCR fallback, heading detection and overlapping chunking."""
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from .. import db
from ..models import Document, Chunk
from . import ocr_service

log = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=2)


def chunk_text(text, size=1200, overlap=200):
    text = re.sub(r"[ \t]+", " ", text).strip()
    out, i, n = [], 0, len(text)
    while i < n:
        j = min(n, i + size)
        if j < n:
            k = max(text.rfind("\n", i + size // 2, j), text.rfind(". ", i + size // 2, j), text.rfind(" ", i + size // 2, j))
            if k != -1:
                j = k + 1
        piece = text[i:j].strip()
        if piece:
            out.append(piece)
        if j >= n:
            break
        i = max(j - overlap, i + 1)
    return out


def find_heading(text, prev=""):
    for line in text.splitlines()[:6]:
        l = line.strip()
        if 3 <= len(l) <= 80 and not l.endswith((".", ",", ";")) and (l.isupper() or re.match(r"^(chapter|unit|section|\d+(\.\d+)*)\b", l, re.I) or l.istitle()):
            return l
    return prev


def start(app, doc_id):
    if app.config.get("PROCESS_SYNC"):
        return process(app, doc_id)
    _pool.submit(process, app, doc_id)


def process(app, doc_id):
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        if not doc:
            return
        path = os.path.join(app.config["UPLOAD_FOLDER"], str(doc.user_id), doc.stored_name)
        warnings, total_chars, heading = [], 0, ""
        try:
            doc.status, doc.progress, doc.error = "processing", 1, None
            Chunk.query.filter_by(document_id=doc.id).delete()
            db.session.commit()
            pages = []  # (page_no, text, used_ocr)
            if doc.mime == "application/pdf":
                import fitz
                pdf = fitz.open(path)
                n = pdf.page_count
                if n > app.config["MAX_PDF_PAGES"]:
                    raise ValueError(f"PDF has {n} pages; the limit is {app.config['MAX_PDF_PAGES']}.")
                doc.pages = n
                for p in range(n):
                    page, text, used = pdf[p], "", False
                    try:
                        text = page.get_text()
                    except Exception as e:
                        warnings.append(f"Page {p+1}: text extraction failed ({e}).")
                    if len(text.strip()) < 40:  # likely scanned
                        try:
                            from PIL import Image
                            pix = page.get_pixmap(dpi=200)
                            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                            text, used = ocr_service.ocr_image(img), True
                        except ocr_service.OCRUnavailable:
                            if not text.strip():
                                warnings.append(f"Page {p+1}: looks scanned but OCR is unavailable on this server.")
                        except Exception as e:
                            warnings.append(f"Page {p+1}: OCR failed ({str(e)[:80]}).")
                    pages.append((p + 1, text, used))
                    doc.progress = max(1, int(90 * (p + 1) / n))
                    if (p + 1) % 5 == 0:
                        db.session.commit()
                pdf.close()
            else:
                from PIL import Image
                img = Image.open(path)
                img.load()
                doc.pages = 1
                try:
                    pages.append((1, ocr_service.ocr_image(img.convert("RGB")), True))
                except ocr_service.OCRUnavailable:
                    warnings.append("Image OCR is unavailable on this server (Tesseract not installed).")
            idx = 0
            for pno, text, used in pages:
                heading = find_heading(text, heading) if text.strip() else heading
                for piece in chunk_text(text):
                    db.session.add(Chunk(document_id=doc.id, user_id=doc.user_id, page=pno, heading=heading[:200],
                                         idx=idx, text=piece, ocr=used))
                    idx += 1
                    total_chars += len(piece)
            if total_chars == 0:
                raise ValueError("No readable text found. " + (warnings[0] if warnings else "Try a clearer file."))
            doc.status, doc.progress = "ready", 100
        except Exception as e:
            log.exception("Document processing failed")
            db.session.rollback()
            doc = db.session.get(Document, doc_id)
            doc.status, doc.error = "failed", str(e)[:300]
        doc.warnings = warnings[:50]
        db.session.commit()
