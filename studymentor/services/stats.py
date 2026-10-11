from collections import defaultdict
from datetime import datetime, timedelta
from ..models import QuizAttempt, Quiz, StudySession


def topic_perf(uid):
    agg = defaultdict(lambda: [0.0, 0])
    for a in QuizAttempt.query.filter_by(user_id=uid).all():
        for t, (c, n) in (a.topic_stats or {}).items():
            agg[t][0] += c
            agg[t][1] += n
    return {t: round(100 * c / n) for t, (c, n) in agg.items() if n}


def weak_topics(uid, limit=5):
    perf = topic_perf(uid)
    return [{"topic": t, "accuracy": p} for t, p in sorted(perf.items(), key=lambda x: x[1]) if p < 70][:limit]


def subject_perf(uid):
    agg = defaultdict(lambda: [0.0, 0])
    for a in QuizAttempt.query.filter_by(user_id=uid).all():
        k = (a.quiz.subject or a.quiz.category or "General") if a.quiz else "General"
        agg[k][0] += a.score
        agg[k][1] += a.total
    return {k: round(100 * c / n) for k, (c, n) in agg.items() if n}


def weekly_minutes(uid):
    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    since = datetime.combine(days[0], datetime.min.time())
    tot = defaultdict(float)
    for s in StudySession.query.filter(StudySession.user_id == uid, StudySession.created_at >= since):
        tot[s.created_at.date()] += s.minutes
    return {"labels": [d.strftime("%a") for d in days], "minutes": [round(tot[d], 1) for d in days]}
