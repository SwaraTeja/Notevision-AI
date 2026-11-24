import pandas as pd
import streamlit as st

from modules import analytics
from modules.ui import (ACTIVITY_ICONS, ACTIVITY_LABELS, PALETTE, empty_state, esc, fmt_date, goto, greeting, kpi,
                        status_chip)


def render(db):
    o = analytics.overview(db)
    st.markdown(
        f'<div class="nv-hero"><span class="hi">{greeting()} 👋 Ready to study?</span><h2>Turn your notes into study material</h2>'
        '<p>Upload handwritten or printed notes. NoteVision AI reads them with computer vision, then builds '
        'summaries, quizzes and flashcards from your own content, and lets you ask questions about it.</p></div>',
        unsafe_allow_html=True)

    st.markdown(
        '<div class="nv-steps">'
        '<div class="nv-step"><div class="n">1</div><div><b>Upload</b><span>Add a photo, PDF, PowerPoint or typed notes.</span></div></div>'
        '<div class="nv-step"><div class="n">2</div><div><b>Review</b><span>Check the extracted text and fix mistakes.</span></div></div>'
        '<div class="nv-step"><div class="n">3</div><div><b>Study</b><span>Summaries, quizzes, flashcards and questions.</span></div></div>'
        '</div>', unsafe_allow_html=True)

    cols = st.columns(4)
    items = [("Documents", o["documents"], "in your library", "📚", ""),
             ("Pages processed", o["pages"], "scanned or typed", "📄", "sky"),
             ("Quizzes attempted", o["quizzes"], "completed attempts", "🧠", "violet"),
             ("Average quiz score", f"{o['avg_score']:.0f}%" if o["avg_score"] is not None else "–",
              "across all attempts" if o["avg_score"] is not None else "take a quiz to see this", "🎯", "green")]
    for col, (l, v, h, ic, tn) in zip(cols, items):
        col.markdown(kpi(l, v, h, ic, tn), unsafe_allow_html=True)

    st.markdown("#### Quick actions")
    a, b, c, d = st.columns(4)
    a.button("Upload notes", icon=":material/upload_file:", type="primary", width="stretch", on_click=goto, args=("Upload Notes",))
    b.button("Take a quiz", icon=":material/quiz:", width="stretch", on_click=goto, args=("Quiz Generator",))
    c.button("Revise flashcards", icon=":material/style:", width="stretch", on_click=goto, args=("Flashcards",))
    d.button("Ask my notes", icon=":material/forum:", width="stretch", on_click=goto, args=("Ask My Notes",))

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Study progress, last 14 days")
        df = analytics.activity_by_day(db, 14)
        if (df["n"] == 0).all() or df["kind"].eq("none").all():
            empty_state("No activity yet", "Your uploads, quizzes and revision will appear here as you study.")
        else:
            df = df.assign(activity=df["kind"].map(ACTIVITY_LABELS).fillna(df["kind"]))
            pv = df.pivot_table(index="day", columns="activity", values="n", aggfunc="sum", fill_value=0)
            pv = pv.reindex(pd.date_range(end=pd.Timestamp.now().normalize(), periods=14), fill_value=0)
            st.bar_chart(pv, color=PALETTE[:len(pv.columns)], y_label="Actions", height=300)
    with right:
        st.markdown("#### Recent documents")
        docs = db.list_documents()[:4]
        if not docs:
            empty_state("Nothing uploaded", "Add notes to see them here.")
        if docs:
            rows = "".join(
                f'<div class="nv-row"><div class="lead"><div class="tile">📄</div><div><b>{esc(dd["title"])}</b>'
                f'<div class="nv-muted">{esc(dd["subject"])} · {dd["page_count"]} page(s) · {fmt_date(dd["created_at"])}</div></div></div>'
                f'{status_chip(dd["status"])}</div>' for dd in docs)
            st.markdown(f'<div class="nv-list">{rows}</div>', unsafe_allow_html=True)

    st.markdown("#### Recent learning activity")
    acts = db.recent_activity(6)
    if not acts:
        st.caption("No activity recorded yet.")
    if acts:
        rows = "".join(
            f'<div class="nv-row"><div class="lead"><div class="tile">{ACTIVITY_ICONS.get(a_["kind"], "📝")}</div><div>'
            f'{esc(ACTIVITY_LABELS.get(a_["kind"], a_["kind"]))}'
            f'<span class="nv-muted"> · {esc(a_["title"] or "deleted document")}</span></div></div>'
            f'<span class="nv-muted">{fmt_date(a_["created_at"])}</span></div>' for a_ in acts)
        st.markdown(f'<div class="nv-list">{rows}</div>', unsafe_allow_html=True)
