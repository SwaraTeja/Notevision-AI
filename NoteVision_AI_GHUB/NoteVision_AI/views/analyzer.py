import hashlib

import pandas as pd
import streamlit as st

import config
from modules import keyword_extractor, text_preprocessing as tp
from modules.ocr_engine import confidence_label
from modules.ui import chip, doc_picker, empty_state, page_header


@st.cache_data(show_spinner=False)
def _analyse(text: str, _h: str):
    return tp.preprocess(text), keyword_extractor.extract_keywords(text, 15)


def _scan_tab(db, doc):
    pages = db.get_pages(doc["id"])
    if not pages:
        st.warning("This document has no pages.")
        return
    page = pages[0]
    if len(pages) > 1:
        page = st.selectbox("Page", pages, format_func=lambda p: f"{'Slide' if doc['file_type'] == 'pptx' else 'Page'} {p['page_no']}", key=f"pg_{doc['id']}")
    folder = config.GENERATED_DIR / f"doc_{doc['id']}"
    orig, proc = folder / f"page_{page['page_no']}_original.png", folder / f"page_{page['page_no']}_processed.png"

    if orig.exists():
        c1, c2 = st.columns(2)
        c1.markdown("**Original**"); c1.image(str(orig), width="stretch")
        c2.markdown("**Processed for OCR**")
        if proc.exists():
            c2.image(str(proc), width="stretch")
            c2.caption("Grayscale, denoised, background-normalised, contrast-enhanced, deskewed and thresholded.")
        else:
            c2.info("This page already contains digital text, so no image processing was needed.")
    elif doc["file_type"] == "text":
        st.info("These notes were typed or pasted, so there is no scanned image.")
    elif doc["file_type"] == "pptx":
        st.info("This is a PowerPoint file. Each slide is one page; its text, tables and speaker notes were read directly.")

    meta = [chip(page["method"] or "text")]
    if page["confidence"] is not None:
        tone = {"High": "good", "Medium": "warn", "Low": "bad"}[confidence_label(page["confidence"])]
        meta.append(chip(f"Confidence {page['confidence']:.0f}% ({confidence_label(page['confidence'])})", tone))
    if page["edited"]:
        meta.append(chip("Edited by you", "gray"))
    st.markdown(" ".join(meta), unsafe_allow_html=True)
    if page["confidence"] is not None and page["confidence"] < 60:
        st.warning("Low OCR confidence. Handwriting and blurry photos are often misread, so check the text below "
                   "and fix any mistakes. Nothing is guessed or filled in for you.")

    new_text = st.text_area("Extracted text (editable)", value=page["text"], height=300, key=f"txt_{page['id']}")
    a, b, _ = st.columns([1, 1, 3])
    if a.button("Save corrections", type="primary", icon=":material/save:", key=f"save_{page['id']}"):
        db.update_page_text(page["id"], new_text)
        if doc["status"] == "Needs review":
            db.update_document_status(doc["id"], "Ready")
        st.toast("Corrections saved.", icon="✅")
        st.rerun()
    b.download_button("Download text", new_text, file_name=f"{doc['title']}_page{page['page_no']}.txt", icon=":material/download:")


def _language_tab(db, doc):
    text = db.get_full_text(doc["id"])
    if len(text.split()) < 5:
        empty_state("Not enough text", "Add or correct the extracted text first.")
        return
    res, keywords = _analyse(text, hashlib.md5(text.encode()).hexdigest())
    s = res["stats"]
    m = st.columns(5)
    for col, (l, v) in zip(m, [("Words", s["words"]), ("Sentences", s["sentences"]), ("Unique words", s["unique_words"]),
                               ("After stop-word removal", s["after_stopwords"]), ("Characters", s["characters"])]):
        col.metric(l, f"{v:,}")

    t1, t2, t3, t4 = st.tabs(["Original vs processed", "Tokens, stems, lemmas", "Keywords", "Grammar and entities"])
    with t1:
        a, b = st.columns(2)
        a.text_area("Cleaned text (sentence and word structure kept)", res["cleaned"], height=260, disabled=True)
        b.text_area("Processed text (lower-case, stop-words removed, lemmatised)", res["processed_text"], height=260, disabled=True)
        st.caption(f"Lemmatiser: {res['lemmatizer']}. Technical words are kept; only common function words are removed.")
    with t2:
        st.dataframe(pd.DataFrame(res["table"]), width="stretch", hide_index=True)
        st.caption("First 60 tokens after stop-word removal. Stem = Porter stemmer; lemma = dictionary base form.")
    with t3:
        if keywords:
            df = pd.DataFrame(keywords)[["term", "score"]].rename(columns={"score": "TF-IDF score"})
            st.bar_chart(df.set_index("term"), horizontal=True, color="#4F46E5", height=420)
        else:
            st.info("No keywords could be extracted.")
    with t4:
        pos = res["pos"]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Part-of-speech tags** ({pos['engine']})")
            if pos["counts"]:
                df = pd.DataFrame(sorted(pos["counts"].items(), key=lambda x: -x[1]), columns=["tag", "count"])
                st.dataframe(df, width="stretch", hide_index=True, height=300)
            else:
                st.info("POS tagger data is not available.")
        with c2:
            ents = res["entities"]
            st.markdown(f"**Named entities** ({ents['engine']})")
            if ents["entities"]:
                st.dataframe(pd.DataFrame(ents["entities"]), width="stretch", hide_index=True, height=300)
            else:
                st.info("No entities detected.")


def render(db):
    page_header("Notes analyzer", "Check what was read from your notes, fix mistakes, and see how the text is processed.")
    doc = doc_picker(db, "an")
    if not doc:
        return
    tab1, tab2 = st.tabs(["Scan and text", "Language analysis"])
    with tab1:
        _scan_tab(db, doc)
    with tab2:
        _language_tab(db, doc)
