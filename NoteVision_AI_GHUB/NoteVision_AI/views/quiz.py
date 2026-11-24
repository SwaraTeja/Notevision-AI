import time

import streamlit as st

from modules import analytics
from modules.quiz_generator import generate_quiz
from modules.ui import doc_picker, esc, fmt_date, page_header


def _new_quiz(db, doc, n):
    questions = generate_quiz(db.get_full_text(doc["id"]), n, seed=int(time.time() * 1000) % 10_000_000)
    if not questions:
        st.error("These notes do not contain enough definitions or repeated key terms to build reliable questions. "
                 "Add more detailed notes and try again.")
        return
    if len(questions) < n:
        st.info(f"Only {len(questions)} reliable questions could be built from these notes (you asked for {n}). "
                "Longer notes allow bigger quizzes.")
    quiz_id = db.save_quiz(doc["id"], questions)
    st.session_state["quiz"] = {"quiz_id": quiz_id, "doc_id": doc["id"], "attempt": 0, "result": None}


def _retake():
    q = st.session_state["quiz"]
    q["attempt"] += 1
    q["result"] = None


def _result_view(db, quiz, state):
    r = state["result"]
    pct = r["percent"]
    tone = "#12A150" if pct >= 80 else "#D97706" if pct >= 50 else "#DC2626"
    msg = ("Strong result. You know this material well." if pct >= 80 else
           "Good start. Review the questions you missed below." if pct >= 50 else
           "This topic needs more revision. Read the summary and revise the flashcards, then retake the quiz.")
    c1, c2 = st.columns([1, 2])
    c1.markdown(f'<div class="nv-card" style="text-align:center"><div class="nv-score" style="color:{tone}">{pct:.0f}%</div>'
                f'<div class="nv-muted">{r["score"]} of {r["total"]} correct</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f"**Performance summary**\n\n{msg}")
        missed = [q["topic"] for q in quiz["questions"] if r["answers"].get(str(q["id"])) != q["answer_index"] and q["topic"]]
        if missed:
            st.markdown("**Topics to revise:** " + ", ".join(dict.fromkeys(missed)))
    a, b, _ = st.columns([1, 1.4, 2])
    a.button("Retake quiz", icon=":material/replay:", on_click=_retake, width="stretch")
    if b.button("Generate another quiz", icon=":material/autorenew:", type="primary", width="stretch"):
        doc = db.get_document(quiz["doc_id"])
        _new_quiz(db, doc, quiz["num_questions"])
        st.rerun()

    st.markdown("#### Review answers")
    for i, q in enumerate(quiz["questions"], 1):
        chosen = r["answers"].get(str(q["id"]))
        ok = chosen == q["answer_index"]
        with st.container(border=True):
            st.markdown(f"**Q{i}.** {q['question']}")
            st.markdown(f"{'✅' if ok else '❌'} Your answer: {q['options'][chosen]}")
            if not ok:
                st.markdown(f"✅ Correct answer: **{q['options'][q['answer_index']]}**")
            if q["explanation"]:
                st.caption(q["explanation"])


def render(db):
    page_header("Quiz generator", "Multiple-choice questions built from your own notes, with explanations and scoring.")
    doc = doc_picker(db, "qz")
    if not doc:
        return
    c1, c2 = st.columns([2, 1])
    n = c1.radio("Number of questions", [5, 10, 15], horizontal=True, key="qz_n")
    c2.write("")
    if c2.button("Generate quiz", type="primary", icon=":material/quiz:", width="stretch"):
        _new_quiz(db, doc, n)
        st.rerun() if st.session_state.get("quiz") else None

    state = st.session_state.get("quiz")
    if not state or state["doc_id"] != doc["id"]:
        st.info("Choose the number of questions and press Generate quiz.")
        _history(db, doc)
        return
    quiz = db.get_quiz(state["quiz_id"])
    if not quiz:
        st.session_state.pop("quiz", None)
        st.rerun()

    if state["result"]:
        _result_view(db, quiz, state)
    else:
        with st.form(f"quiz_form_{quiz['id']}_{state['attempt']}"):
            picks = {}
            for i, q in enumerate(quiz["questions"], 1):
                st.markdown(f"**Q{i}.** {q['question']}")
                picks[q["id"]] = st.radio(f"Answer {i}", range(len(q["options"])), index=None, label_visibility="collapsed",
                                          format_func=lambda k, opts=q["options"]: opts[k],
                                          key=f"q_{quiz['id']}_{state['attempt']}_{q['id']}")
                st.divider()
            submitted = st.form_submit_button("Submit quiz", type="primary", icon=":material/check_circle:")
        if submitted:
            missing = [i for i, (qid, v) in enumerate(picks.items(), 1) if v is None]
            if missing:
                st.warning("Answer every question before submitting. Unanswered: " + ", ".join(f"Q{m}" for m in missing))
            else:
                score = sum(picks[q["id"]] == q["answer_index"] for q in quiz["questions"])
                total = len(quiz["questions"])
                answers = {str(k): v for k, v in picks.items()}
                db.save_attempt(quiz["id"], quiz["doc_id"], score, total, answers)
                db.log_activity("quiz", quiz["doc_id"], f"{score}/{total}")
                state["result"] = {"score": score, "total": total, "percent": 100.0 * score / total, "answers": answers}
                st.rerun()
    _history(db, doc)


def _history(db, doc):
    attempts = db.list_attempts(doc["id"])
    if attempts:
        st.markdown("#### Previous attempts for this document")
        rows = "".join(f'<div class="nv-row"><span>{a["score"]} / {a["total"]} correct</span>'
                       f'<span class="nv-muted">{a["percent"]:.0f}% · {fmt_date(a["created_at"])}</span></div>'
                       for a in attempts[:5])
        st.markdown(f'<div class="nv-list">{rows}</div>', unsafe_allow_html=True)
