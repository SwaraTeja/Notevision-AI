"""SQLite persistence layer for NoteVision AI (documents, pages, summaries, quizzes, flashcards, activity)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

import config


class Database:
    def __init__(self, path: Path | str = config.DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    # ------------------------------------------------------------------ core
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self._conn() as c:
            c.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        with self._conn() as c:
            return c.execute(sql, tuple(params)).lastrowid

    # ------------------------------------------------------------- documents
    def add_document(self, title, subject, filename, stored_path, file_type,
                     page_count, status="Ready", ocr_confidence=None, is_demo=False) -> int:
        return self.execute(
            """INSERT INTO documents(title,subject,filename,stored_path,file_type,page_count,status,ocr_confidence,is_demo)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (title, subject, filename, stored_path, file_type, page_count, status, ocr_confidence, int(is_demo)))

    def add_pages(self, doc_id: int, pages: list[dict]) -> None:
        with self._conn() as c:
            c.executemany(
                "INSERT INTO pages(doc_id,page_no,text,method,confidence) VALUES(?,?,?,?,?)",
                [(doc_id, p["page_no"], p["text"], p.get("method"), p.get("confidence")) for p in pages])

    def list_documents(self, search: str = "", subject: str | None = None) -> list[dict]:
        sql = """SELECT d.*, (SELECT COALESCE(SUM(LENGTH(text)),0) FROM pages p WHERE p.doc_id=d.id) AS chars
                 FROM documents d WHERE 1=1"""
        params: list[Any] = []
        if subject and subject != "All":
            sql += " AND d.subject = ?"
            params.append(subject)
        if search.strip():
            sql += """ AND (d.title LIKE ? OR d.subject LIKE ? OR d.id IN
                       (SELECT doc_id FROM pages WHERE text LIKE ?))"""
            like = f"%{search.strip()}%"
            params += [like, like, like]
        sql += " ORDER BY d.created_at DESC, d.id DESC"
        return self.query(sql, params)

    def get_document(self, doc_id: int) -> dict | None:
        return self.one("SELECT * FROM documents WHERE id=?", (doc_id,))

    def get_pages(self, doc_id: int) -> list[dict]:
        return self.query("SELECT * FROM pages WHERE doc_id=? ORDER BY page_no", (doc_id,))

    def get_full_text(self, doc_id: int) -> str:
        return "\n\n".join(p["text"] for p in self.get_pages(doc_id) if p["text"].strip())

    def update_page_text(self, page_id: int, text: str) -> None:
        self.execute("UPDATE pages SET text=?, edited=1 WHERE id=?", (text, page_id))

    def update_document_status(self, doc_id: int, status: str) -> None:
        self.execute("UPDATE documents SET status=? WHERE id=?", (status, doc_id))

    def subjects_in_use(self) -> list[str]:
        return [r["subject"] for r in self.query("SELECT DISTINCT subject FROM documents ORDER BY subject")]

    def delete_document(self, doc_id: int) -> None:
        """Deletes the document and (through ON DELETE CASCADE) all material generated from it."""
        self.execute("DELETE FROM documents WHERE id=?", (doc_id,))

    # ------------------------------------------------------------- summaries
    def save_summary(self, doc_id: int, mode: str, content: str) -> int:
        return self.execute("INSERT INTO summaries(doc_id,mode,content) VALUES(?,?,?)", (doc_id, mode, content))

    def latest_summary(self, doc_id: int, mode: str) -> dict | None:
        return self.one("SELECT * FROM summaries WHERE doc_id=? AND mode=? ORDER BY id DESC LIMIT 1", (doc_id, mode))

    # ----------------------------------------------------------------- quizzes
    def save_quiz(self, doc_id: int, questions: list[dict]) -> int:
        with self._conn() as c:
            quiz_id = c.execute("INSERT INTO quizzes(doc_id,num_questions) VALUES(?,?)",
                                (doc_id, len(questions))).lastrowid
            c.executemany(
                """INSERT INTO quiz_questions(quiz_id,position,question,options,answer_index,explanation,qtype,topic)
                   VALUES(?,?,?,?,?,?,?,?)""",
                [(quiz_id, i, q["question"], json.dumps(q["options"]), q["answer_index"],
                  q.get("explanation", ""), q.get("qtype", ""), q.get("topic", ""))
                 for i, q in enumerate(questions)])
        return quiz_id

    def get_quiz(self, quiz_id: int) -> dict | None:
        quiz = self.one("SELECT * FROM quizzes WHERE id=?", (quiz_id,))
        if not quiz:
            return None
        rows = self.query("SELECT * FROM quiz_questions WHERE quiz_id=? ORDER BY position", (quiz_id,))
        for r in rows:
            r["options"] = json.loads(r["options"])
        quiz["questions"] = rows
        return quiz

    def save_attempt(self, quiz_id: int, doc_id: int, score: int, total: int, answers: dict) -> int:
        pct = round(100.0 * score / total, 1) if total else 0.0
        return self.execute(
            "INSERT INTO quiz_attempts(quiz_id,doc_id,score,total,percent,answers) VALUES(?,?,?,?,?,?)",
            (quiz_id, doc_id, score, total, pct, json.dumps(answers)))

    def list_attempts(self, doc_id: int | None = None) -> list[dict]:
        sql = """SELECT a.*, d.title, d.subject FROM quiz_attempts a JOIN documents d ON d.id=a.doc_id"""
        params: list[Any] = []
        if doc_id:
            sql += " WHERE a.doc_id=?"
            params.append(doc_id)
        return self.query(sql + " ORDER BY a.created_at DESC, a.id DESC", params)

    # -------------------------------------------------------------- flashcards
    def replace_flashcards(self, doc_id: int, cards: list[dict]) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM flashcards WHERE doc_id=?", (doc_id,))
            c.executemany("INSERT INTO flashcards(doc_id,front,back) VALUES(?,?,?)",
                          [(doc_id, k["front"], k["back"]) for k in cards])

    def get_flashcards(self, doc_id: int) -> list[dict]:
        return self.query("SELECT * FROM flashcards WHERE doc_id=? ORDER BY id", (doc_id,))

    def set_flashcard_status(self, card_id: int, status: str) -> None:
        self.execute("""UPDATE flashcards SET status=?, reviews=reviews+1,
                        last_reviewed=datetime('now','localtime') WHERE id=?""", (status, card_id))

    # ---------------------------------------------------------------- activity
    def log_activity(self, kind: str, doc_id: int | None = None, detail: str = "") -> None:
        doc = self.get_document(doc_id) if doc_id else None
        self.execute("INSERT INTO activity(doc_id,subject,kind,detail) VALUES(?,?,?,?)",
                     (doc_id, doc["subject"] if doc else None, kind, detail))

    def recent_activity(self, limit: int = 8) -> list[dict]:
        return self.query("""SELECT a.*, d.title FROM activity a LEFT JOIN documents d ON d.id=a.doc_id
                             ORDER BY a.created_at DESC, a.id DESC LIMIT ?""", (limit,))
