import streamlit as st

from modules import exporter, summarizer
from modules.ui import doc_picker, fmt_date, page_header

DESCRIPTIONS = {
    "quick": "A short summary with the most important ideas.",
    "detailed": "A structured summary with key points, definitions and key terms.",
    "exam": "Definitions, key concepts, revision points and likely exam questions.",
}


def render(db):
    page_header("Smart summarizer", "Summaries are built only from sentences in your own notes. Nothing is added or invented.")
    doc = doc_picker(db, "sm")
    if not doc:
        return
    mode = st.radio("Summary type", list(summarizer.MODES), format_func=summarizer.MODES.get, horizontal=True, key="sm_mode")
    st.caption(DESCRIPTIONS[mode])

    if st.button("Generate summary", type="primary", icon=":material/auto_awesome:"):
        text = db.get_full_text(doc["id"])
        try:
            with st.spinner("Reading your notes…"):
                content = summarizer.summarize(text, mode, doc["title"])
            db.save_summary(doc["id"], mode, content)
            db.log_activity("summary", doc["id"], summarizer.MODES[mode])
        except ValueError as e:
            st.error(str(e))

    saved = db.latest_summary(doc["id"], mode)
    if not saved:
        st.info("No summary of this type yet. Press Generate summary.")
        return
    st.caption(f"Generated {fmt_date(saved['created_at'])}")
    with st.container(border=True):
        st.markdown(saved["content"])
    name = f"{doc['title']} - {summarizer.MODES[mode]}"
    st.download_button("Download TXT", exporter.markdown_to_text(saved["content"]), file_name=f"{name}.txt",
                       mime="text/plain", icon=":material/description:")
