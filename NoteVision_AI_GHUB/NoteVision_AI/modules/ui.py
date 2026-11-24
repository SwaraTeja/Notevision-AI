"""Shared UI helpers: CSS injection, headers, cards, navigation, document picker."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

import config

PAGES = [  # (label, material icon)
    ("Dashboard", ":material/space_dashboard:"),
    ("Upload Notes", ":material/upload_file:"),
    ("My Library", ":material/folder_open:"),
    ("Notes Analyzer", ":material/document_scanner:"),
    ("Smart Summarizer", ":material/auto_awesome:"),
    ("Quiz Generator", ":material/quiz:"),
    ("Flashcards", ":material/style:"),
    ("Ask My Notes", ":material/forum:"),
    ("Study Analytics", ":material/insights:"),
]

# Sidebar sections (same pages, just grouped so the menu is easier to scan).
NAV_GROUPS = [
    ("Get started", ["Dashboard", "Upload Notes", "My Library"]),
    ("Study tools", ["Notes Analyzer", "Smart Summarizer", "Quiz Generator", "Flashcards", "Ask My Notes"]),
    ("My progress", ["Study Analytics"]),
]

# Emoji tile + one-line tip shown in each page header (purely visual helpers).
PAGE_META = {
    "Upload notes": ("📤", "Bright, flat photos give the cleanest text."),
    "My library": ("📚", "Use the icons on a card to jump straight to a summary, quiz or flashcards."),
    "Notes analyzer": ("🔍", "Fix any misread words before you generate study material."),
    "Smart summarizer": ("✨", "Exam revision notes are handy the night before a test."),
    "Quiz generator": ("🧠", "Retake a quiz after revising to see your score improve."),
    "Flashcards": ("🗂️", "Mark cards honestly: the “Need revision” filter brings them back."),
    "Ask my notes": ("💬", "Short, specific questions find the best match in your notes."),
    "Study analytics": ("📈", "Check “Most-missed topics” to decide what to revise next."),
}

STUDY_TIPS = [
    "Short, regular sessions beat one long cram. Try 25 minutes, then a 5-minute break.",
    "Test yourself before re-reading. Quizzes and flashcards make memory stronger.",
    "Explain a topic in your own words. If you get stuck, that is what to revise.",
    "Revise a topic again after a day, then after a week, so it sticks.",
    "Fix OCR mistakes first. Clean notes make better summaries and quizzes.",
]


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def inject_css() -> None:
    st.markdown(f"<style>{config.CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def logo_svg(size: int = 40) -> str:
    """Inline logo so it stays sharp at any size and needs no extra file serving."""
    try:
        svg = config.LOGO_PATH.read_text(encoding="utf-8")
    except OSError:
        return '<div class="nv-mark">N</div>'
    return svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)


def brand_html() -> str:
    return (f'<div class="nv-brand">{logo_svg(42)}<div><b>NoteVision <span class="ai">AI</span></b>'
            '<small>Learn smarter from your notes</small></div></div>')


def nav_label(text: str) -> None:
    st.markdown(f'<div class="nv-nav-label">{esc(text)}</div>', unsafe_allow_html=True)


def greeting() -> str:
    h = datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def study_tip() -> str:
    return STUDY_TIPS[datetime.now().timetuple().tm_yday % len(STUDY_TIPS)]


def goto(page: str, doc_id: int | None = None) -> None:
    """on_click callback: switch page (and optionally the active document)."""
    st.session_state["page"] = page
    if doc_id is not None:
        st.session_state["active_doc_id"] = doc_id


def page_header(title: str, subtitle: str) -> None:
    icon, tip = PAGE_META.get(title, ("📝", ""))
    tip_html = f'<div class="nv-tip"><span>💡</span>{esc(tip)}</div>' if tip else ""
    st.markdown(f'<div class="nv-head"><div class="nv-head-ico">{icon}</div><div class="nv-head-txt">'
                f'<h1>{esc(title)}</h1><p>{esc(subtitle)}</p>{tip_html}</div></div>', unsafe_allow_html=True)


def kpi(label: str, value, hint: str = "", icon: str = "", tone: str = "") -> str:
    ico = f'<div class="ico {tone}">{icon}</div>' if icon else ""
    return (f'<div class="nv-kpi">{ico}<div class="body"><div class="l">{esc(label)}</div>'
            f'<div class="v">{esc(value)}</div><div class="h">{esc(hint)}</div></div></div>')


def chip(text: str, tone: str = "") -> str:
    return f'<span class="nv-chip {tone}">{esc(text)}</span>'


def status_chip(status: str) -> str:
    return chip(status, {"Ready": "good", "Needs review": "warn"}.get(status, "gray"))


def empty_state(title: str, text: str, icon: str = "🌱") -> None:
    st.markdown(f'<div class="nv-empty"><div class="eico">{icon}</div><b>{esc(title)}</b>{esc(text)}</div>',
                unsafe_allow_html=True)


def fmt_date(s: str | None) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y, %H:%M")
    except Exception:
        return s or ""


def doc_picker(db, key: str, label: str = "Choose a document", allow_all: bool = False):
    """Select a document; remembers the choice across pages. Returns the document dict (or None)."""
    docs = db.list_documents()
    if not docs:
        empty_state("No notes yet", "Upload your first notes to use this feature.", "📂")
        st.button("Upload notes", type="primary", on_click=goto, args=("Upload Notes",), key=f"{key}_go_upload")
        return None
    ids = [d["id"] for d in docs]
    active = st.session_state.get("active_doc_id")
    index = ids.index(active) if active in ids else 0
    choice = st.selectbox(label, docs, index=index, key=f"{key}_pick",
                          format_func=lambda d: f"{d['title']}  ·  {d['subject']}")
    st.session_state["active_doc_id"] = choice["id"]
    return choice


def doc_text(db, doc_id: int) -> str:
    return db.get_full_text(doc_id)


PALETTE = ["#4F46E5", "#7C3AED", "#0EA5E9", "#12A150", "#F59E0B", "#EC4899"]
ACTIVITY_LABELS = {"upload": "Added notes", "summary": "Generated a summary", "quiz": "Completed a quiz",
                   "flashcard": "Reviewed a flashcard", "question": "Asked a question"}
ACTIVITY_ICONS = {"upload": "📤", "summary": "✨", "quiz": "🧠", "flashcard": "🗂️", "question": "💬"}
