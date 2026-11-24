from datetime import datetime

import streamlit as st

from modules import question_answering as qa
from modules.ui import empty_state, esc, page_header


def _bubble(m) -> str:
    body = esc(m["text"]).replace("\n- ", "\n• ").replace("\n", "<br>")
    src = ""
    for s in m.get("sources", []):
        src += (f'<div class="nv-src"><b>{esc(s["title"])}</b> · page {s["page"]} · match {s["score"]:.2f}<br>'
                f'<span style="opacity:.8">{esc(s["snippet"])}</span></div>')
    role = "user" if m["role"] == "user" else "bot"
    avatar = "🙂" if role == "user" else "🤖"
    return (f'<div class="nv-msg {role}"><div class="nv-av">{avatar}</div><div class="nv-bubble">{body}{src}'
            f'<div class="nv-time">{m["time"]}</div></div></div>')


def render(db):
    page_header("Ask my notes", "Ask a question and get an answer built from your own notes, with the source page shown.")
    docs = db.list_documents()
    if not docs:
        empty_state("No notes to ask about", "Upload notes first.")
        return
    options = [None] + docs
    scope = st.selectbox("Search in", options, format_func=lambda d: "All my documents" if d is None else d["title"], key="ask_scope")
    selected = docs if scope is None else [scope]
    index_docs = [{"id": d["id"], "title": d["title"], "pages": db.get_pages(d["id"])} for d in selected]
    index = qa.NotesIndex(index_docs)

    st.session_state.setdefault("chat", [])
    pending = None
    sample_text = "\n\n".join(db.get_full_text(d["id"]) for d in selected[:3])
    suggestions = qa.suggest_questions(sample_text, 4)
    if suggestions:
        st.caption("Suggested questions")
        cols = st.columns(len(suggestions))
        for c, q in zip(cols, suggestions):
            if c.button(q, key=f"sug_{q}", width="stretch"):
                pending = q

    typed = st.chat_input("Ask a question about your notes…")
    question = typed or pending
    now = lambda: datetime.now().strftime("%H:%M")
    if question:
        st.session_state["chat"].append({"role": "user", "text": question, "time": now()})
        res = qa.answer(index, question)
        if res["found"]:
            st.session_state["chat"].append({"role": "bot", "text": "From your notes:\n" + res["answer"],
                                             "time": now(), "sources": res["sources"]})
        else:
            st.session_state["chat"].append({"role": "bot", "time": now(), "text":
                "I could not find this in your uploaded notes, so I will not guess. Try different wording, "
                "or check that the topic is covered in the selected documents."})
        db.log_activity("question", selected[0]["id"] if len(selected) == 1 else None, question[:120])

    if not st.session_state["chat"]:
        empty_state("Ask your first question", "Try one of the suggestions above, or type your own.", "💬")
    else:
        st.markdown("".join(_bubble(m) for m in st.session_state["chat"]), unsafe_allow_html=True)
        st.button("Clear conversation", icon=":material/delete_sweep:", on_click=lambda: st.session_state.update(chat=[]))
