"""Study analytics computed only from real stored activity."""
from __future__ import annotations

import json
from collections import defaultdict

import pandas as pd

from database.db_manager import Database


def overview(db: Database) -> dict:
    one = lambda sql: (db.one(sql) or {}).get("n", 0) or 0
    attempts = one("SELECT COUNT(*) n FROM quiz_attempts")
    return {
        "documents": one("SELECT COUNT(*) n FROM documents"),
        "pages": one("SELECT COALESCE(SUM(page_count),0) n FROM documents"),
        "summaries": one("SELECT COUNT(*) n FROM summaries"),
        "quizzes": attempts,
        "avg_score": round((db.one("SELECT AVG(percent) n FROM quiz_attempts") or {}).get("n") or 0, 1) if attempts else None,
        "cards_total": one("SELECT COUNT(*) n FROM flashcards"),
        "cards_reviewed": one("SELECT COUNT(*) n FROM flashcards WHERE reviews>0"),
        "cards_known": one("SELECT COUNT(*) n FROM flashcards WHERE status='known'"),
        "cards_revise": one("SELECT COUNT(*) n FROM flashcards WHERE status='revise'"),
        "questions": one("SELECT COUNT(*) n FROM activity WHERE kind='question'"),
    }


def activity_by_day(db: Database, days: int = 14) -> pd.DataFrame:
    rows = db.query(f"""SELECT date(created_at) AS day, kind, COUNT(*) AS n FROM activity
                        WHERE date(created_at) >= date('now','localtime','-{int(days) - 1} day')
                        GROUP BY day, kind""")
    idx = pd.date_range(end=pd.Timestamp.now().normalize(), periods=days)
    df = pd.DataFrame(rows, columns=["day", "kind", "n"])
    if df.empty:
        return pd.DataFrame({"day": idx, "kind": "none", "n": 0})
    df["day"] = pd.to_datetime(df["day"])
    return df


def quiz_history(db: Database) -> pd.DataFrame:
    rows = db.list_attempts()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df.sort_values("created_at").reset_index(drop=True)


def subject_activity(db: Database) -> pd.DataFrame:
    rows = db.query("""SELECT COALESCE(subject,'Unknown') AS subject, kind, COUNT(*) AS n FROM activity
                       GROUP BY subject, kind""")
    return pd.DataFrame(rows, columns=["subject", "kind", "n"])


def weak_topics(db: Database, limit: int = 5) -> list[tuple[str, int]]:
    """Topics of questions answered wrongly across all attempts (most frequent first)."""
    miss: dict[str, int] = defaultdict(int)
    for a in db.list_attempts():
        quiz = db.get_quiz(a["quiz_id"])
        if not quiz:
            continue
        answers = json.loads(a["answers"])
        for q in quiz["questions"]:
            if answers.get(str(q["id"])) != q["answer_index"] and q.get("topic"):
                miss[q["topic"]] += 1
    return sorted(miss.items(), key=lambda x: x[1], reverse=True)[:limit]


def insights(db: Database) -> list[str]:
    o, out = overview(db), []
    hist = quiz_history(db)
    if o["documents"] == 0:
        return ["Upload your first notes to start building insights."]
    if not hist.empty:
        by_subject = hist.groupby("subject")["percent"].mean().round(1)
        if len(by_subject) > 1:
            out.append(f"Strongest subject: {by_subject.idxmax()} ({by_subject.max()}% average). "
                       f"Needs most work: {by_subject.idxmin()} ({by_subject.min()}%).")
        if len(hist) >= 2:
            delta = hist["percent"].iloc[-1] - hist["percent"].iloc[0]
            out.append(f"Your latest quiz score is {abs(delta):.0f} points {'higher' if delta >= 0 else 'lower'} than your first.")
        wt = weak_topics(db, 3)
        if wt:
            out.append("Topics you missed most often: " + ", ".join(t for t, _ in wt) + ".")
    else:
        out.append("You have not taken a quiz yet. A short 5-question quiz is a good first check.")
    if o["cards_total"]:
        out.append(f"Flashcards: {o['cards_known']} of {o['cards_total']} marked as known, {o['cards_revise']} need revision.")
    return out
