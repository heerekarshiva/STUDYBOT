"""Simple DB-backed lexical retrieval (TF-IDF style). Embeddings are optional and not assumed."""
import math
import re
from collections import Counter
from flask import current_app
from ..models import Chunk, Document

STOP = set("the a an and or of to in is are was were be for on with as by that this it from at which what how why when who whom do does did can could should would will you your i me my we our about explain tell give please".split())


def tokens(t):
    return [w for w in re.findall(r"[a-z0-9]{2,}", (t or "").lower()) if w not in STOP]


def _load(user_id, doc_ids):
    names = {d.id: d.name for d in Document.query.filter(Document.user_id == user_id, Document.id.in_(doc_ids or [])).all()}
    if not names:
        return [], names
    rows = Chunk.query.filter(Chunk.user_id == user_id, Chunk.document_id.in_(list(names))).order_by(Chunk.document_id, Chunk.idx).all()
    return rows, names


def _fmt(c, names):
    return {"doc": names[c.document_id], "doc_id": c.document_id, "page": c.page, "heading": c.heading, "text": c.text}


def search(user_id, doc_ids, query, budget=None):
    budget = budget or current_app.config["MAX_CONTEXT_CHARS"]
    rows, names = _load(user_id, doc_ids)
    q = tokens(query)
    if not rows:
        return []
    if not q:
        return sample_rows(rows, names, budget)
    toks = [Counter(tokens(c.text + " " + (c.heading or ""))) for c in rows]
    df = Counter(t for tk in toks for t in set(tk))
    n = len(rows)
    scored = []
    for c, tk in zip(rows, toks):
        s = sum((1 + math.log(tk[t])) * math.log(1 + n / df[t]) for t in q if tk.get(t))
        if s:
            scored.append((s / math.sqrt(sum(tk.values()) + 20), c))
    scored.sort(key=lambda x: -x[0])
    out, used = [], 0
    for _, c in scored:
        if used + len(c.text) > budget:
            break
        out.append(c)
        used += len(c.text)
    out.sort(key=lambda c: (c.document_id, c.idx))
    return [_fmt(c, names) for c in out] or sample_rows(rows, names, budget)


def sample_rows(rows, names, budget):
    avg = max(1, sum(len(c.text) for c in rows) // len(rows))
    k = max(1, min(len(rows), budget // avg))
    step = len(rows) / k
    return [_fmt(rows[int(i * step)], names) for i in range(k)]


def sample(user_id, doc_ids, budget=None):
    rows, names = _load(user_id, doc_ids)
    return sample_rows(rows, names, budget or current_app.config["MAX_CONTEXT_CHARS"]) if rows else []


def build_context(chunks):
    return "\n\n".join(f"[Document: {c['doc']} | Page {c['page']}{' | ' + c['heading'] if c['heading'] else ''}]\n{c['text']}" for c in chunks)


def sources(chunks):
    seen, out = set(), []
    for c in chunks:
        k = (c["doc"], c["page"])
        if k not in seen:
            seen.add(k)
            out.append({"doc": c["doc"], "doc_id": c["doc_id"], "page": c["page"]})
    return out[:12]
