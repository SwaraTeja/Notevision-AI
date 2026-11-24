from pathlib import Path

import streamlit as st

import config
from modules import pipeline, ppt_reader
from modules.ocr_engine import confidence_label
from modules.ui import esc, goto, page_header, status_chip


def _subject_input(key: str) -> str:
    choice = st.selectbox("Subject", config.SUBJECTS + ["Other…"], key=f"{key}_subj")
    if choice == "Other…":
        return st.text_input("Subject name", key=f"{key}_subj_other").strip() or "General"
    return choice


def _result_card(db):
    r = st.session_state.get("last_upload")
    if not r:
        return
    doc = db.get_document(r["doc_id"])
    if not doc:
        return
    st.success(f"“{doc['title']}” was added to your library.")
    conf = r.get("confidence")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pages", r["pages"])
    c2.metric("Text confidence", f"{conf:.0f}% ({confidence_label(conf)})" if conf is not None else "typed")
    c3.markdown(f"**Status**<br>{status_chip(doc['status'])}", unsafe_allow_html=True)
    if doc["status"] == "Needs review":
        st.warning("The text was hard to read, which is common with handwriting or blurry photos. "
                   "Open the Notes Analyzer and correct the extracted text before generating summaries or quizzes.")
    st.button("Review and correct extracted text", type="primary", icon=":material/document_scanner:",
              on_click=goto, args=("Notes Analyzer", doc["id"]), key="goto_review")


def render(db):
    page_header("Upload notes", "Add a photo, scan, PDF or PowerPoint of your notes. The text is extracted and saved to your library.")
    tab_file, tab_text = st.tabs(["Upload a file", "Type or paste notes"])

    with tab_file:
        left, right = st.columns([3, 2], gap="large")
        with left:
            up = st.file_uploader("Drag and drop your notes here", type=["jpg", "jpeg", "png", "pdf", "pptx", "ppt"],
                                  help=f"JPG, JPEG, PNG, PDF or PowerPoint (PPTX), up to {config.MAX_FILE_MB} MB")
            if up is not None:
                data = up.getvalue()
                st.caption(f"{up.name} · {len(data) / 1024:.0f} KB")
                title = st.text_input("Document title", value=Path(up.name).stem, key=f"title_{up.name}")
                subject = _subject_input(f"up_{up.name}")
                go = st.button("Upload and analyze", type="primary", icon=":material/bolt:", width="stretch")
                if go:
                    bar, msg = st.progress(0.0), st.empty()

                    def progress(frac, text):
                        bar.progress(min(frac, 1.0))
                        msg.caption(text)

                    try:
                        st.session_state["last_upload"] = pipeline.process_upload(db, data, up.name, title, subject, progress)
                    except pipeline.ProcessingError as e:
                        st.session_state.pop("last_upload", None)
                        bar.empty(); msg.empty()
                        st.error(str(e))
                    except Exception as e:  # unexpected: keep the app alive and explain
                        st.session_state.pop("last_upload", None)
                        bar.empty(); msg.empty()
                        st.error(f"Something went wrong while processing this file ({type(e).__name__}). Try another file.")
                    else:
                        bar.empty(); msg.empty()
            _result_card(db)
        with right:
            if up is not None:
                st.markdown("**Preview**")
                if up.name.lower().endswith(".pdf"):
                    png = pipeline.pdf_first_page_png(up.getvalue())
                    st.image(png, caption="First page", width="stretch") if png else st.warning("Preview unavailable for this PDF.")
                elif up.name.lower().endswith((".pptx", ".ppt")):
                    outline = ppt_reader.first_slides_outline(up.getvalue(), Path(up.name).suffix.lower())
                    if outline:
                        st.caption("First slides")
                        for n, line in outline:
                            st.markdown(f"**{n}.** {line}")
                    else:
                        st.info("PowerPoint file ready. Slide text, tables and speaker notes will be extracted.")
                else:
                    st.image(up.getvalue(), width="stretch")
            else:
                st.markdown('<div class="nv-card"><h4>For the best results</h4>'
                            '<p class="nv-muted">Use a bright, even light and keep the page flat.<br>'
                            'Fill the frame with the page and avoid shadows.<br>'
                            'Printed text and neat handwriting work best; always review the extracted text.<br>'
                            'Digital PDFs and PowerPoint slides keep their original text with no OCR errors.</p></div>', unsafe_allow_html=True)

    with tab_text:
        title = st.text_input("Document title", key="typed_title")
        subject = _subject_input("typed")
        text = st.text_area("Your notes", height=240, key="typed_notes", placeholder="Paste or type your notes here…")
        if st.button("Save notes", type="primary", icon=":material/save:"):
            try:
                doc_id = pipeline.create_text_document(db, title.strip() or "Untitled notes", subject, text)
                st.session_state["last_upload"] = {"doc_id": doc_id, "pages": 1, "confidence": None, "status": "Ready"}
                st.rerun()
            except pipeline.ProcessingError as e:
                st.error(str(e))

    with st.expander("Try it with demo notes"):
        st.caption("Adds a clearly labelled sample document (Machine Learning basics) so you can explore every feature. "
                   "All results are still generated by the real pipeline. Delete it any time from My Library.")
        if st.button("Load demo notes", icon=":material/science:"):
            demo = config.DEMO_NOTES_PATH.read_text(encoding="utf-8")
            doc_id = pipeline.create_text_document(db, "[Demo] Machine Learning Basics", "Computer Science", demo, demo=True)
            st.session_state["last_upload"] = {"doc_id": doc_id, "pages": 1, "confidence": None, "status": "Ready"}
            st.rerun()
