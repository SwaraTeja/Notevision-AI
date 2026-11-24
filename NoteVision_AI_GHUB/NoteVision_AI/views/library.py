import streamlit as st

from modules import pipeline
from modules.ui import chip, empty_state, esc, fmt_date, goto, page_header, status_chip


def _delete(db, doc):
    pipeline.delete_document_files(doc["id"], doc.get("stored_path"))
    db.delete_document(doc["id"])
    if st.session_state.get("active_doc_id") == doc["id"]:
        st.session_state.pop("active_doc_id", None)
    st.session_state.pop("last_upload", None)


def render(db):
    page_header("My library", "All your notes in one place. Search them, open them, or turn them into study material.")
    c1, c2 = st.columns([3, 1])
    search = c1.text_input("Search", placeholder="Search by title, subject or words inside your notes", label_visibility="collapsed")
    subjects = ["All"] + db.subjects_in_use()
    subject = c2.selectbox("Subject", subjects, label_visibility="collapsed")
    docs = db.list_documents(search, subject)

    if not db.list_documents():
        empty_state("Your library is empty", "Upload notes to start building your library.", "📚")
        st.button("Upload notes", type="primary", on_click=goto, args=("Upload Notes",))
        return
    if not docs:
        empty_state("No matches", "Try a different search or choose another subject.", "🔎")
        return

    st.caption(f"{len(docs)} document(s)")
    cols = st.columns(3, gap="medium")
    for i, d in enumerate(docs):
        with cols[i % 3]:
            conf = f" · OCR {d['ocr_confidence']:.0f}%" if d["ocr_confidence"] is not None else ""
            demo = chip("Demo", "gray") + " " if d["is_demo"] else ""
            tile = {"pdf": "📕", "pptx": "📊", "text": "📝"}.get(d["file_type"], "🖼️")
            st.markdown(
                f'<div class="nv-card"><div class="nv-doc"><div class="tile">{tile}</div><div class="tt">'
                f'<div style="display:flex;justify-content:space-between;gap:.5rem;align-items:start">'
                f'<h4>{esc(d["title"])}</h4>{status_chip(d["status"])}</div>'
                f'<div style="margin:.35rem 0">{demo}{chip(d["subject"])}</div>'
                f'<div class="nv-muted">{d["page_count"]} page(s) · {d["chars"]:,} characters{esc(conf)}<br>Added {fmt_date(d["created_at"])}</div>'
                f'</div></div></div>',
                unsafe_allow_html=True)
            a, b, c, e, f = st.columns([2.2, 1, 1, 1, 1])
            a.button("Open", key=f"open_{d['id']}", type="primary", width="stretch", on_click=goto, args=("Notes Analyzer", d["id"]))
            b.button(":material/auto_awesome:", key=f"sum_{d['id']}", help="Generate summary", width="stretch", on_click=goto, args=("Smart Summarizer", d["id"]))
            c.button(":material/quiz:", key=f"quiz_{d['id']}", help="Generate quiz", width="stretch", on_click=goto, args=("Quiz Generator", d["id"]))
            e.button(":material/style:", key=f"fc_{d['id']}", help="Create flashcards", width="stretch", on_click=goto, args=("Flashcards", d["id"]))
            with f.popover(":material/delete:", help="Delete document"):
                st.markdown(f"Delete **{d['title']}** and everything generated from it? This cannot be undone.")
                st.button("Delete permanently", key=f"del_{d['id']}", type="primary", on_click=_delete, args=(db, d))
            st.write("")
