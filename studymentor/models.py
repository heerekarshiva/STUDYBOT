from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


def utcnow():
    return datetime.utcnow()


def iso(d):
    return d.isoformat() + ("Z" if isinstance(d, datetime) else "") if d else None


CASCADE = dict(cascade="all, delete-orphan")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    settings = db.relationship("Setting", uselist=False, **CASCADE)
    documents = db.relationship("Document", **CASCADE)
    notes = db.relationship("Note", **CASCADE)
    conversations = db.relationship("Conversation", **CASCADE)
    quizzes = db.relationship("Quiz", **CASCADE)
    attempts = db.relationship("QuizAttempt", **CASCADE)
    flashcards = db.relationship("Flashcard", **CASCADE)
    reviews = db.relationship("FlashcardReview", **CASCADE)
    subjects = db.relationship("Subject", **CASCADE)
    tasks = db.relationship("Task", **CASCADE)
    sessions = db.relationship("StudySession", **CASCADE)
    usage = db.relationship("AIUsage", **CASCADE)

    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        return check_password_hash(self.password_hash, p)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "name": self.name, "created_at": iso(self.created_at)}


def _uid():
    return db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False)


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False)
    data = db.Column(db.JSON, default=dict)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    name = db.Column(db.String(255))
    original_name = db.Column(db.String(255))
    stored_name = db.Column(db.String(100))
    mime = db.Column(db.String(60))
    size = db.Column(db.Integer, default=0)
    pages = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="uploaded")  # uploaded|processing|ready|failed
    progress = db.Column(db.Integer, default=0)
    error = db.Column(db.Text)
    warnings = db.Column(db.JSON, default=list)
    subject = db.Column(db.String(100), default="")
    topic = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=utcnow)
    chunks = db.relationship("Chunk", backref="document", **CASCADE)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "original_name": self.original_name, "mime": self.mime,
                "size": self.size, "pages": self.pages, "status": self.status, "progress": self.progress,
                "error": self.error, "warnings": self.warnings or [], "subject": self.subject,
                "topic": self.topic, "created_at": iso(self.created_at)}


class Chunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("document.id", ondelete="CASCADE"), index=True)
    user_id = _uid()
    page = db.Column(db.Integer, default=1)
    heading = db.Column(db.String(200), default="")
    idx = db.Column(db.Integer, default=0)
    text = db.Column(db.Text)
    ocr = db.Column(db.Boolean, default=False)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    title = db.Column(db.String(200))
    kind = db.Column(db.String(30), default="notes")
    content = db.Column(db.Text)
    subject = db.Column(db.String(100), default="")
    sources = db.Column(db.JSON, default=list)
    bookmarks = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self, full=True):
        d = {"id": self.id, "title": self.title, "kind": self.kind, "subject": self.subject,
             "sources": self.sources or [], "bookmarks": self.bookmarks or [], "updated_at": iso(self.updated_at)}
        if full:
            d["content"] = self.content
        return d


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    title = db.Column(db.String(200), default="New conversation")
    doc_ids = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)
    messages = db.relationship("Message", backref="conversation", order_by="Message.id", **CASCADE)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "doc_ids": self.doc_ids or [], "updated_at": iso(self.updated_at)}


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversation.id", ondelete="CASCADE"), index=True)
    role = db.Column(db.String(12))
    content = db.Column(db.Text)
    sources = db.Column(db.JSON, default=list)
    saved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "role": self.role, "content": self.content, "sources": self.sources or [],
                "saved": self.saved, "created_at": iso(self.created_at)}


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    title = db.Column(db.String(200))
    subject = db.Column(db.String(100), default="")
    category = db.Column(db.String(60), default="")
    mode = db.Column(db.String(12), default="practice")
    difficulty = db.Column(db.String(20), default="medium")
    time_limit = db.Column(db.Integer, default=0)  # minutes
    questions = db.Column(db.JSON, default=list)   # includes answers; never sent raw to client
    created_at = db.Column(db.DateTime, default=utcnow)
    attempts = db.relationship("QuizAttempt", backref="quiz", **CASCADE)


class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.id", ondelete="CASCADE"), index=True)
    user_id = _uid()
    score = db.Column(db.Float, default=0)
    total = db.Column(db.Integer, default=0)
    answers = db.Column(db.JSON, default=dict)
    results = db.Column(db.JSON, default=list)
    topic_stats = db.Column(db.JSON, default=dict)
    duration = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)


class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    front = db.Column(db.Text)
    back = db.Column(db.Text)
    topic = db.Column(db.String(100), default="")
    source = db.Column(db.String(200), default="")
    bookmarked = db.Column(db.Boolean, default=False)
    ease = db.Column(db.Float, default=2.5)
    interval = db.Column(db.Integer, default=0)
    reps = db.Column(db.Integer, default=0)
    due = db.Column(db.Date, default=lambda: datetime.utcnow().date(), index=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "front": self.front, "back": self.back, "topic": self.topic, "source": self.source,
                "bookmarked": self.bookmarked, "interval": self.interval, "reps": self.reps, "due": iso(self.due)}


class FlashcardReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    card_id = db.Column(db.Integer, db.ForeignKey("flashcard.id", ondelete="CASCADE"), index=True)
    rating = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=utcnow)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    name = db.Column(db.String(100))
    exam_date = db.Column(db.Date)
    daily_goal_min = db.Column(db.Integer, default=60)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "exam_date": iso(self.exam_date), "daily_goal_min": self.daily_goal_min}


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    title = db.Column(db.String(200))
    subject = db.Column(db.String(100), default="")
    minutes = db.Column(db.Integer, default=30)
    due = db.Column(db.Date)
    done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "subject": self.subject, "minutes": self.minutes,
                "due": iso(self.due), "done": self.done}


class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    kind = db.Column(db.String(30))
    minutes = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)


class AIUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = _uid()
    feature = db.Column(db.String(40))
    model = db.Column(db.String(80))
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)
