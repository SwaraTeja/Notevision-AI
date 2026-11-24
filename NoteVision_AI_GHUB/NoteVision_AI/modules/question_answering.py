"""Ask My Notes: TF-IDF retrieval + cosine similarity, with a controlled extractive answer.

The answer is always built from sentences that exist in the student's notes. When nothing relevant is
found the assistant says so instead of inventing a response."""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import config
from modules import text_preprocessing as tp
from modules.keyword_extractor import extract_definitions, extract_keywords

WINDOW, STRIDE = 3, 2
# words that describe the *kind* of question rather than its subject
QUESTION_WORDS = {"explain", "describe", "define", "simple", "simply", "word", "words", "tell", "meaning", "mean",
                  "difference", "differences", "differ", "between", "compare", "comparison", "detail", "details",
                  "briefly", "short", "answer", "list", "give", "write", "please", "understand", "concept", "notes"}


@dataclass
class Chunk:
    doc_id: int
    title: str
    page: int
    sentences: list[str]

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


def build_chunks(docs: list[dict]) -> list[Chunk]:
    """docs: [{'id','title','pages':[{'page_no','text'}]}] -> overlapping 3-sentence passages."""
    chunks: list[Chunk] = []
    for d in docs:
        for p in d["pages"]:
            sents = [s for s in tp.split_sentences(p["text"]) if len(s.split()) >= 3]
            if not sents:
                continue
            starts = list(range(0, max(len(sents) - WINDOW, 0) + 1, STRIDE))
            if starts[-1] + WINDOW < len(sents):            # make sure the tail of the page is covered
                starts.append(len(sents) - WINDOW)
            for i in starts:
                chunks.append(Chunk(d["id"], d["title"], p["page_no"], sents[i:i + WINDOW]))
    return chunks


class NotesIndex:
    def __init__(self, docs: list[dict]):
        self.chunks = build_chunks(docs)
        self.vec = TfidfVectorizer(analyzer=tp.analyzer_stems, sublinear_tf=True)
        self.matrix = self.vec.fit_transform([c.text for c in self.chunks]) if self.chunks else None

    def ready(self) -> bool:
        return self.matrix is not None and self.matrix.shape[1] > 0

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        if not self.ready():
            return []
        sims = cosine_similarity(self.vec.transform([query]), self.matrix).ravel()
        order = np.argsort(sims)[::-1][:k]
        return [(self.chunks[i], float(sims[i])) for i in order if sims[i] > 0]


def _coverage(query: str, chunk: Chunk) -> float:
    q = {tp.stem(t) for t, _, _ in tp.word_spans(query)
         if tp.is_content_word(t) and t.lower() not in QUESTION_WORDS}
    if not q:
        return 0.0
    c = {tp.stem(t) for t, _, _ in tp.word_spans(chunk.text)}
    return len(q & c) / len(q)


def answer(index: NotesIndex, question: str) -> dict:
    """Return {'found': bool, 'answer': str, 'sources': [...]}"""
    hits = index.search(question, k=3)
    if not hits or hits[0][1] < config.QA_MIN_SCORE or _coverage(question, hits[0][0]) < config.QA_MIN_COVERAGE:
        return {"found": False, "answer": "", "sources": []}

    # rank individual sentences of the best passages against the question
    cand = []
    for chunk, score in hits:
        if score < config.QA_MIN_SCORE:
            continue
        for pos, s in enumerate(chunk.sentences):
            cand.append((chunk, pos, s, score))
    sent_vec = index.vec.transform([s for _, _, s, _ in cand])
    sims = cosine_similarity(index.vec.transform([question]), sent_vec).ravel()
    ql = question.lower()
    wants_definition = bool(re.match(r"\s*(what is|what are|define|explain|describe|meaning of)", ql))
    ranked = []
    for (chunk, pos, s, score), sim in zip(cand, sims):
        bonus = 0.15 if wants_definition and re.search(r"\b(is|are|refers to|means)\b", s) else 0.0
        ranked.append((sim + bonus + 0.1 * score, chunk, pos, s, sim))
    ranked.sort(key=lambda x: x[0], reverse=True)

    n_pick = 4 if re.search(r"differen|compare|versus|\bvs\b|advantages|types of|steps", ql) else 3
    picked, seen = [], set()
    for total, chunk, pos, s, sim in ranked:
        if sim <= 0 or s in seen:
            continue
        picked.append((chunk, pos, s))
        seen.add(s)
        if len(picked) >= n_pick:
            break
    if not picked:
        return {"found": False, "answer": "", "sources": []}
    picked.sort(key=lambda x: (x[0].doc_id, x[0].page, x[1]))
    text = "\n".join(f"- {s}" for _, _, s in picked)

    sources, seen_src = [], set()
    for chunk, score in hits:
        key = (chunk.doc_id, chunk.page)
        if key in seen_src or score < config.QA_MIN_SCORE:
            continue
        seen_src.add(key)
        sources.append({"doc_id": chunk.doc_id, "title": chunk.title, "page": chunk.page,
                        "score": round(score, 3), "snippet": chunk.text[:220] + ("…" if len(chunk.text) > 220 else "")})
    return {"found": True, "answer": text, "sources": sources}


def suggest_questions(text: str, n: int = 5) -> list[str]:
    sents = tp.content_sentences(text)
    out = [f"What is {d['term']}?" for d in extract_definitions(sents)[:3]]
    for kw in extract_keywords(text, top_n=10):
        q = f"Explain {kw['term']} in simple words."
        if len(out) < n and not any(kw["term"].lower() in o.lower() for o in out):
            out.append(q)
    return out[:n]
