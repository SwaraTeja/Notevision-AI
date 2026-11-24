import random

import streamlit as st

from modules.flashcard_generator import generate_flashcards
from modules.ui import doc_picker, esc, page_header


def _state(doc_id):
    s = st.session_state.setdefault("fc", {})
    if s.get("doc") != doc_id:
        s.clear()
        s.update({"doc": doc_id, "i": 0, "flip": False, "seed": None})
    return s


def _move(delta, total):
    s = st.session_state["fc"]
    s["i"] = (s["i"] + delta) % max(total, 1)
    s["flip"] = False


def _flip():
    st.session_state["fc"]["flip"] ^= True


def _shuffle():
    s = st.session_state["fc"]
    s["seed"] = random.randint(1, 10**6)
    s["i"], s["flip"] = 0, False


def _mark(db, card, status):
    db.set_flashcard_status(card["id"], status)
    db.log_activity("flashcard", card["doc_id"], status)
    s = st.session_state["fc"]
    s["i"] += 1 if status == "known" and st.session_state.get("fc_filter") != "Need revision" else 0
    s["flip"] = False


def _generate(db, doc):
    cards = generate_flashcards(db.get_full_text(doc["id"]))
    if not cards:
        st.error("No flashcards could be built. The notes need clear definitions or repeated key terms.")
        return
    db.replace_flashcards(doc["id"], cards)
    st.session_state.pop("fc", None)


def render(db):
    page_header("Flashcards", "Revise key concepts from your notes. Mark each card so you know what still needs work.")
    doc = doc_picker(db, "fc_doc")
    if not doc:
        return
    s = _state(doc["id"])
    cards = db.get_flashcards(doc["id"])

    if not cards:
        st.info("No flashcards yet for this document.")
        if st.button("Create flashcards", type="primary", icon=":material/style:"):
            _generate(db, doc)
            st.rerun()
        return

    known = sum(c["status"] == "known" for c in cards)
    revise = sum(c["status"] == "revise" for c in cards)
    m = st.columns(4)
    m[0].metric("Total cards", len(cards)); m[1].metric("Known", known)
    m[2].metric("Need revision", revise); m[3].metric("Not reviewed", len(cards) - known - revise)
    st.progress(known / len(cards), text=f"{known} of {len(cards)} cards known")

    f1, f2 = st.columns([2, 1])
    mode = f1.radio("Show", ["All cards", "Need revision", "Not reviewed"], horizontal=True, key="fc_filter")
    deck = {"All cards": cards, "Need revision": [c for c in cards if c["status"] == "revise"],
            "Not reviewed": [c for c in cards if c["status"] == "new"]}[mode]
    if f2.button("Regenerate cards", icon=":material/refresh:", help="Rebuilds the deck and resets your progress"):
        _generate(db, doc)
        st.rerun()
    if not deck:
        st.success("Nothing in this view. Try another filter.")
        return
    if s["seed"]:
        deck = random.Random(s["seed"]).sample(deck, len(deck))
    s["i"] %= len(deck)
    card = deck[s["i"]]

    side = "back" if s["flip"] else "front"
    text = card["back"] if s["flip"] else card["front"]
    st.markdown(f'<div class="nv-flash {side}"><div class="side">{"Answer" if s["flip"] else "Question"} · card {s["i"] + 1} of {len(deck)}</div>'
                f'<div class="txt">{esc(text)}</div></div>', unsafe_allow_html=True)
    st.write("")
    b = st.columns(4)
    b[0].button("Previous", icon=":material/arrow_back:", width="stretch", on_click=_move, args=(-1, len(deck)))
    b[1].button("Flip card", icon=":material/flip:", type="primary", width="stretch", on_click=_flip)
    b[2].button("Next", icon=":material/arrow_forward:", width="stretch", on_click=_move, args=(1, len(deck)))
    b[3].button("Shuffle", icon=":material/shuffle:", width="stretch", on_click=_shuffle)
    r = st.columns(2)
    r[0].button("Need revision", icon=":material/error:", width="stretch", on_click=_mark, args=(db, card, "revise"))
    r[1].button("Mark as known", icon=":material/check_circle:", width="stretch", on_click=_mark, args=(db, card, "known"))
