PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL,
    subject        TEXT NOT NULL DEFAULT 'General',
    filename       TEXT,
    stored_path    TEXT,
    file_type      TEXT,
    page_count     INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'Ready',
    ocr_confidence REAL,
    is_demo        INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS pages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_no    INTEGER NOT NULL,
    text       TEXT NOT NULL DEFAULT '',
    method     TEXT,
    confidence REAL,
    edited     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS summaries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    mode       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS quizzes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id        INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    num_questions INTEGER NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id      INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    question     TEXT NOT NULL,
    options      TEXT NOT NULL,
    answer_index INTEGER NOT NULL,
    explanation  TEXT,
    qtype        TEXT,
    topic        TEXT
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id    INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    score      INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    percent    REAL NOT NULL,
    answers    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS flashcards (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id        INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    front         TEXT NOT NULL,
    back          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'new',
    reviews       INTEGER NOT NULL DEFAULT 0,
    last_reviewed TEXT
);

CREATE TABLE IF NOT EXISTS activity (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id     INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    subject    TEXT,
    kind       TEXT NOT NULL,
    detail     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_pages_doc ON pages(doc_id);
CREATE INDEX IF NOT EXISTS idx_cards_doc ON flashcards(doc_id);
CREATE INDEX IF NOT EXISTS idx_activity_time ON activity(created_at);
