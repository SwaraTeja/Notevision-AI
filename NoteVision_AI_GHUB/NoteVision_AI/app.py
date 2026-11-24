"""NoteVision AI - entry point.  Run with:  streamlit run app.py"""
import streamlit as st

import config
from database.db_manager import Database
from modules import ocr_engine, text_preprocessing
from modules.ui import NAV_GROUPS, PAGES, brand_html, esc, goto, inject_css, nav_label, study_tip
from views import (analyzer, analytics_page, ask_notes, dashboard, flashcards, library, quiz, summarizer_page,
                   upload)

st.set_page_config(page_title="NoteVision AI", page_icon=str(config.FAVICON_PATH), layout="wide",
                   initial_sidebar_state="expanded")

ROUTES = {
    "Dashboard": dashboard, "Upload Notes": upload, "My Library": library, "Notes Analyzer": analyzer,
    "Smart Summarizer": summarizer_page, "Quiz Generator": quiz, "Flashcards": flashcards,
    "Ask My Notes": ask_notes, "Study Analytics": analytics_page,
}


@st.cache_resource
def get_db() -> Database:
    return Database(config.DB_PATH)


@st.cache_resource
def warm_up() -> dict:
    return text_preprocessing.ensure_resources()      # downloads NLTK data once if missing


inject_css()
db = get_db()
resources = warm_up()
st.session_state.setdefault("page", "Dashboard")

ICONS = dict(PAGES)

with st.sidebar:
    st.markdown(brand_html(), unsafe_allow_html=True)
    for group, labels in NAV_GROUPS:
        nav_label(group)
        for label in labels:
            st.button(label, icon=ICONS[label], key=f"nav_{label}", width="stretch",
                      type="primary" if st.session_state["page"] == label else "secondary",
                      on_click=goto, args=(label,))
    st.markdown(f'<div class="nv-tipcard"><b>💡 Study tip</b>{esc(study_tip())}</div>', unsafe_allow_html=True)
    st.divider()
    ok = ocr_engine.tesseract_available()
    st.markdown(f'<div class="nv-status"><span class="dot {"on" if ok else "off"}"></span>'
                f'OCR engine: {"ready" if ok else "Tesseract not found"}</div>', unsafe_allow_html=True)
    with st.expander("About & limitations"):
        st.markdown(
            "NoteVision AI uses OpenCV + Tesseract for OCR and lightweight NLP (TF-IDF, NLTK) for summaries, "
            "quizzes, flashcards and question answering. Everything runs on your computer.\n\n"
            "**Limits:** printed text is read reliably; handwriting depends on how clear it is, so always "
            "check and correct the extracted text. Summaries and answers only reuse sentences from your notes.")

if not ocr_engine.tesseract_available() and st.session_state["page"] == "Upload Notes":
    st.error("Tesseract OCR was not found. Install it (see README) or set the TESSERACT_CMD environment variable.")

ROUTES[st.session_state["page"]].render(db)
