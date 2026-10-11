"""Central Groq client: model config, retries, context budgeting, JSON validation, usage tracking."""
import json
import logging
import re
import time
from flask import current_app
from .. import db
from ..models import AIUsage

log = logging.getLogger(__name__)


class AIError(Exception):
    def __init__(self, msg, status=502, code="ai_error"):
        super().__init__(msg)
        self.msg, self.status, self.code = msg, status, code


def _client():
    key = current_app.config["GROQ_API_KEY"]
    if not key:
        raise AIError("The AI service is not configured (missing GROQ_API_KEY on the server).", 503, "no_key")
    from groq import Groq
    return Groq(api_key=key, timeout=current_app.config["GROQ_TIMEOUT"], max_retries=0)


def _map_error(e):
    import groq
    m = str(e).lower()
    if isinstance(e, groq.AuthenticationError) or isinstance(e, groq.PermissionDeniedError):
        return AIError("The Groq API key is invalid or lacks permission.", 503, "bad_key"), False
    if isinstance(e, groq.RateLimitError):
        if "quota" in m or "billing" in m:
            return AIError("Groq usage quota exhausted.", 429, "quota"), False
        return AIError("Groq rate limit reached. Please wait a moment and retry.", 429, "ai_rate_limit"), True
    if isinstance(e, groq.NotFoundError):
        return AIError("The configured Groq model is unavailable. Update GROQ_MODEL.", 503, "model_unavailable"), False
    if isinstance(e, groq.BadRequestError):
        if "context" in m or "token" in m:
            return AIError("The request was too large for the model. Select fewer documents or a narrower topic.", 400, "context_length"), False
        return AIError("The AI rejected the request: " + str(e)[:160], 400, "bad_request"), False
    if isinstance(e, (groq.APIConnectionError, groq.APITimeoutError)):
        return AIError("Could not reach the Groq API (network/timeout).", 504, "network"), True
    if isinstance(e, groq.APIStatusError) and getattr(e, "status_code", 500) >= 500:
        return AIError("Groq service error. Try again shortly.", 502, "upstream"), True
    return AIError("AI request failed.", 502, "ai_error"), False


def trim_messages(messages, max_chars=None):
    """Keep system + latest turns within a character budget (~4 chars/token)."""
    max_chars = max_chars or current_app.config["MAX_CONTEXT_CHARS"] + 8000
    total = sum(len(m["content"]) for m in messages)
    msgs = list(messages)
    while total > max_chars and len(msgs) > 2:
        total -= len(msgs.pop(1)["content"])  # drop oldest non-system turn
    if total > max_chars:  # last resort: truncate final user message
        msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"][: max(2000, max_chars - len(msgs[0]["content"]))]}
    return msgs


def chat(messages, user_id=None, feature="chat", json_mode=False, max_tokens=2000, temperature=0.3):
    messages = trim_messages(messages)
    model = current_app.config["GROQ_MODEL"]
    client = _client()
    kw = dict(model=model, messages=messages, max_tokens=max_tokens, temperature=temperature)
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    last = None
    for attempt in range(3):
        try:
            r = client.chat.completions.create(**kw)
            text = (r.choices[0].message.content or "").strip()
            if not text:
                raise AIError("The AI returned an empty response.", 502, "empty")
            try:
                u = r.usage
                db.session.add(AIUsage(user_id=user_id, feature=feature, model=model,
                                       prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                                       completion_tokens=getattr(u, "completion_tokens", 0) or 0))
                db.session.commit()
            except Exception:
                db.session.rollback()
            return text
        except AIError:
            raise
        except Exception as e:
            last, retry = _map_error(e)
            log.warning("Groq error (attempt %s): %s", attempt + 1, e)
            if not retry:
                break
            time.sleep(1.5 * (attempt + 1))
    raise last


def parse_json(text):
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        a, b = t.find("{"), t.rfind("}")
        if a != -1 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except json.JSONDecodeError:
                pass
    raise AIError("The AI returned malformed data. Please try again.", 502, "invalid_response")


def chat_json(messages, **kw):
    return parse_json(chat(messages, json_mode=True, **kw))
