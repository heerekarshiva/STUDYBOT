"""Quiz generation, backend validation of AI output, and answer evaluation."""
import random
import re
from . import groq_service as ai

TYPES = {"mcq", "tf", "fill", "short", "match", "numeric", "assertion"}
ASSERTION_OPTS = ["Both A and R are true and R is the correct explanation of A", "Both A and R are true but R is not the correct explanation of A",
                  "A is true but R is false", "A is false but R is true"]

SCHEMA = """Return ONLY a JSON object: {"questions":[ ... ]}. Each question has "type" and:
- mcq: {"type":"mcq","question","options":[4 strings],"answer":<0-3 index>,"explanation","topic","page":<int or null>}
- tf: {"type":"tf","question","answer":true|false,"explanation","topic","page"}
- fill: {"type":"fill","question":"text with ____","answer":"word/phrase","accepted":[alternative correct answers],"explanation","topic","page"}
- short: {"type":"short","question","answer":"model answer","keywords":[3-6 key terms that a correct answer must contain],"explanation","topic","page"}
- numeric: {"type":"numeric","question","answer":<number>,"tolerance":<relative fraction e.g. 0.01>,"unit":"","explanation","topic","page"}
- match: {"type":"match","question","left":[3-5 items],"right":[same count, right[i] matches left[i]],"explanation","topic","page"}
- assertion: {"type":"assertion","question":"Assertion (A): ... Reason (R): ...","answer":<0-3 index into the standard 4 options>,"explanation","topic","page"}
Use "page" only if the context header shows it, else null. Every question needs a "topic"."""


def norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s.\-/]", "", str(t).lower())).strip()


def validate(q, allowed):
    """Return a normalised question dict or None if malformed."""
    try:
        t = q.get("type")
        text = str(q.get("question", "")).strip()
        if t not in allowed or len(text) < 8:
            return None
        out = {"type": t, "question": text, "explanation": str(q.get("explanation", ""))[:800],
               "topic": str(q.get("topic") or "General")[:80], "page": q.get("page") if isinstance(q.get("page"), int) else None}
        if t == "mcq":
            o = [str(x).strip() for x in q["options"]]
            a = int(q["answer"])
            if len(o) != 4 or len(set(o)) != 4 or not 0 <= a < 4:
                return None
            out.update(options=o, answer=a)
        elif t == "tf":
            a = q["answer"]
            a = a if isinstance(a, bool) else str(a).lower() == "true"
            out.update(options=["True", "False"], answer=0 if a else 1)
        elif t == "assertion":
            a = int(q["answer"])
            if not 0 <= a < 4:
                return None
            out.update(options=ASSERTION_OPTS, answer=a)
        elif t == "fill":
            a = str(q["answer"]).strip()
            if not a:
                return None
            out.update(answer=a, accepted=[str(x) for x in q.get("accepted", [])][:6])
        elif t == "short":
            k = [str(x) for x in q.get("keywords", []) if str(x).strip()]
            if len(k) < 2:
                return None
            out.update(answer=str(q.get("answer", ""))[:800], keywords=k[:8])
        elif t == "numeric":
            out.update(answer=float(q["answer"]), tolerance=max(0.0, min(0.1, float(q.get("tolerance", 0.01)))), unit=str(q.get("unit", ""))[:20])
        elif t == "match":
            l, r = [str(x) for x in q["left"]], [str(x) for x in q["right"]]
            if not 2 <= len(l) <= 6 or len(l) != len(r):
                return None
            perm = list(range(len(r)))
            random.shuffle(perm)  # shuffled right column; answer[i] = index in shuffled list
            shuffled = [r[p] for p in perm]
            out.update(left=l, right=shuffled, answer=[perm.index(i) for i in range(len(l))])
        return out
    except (KeyError, TypeError, ValueError):
        return None


def public(q):
    keep = {"type", "question", "options", "left", "right", "topic", "unit", "page"}
    return {k: v for k, v in q.items() if k in keep}


def evaluate(q, ans):
    """Return score 0..1."""
    t = q["type"]
    try:
        if t in ("mcq", "tf", "assertion"):
            return 1.0 if ans is not None and int(ans) == q["answer"] else 0.0
        if t == "fill":
            a = norm(ans)
            return 1.0 if a and a in {norm(q["answer"])} | {norm(x) for x in q.get("accepted", [])} else 0.0
        if t == "numeric":
            v = float(str(ans).replace(",", "").strip())
            tgt = q["answer"]
            return 1.0 if abs(v - tgt) <= max(abs(tgt) * q["tolerance"], 1e-9) else 0.0
        if t == "short":
            a = norm(ans)
            hit = sum(1 for k in q["keywords"] if norm(k) in a)
            return 1.0 if hit / len(q["keywords"]) >= 0.6 else (0.5 if hit / len(q["keywords"]) >= 0.4 else 0.0)
        if t == "match":
            if not isinstance(ans, list) or len(ans) != len(q["answer"]):
                return 0.0
            return sum(1 for x, y in zip(ans, q["answer"]) if x == y) / len(q["answer"])
    except (TypeError, ValueError):
        return 0.0
    return 0.0


def display_answer(q):
    t = q["type"]
    if t in ("mcq", "tf", "assertion"):
        return q["options"][q["answer"]]
    if t == "match":
        return "; ".join(f"{l} → {q['right'][i]}" for l, i in zip(q["left"], q["answer"]))
    if t == "numeric":
        return f"{q['answer']:g} {q.get('unit', '')}".strip()
    return str(q["answer"])


def generate(user_id, system, context_block, n, difficulty, types, topic, category):
    out, tries = [], 0
    while len(out) < n and tries < 3:
        k = min(10, n - len(out))
        task = (f"Create {k} {difficulty}-difficulty questions{' for ' + category if category else ''}{' on ' + topic if topic else ''}. "
                f"Allowed types: {', '.join(types)} (mix them). Questions must be answerable and unambiguous.\n{SCHEMA}")
        data = ai.chat_json([{"role": "system", "content": system}, {"role": "user", "content": f"{context_block}\n\n{task}"}],
                            user_id=user_id, feature="quiz", max_tokens=3500, temperature=0.5)
        for q in (data.get("questions") or []):
            v = validate(q, set(types))
            if v and all(norm(v["question"]) != norm(o["question"]) for o in out):
                out.append(v)
        tries += 1
    if not out:
        raise ai.AIError("The AI could not produce valid questions. Try again or choose different settings.", 502, "invalid_response")
    return out[:n]
