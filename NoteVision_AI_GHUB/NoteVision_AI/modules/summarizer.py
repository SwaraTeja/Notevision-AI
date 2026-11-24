"""Extractive summariser (TF-IDF sentence scoring + redundancy removal).

Everything returned is made of sentences/terms that exist in the student's notes; nothing is invented."""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from modules import text_preprocessing as tp
from modules.keyword_extractor import extract_definitions, extract_keywords

MODES = {
    "quick": "Quick Summary",
    "detailed": "Detailed Summary",
    "exam": "Exam Revision Notes",
}


def rank_sentences(sentences: list[str], keywords: list[dict]) -> list[tuple[int, float]]:
    """Score every sentence: TF-IDF weight of its terms + keyword hits + definition/position bonuses."""
    if len(sentences) < 2:
        return [(i, 1.0) for i in range(len(sentences))]
    vec = TfidfVectorizer(analyzer=tp.analyzer_stems, sublinear_tf=True)
    try:
        mat = vec.fit_transform(sentences)
    except ValueError:
        return [(i, 1.0) for i in range(len(sentences))]
    base = np.asarray(mat.sum(axis=1)).ravel() / np.sqrt(np.maximum(np.asarray((mat > 0).sum(axis=1)).ravel(), 1))
    kw_terms = [k["term"].lower() for k in keywords[:12]]
    scores = []
    for i, s in enumerate(sentences):
        low = s.lower()
        score = float(base[i]) + 0.15 * sum(1 for k in kw_terms if k in low)
        if i < 2:
            score *= 1.15                                       # opening sentences usually introduce the topic
        if any(c in low for c in (" is a ", " is an ", " refers to ", " is defined as", " are ", " means ")):
            score *= 1.1
        scores.append(score)
    return list(enumerate(scores))


def select_sentences(sentences: list[str], scores: list[tuple[int, float]], n: int, redundancy: float = 0.55) -> list[int]:
    """Greedy top-n selection that skips sentences too similar to those already chosen (MMR-style)."""
    if not sentences:
        return []
    vec = TfidfVectorizer(analyzer=tp.analyzer_stems)
    try:
        mat = vec.fit_transform(sentences)
        sim = cosine_similarity(mat)
    except ValueError:
        sim = np.zeros((len(sentences), len(sentences)))
    chosen: list[int] = []
    for idx, _ in sorted(scores, key=lambda x: x[1], reverse=True):
        if len(chosen) >= n:
            break
        if all(sim[idx, c] < redundancy for c in chosen):
            chosen.append(idx)
    return sorted(chosen)


def _prepare(text: str):
    sentences = tp.content_sentences(text)
    keywords = extract_keywords(text, top_n=15)
    return sentences, keywords


def summarize(text: str, mode: str = "quick", title: str = "") -> str:
    sentences, keywords = _prepare(text)
    if len(sentences) < 2:
        raise ValueError("The notes are too short to summarise. Add more text (at least a few full sentences).")
    scores = rank_sentences(sentences, keywords)
    n = len(sentences)

    if mode == "quick":
        k = min(n, max(3, min(6, round(n * 0.2))))
        picks = select_sentences(sentences, scores, k)
        body = " ".join(sentences[i] for i in picks)
        top = ", ".join(k_["term"] for k_ in keywords[:6])
        return f"## Quick summary\n\n{body}\n\n**Main topics:** {top}" if top else f"## Quick summary\n\n{body}"

    if mode == "detailed":
        k = min(n, max(5, min(16, round(n * 0.4))))
        picks = select_sentences(sentences, scores, k)
        overview = picks[:2]
        points = picks[2:] if len(picks) > 2 else picks
        defs = extract_definitions(sentences)
        out = ["## Detailed summary", "", "### Overview", " ".join(sentences[i] for i in overview), "",
               "### Key points", *[f"- {sentences[i]}" for i in points]]
        if defs:
            out += ["", "### Definitions found in your notes",
                    *[f"- **{d['term']}**: {d['definition']}" for d in defs[:8]]]
        out += ["", "### Key terms", ", ".join(k_["term"] for k_ in keywords[:12])]
        return "\n".join(out)

    if mode == "exam":
        return exam_notes(sentences, keywords, scores)
    raise ValueError(f"Unknown summary mode: {mode}")


def exam_notes(sentences: list[str], keywords: list[dict], scores) -> str:
    defs = extract_definitions(sentences)
    k = min(len(sentences), max(5, min(12, round(len(sentences) * 0.3))))
    picks = select_sentences(sentences, scores, k)
    out = ["## Exam revision notes", ""]

    out += ["### Important definitions"]
    out += [f"- **{d['term']}**: {d['definition']}" for d in defs[:10]] or \
           ["- No explicit definitions ('X is ...') were found in these notes."]

    out += ["", "### Key concepts"]
    for kw in keywords[:8]:
        ctx = next((s for s in sentences if kw["term"] in s.lower()), None)
        if ctx:
            out.append(f"- **{kw['term'].title()}**: {ctx}")

    out += ["", "### Important terms to remember", ", ".join(f"`{k_['term']}`" for k_ in keywords[:15])]

    out += ["", "### Quick revision points", *[f"- {sentences[i]}" for i in picks]]

    qs: list[str] = []
    for d in defs[:5]:
        qs.append(f"Define **{d['term']}**.")
    for kw in keywords[:6]:
        if kw["count"] >= 2 and not any(kw["term"].lower() == d["term"].lower() for d in defs):
            qs.append(f"Explain **{kw['term']}** with reference to your notes.")
    contrast = [s for s in sentences if any(w in s.lower() for w in ("whereas", "unlike", "differ", "in contrast", " while "))]
    for s in contrast[:2]:
        present = [k_["term"] for k_ in keywords if k_["term"] in s.lower()][:2]
        if len(present) == 2:
            qs.append(f"Differentiate between **{present[0]}** and **{present[1]}**.")
    out += ["", "### Questions you may be asked"]
    out += [f"{i}. {q}" for i, q in enumerate(qs[:10], 1)] or ["- Not enough repeated concepts to suggest questions."]
    return "\n".join(out)
