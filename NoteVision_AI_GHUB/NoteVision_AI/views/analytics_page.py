import pandas as pd
import streamlit as st

from modules import analytics
from modules.ui import ACTIVITY_LABELS, PALETTE, empty_state, fmt_date, kpi, page_header


def render(db):
    page_header("Study analytics", "Your real study activity: nothing here is estimated or made up.")
    o = analytics.overview(db)
    if o["documents"] == 0:
        empty_state("No data yet", "Upload notes and try a quiz to see your analytics.")
        return
    items = [("Documents", o["documents"], "", "📚", ""), ("Summaries", o["summaries"], "generated", "✨", "amber"),
             ("Quizzes", o["quizzes"], "attempted", "🧠", "violet"),
             ("Average score", f"{o['avg_score']:.0f}%" if o["avg_score"] is not None else "–", "", "🎯", "green"),
             ("Cards reviewed", o["cards_reviewed"], f"of {o['cards_total']}", "🗂️", "sky"),
             ("Questions asked", o["questions"], "", "💬", "pink")]
    for col, (l, v, h, ic, tn) in zip(st.columns(6), items):
        col.markdown(kpi(l, v, h, ic, tn), unsafe_allow_html=True)
    st.write("")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Quiz performance over time")
        hist = analytics.quiz_history(db)
        if hist.empty:
            empty_state("No quizzes yet", "Complete a quiz to see your score trend.")
        else:
            hist["attempt"] = range(1, len(hist) + 1)
            st.line_chart(hist.set_index("attempt")["percent"], color="#4F46E5", x_label="Attempt", y_label="Score %", height=300)
    with right:
        st.markdown("#### Activity by subject")
        sa = analytics.subject_activity(db)
        if sa.empty:
            empty_state("No activity yet", "Study activity is grouped by subject here.")
        else:
            sa["activity"] = sa["kind"].map(ACTIVITY_LABELS).fillna(sa["kind"])
            pv = sa.pivot_table(index="subject", columns="activity", values="n", aggfunc="sum", fill_value=0)
            st.bar_chart(pv, color=PALETTE[:len(pv.columns)], y_label="Actions", height=300)

    l2, r2 = st.columns(2)
    with l2:
        st.markdown("#### Flashcard progress")
        if o["cards_total"] == 0:
            empty_state("No flashcards yet", "Create a deck to track your revision.")
        else:
            new = o["cards_total"] - o["cards_known"] - o["cards_revise"]
            df = pd.DataFrame({"Known": [o["cards_known"]], "Need revision": [o["cards_revise"]], "Not reviewed": [new]}, index=["Cards"])
            st.bar_chart(df, horizontal=True, color=["#12A150", "#F59E0B", "#C9CCE8"], height=160)
    with r2:
        st.markdown("#### Insights")
        for tip in analytics.insights(db):
            st.markdown(f"- {tip}")
        wt = analytics.weak_topics(db)
        if wt:
            st.markdown("**Most-missed topics**")
            for t, n in wt:
                st.markdown(f"- {t} (missed {n}×)")

    st.markdown("#### Quiz attempts")
    attempts = db.list_attempts()
    if attempts:
        df = pd.DataFrame(attempts)[["created_at", "title", "subject", "score", "total", "percent"]]
        df.columns = ["When", "Document", "Subject", "Score", "Out of", "Percent"]
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.caption("No attempts recorded.")
