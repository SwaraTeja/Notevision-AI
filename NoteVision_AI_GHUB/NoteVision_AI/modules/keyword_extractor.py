"""Keyword / key-phrase extraction with TF-IDF (sentences are the 'documents')."""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from modules import text_preprocessing as tp


def _terms(sentence: str) -> list[tuple[str, str]]:
    """(key, surface) unigrams and bigrams of content words in one sentence."""
    toks = tp.word_spans(sentence)
    terms = []
    for i, (tok, *_rest) in enumerate(toks):
        if tp.is_content_word(tok):
            terms.append((tp.normalize_word(tok), tok.lower()))
        if i + 1 < len(toks) and tp.is_content_word(tok) and tp.is_content_word(toks[i + 1][0]):
            a, b = tok, toks[i + 1][0]
            terms.append((f"{tp.normalize_word(a)} {tp.normalize_word(b)}", f"{a.lower()} {b.lower()}"))
    return terms


def extract_keywords(text: str, top_n: int = 15) -> list[dict]:
    """Return [{'term','score','count','key'}] ranked by summed TF-IDF over sentences.
    Frequent two-word phrases are preferred over the single words they contain."""
    sents = [s for s in tp.split_sentences(text) if len(s.split()) >= 2]
    if not sents:
        return []
    surface: dict[str, Counter] = defaultdict(Counter)
    for s in sents:
        for key, surf in _terms(s):
            surface[key][surf] += 1

    vec = TfidfVectorizer(analyzer=lambda s: [k for k, _ in _terms(s)], sublinear_tf=True)
    try:
        mat = vec.fit_transform(sents)
    except ValueError:
        return []
    scores = np.asarray(mat.sum(axis=0)).ravel()
    counts = np.asarray((mat > 0).sum(axis=0)).ravel()
    items = []
    for key, idx in vec.vocabulary_.items():
        n_words = key.count(" ") + 1
        total = sum(surface[key].values())
        if n_words == 2 and total < 2:
            continue
        if n_words == 1 and len(key) < 3 and not key.isalpha():
            continue
        score = float(scores[idx]) * (1.5 if n_words == 2 else 1.0)
        items.append({"key": key, "term": surface[key].most_common(1)[0][0], "score": score,
                      "count": int(total), "sentences": int(counts[idx])})
    items.sort(key=lambda d: d["score"], reverse=True)

    chosen: list[dict] = []
    bigrams = [i for i in items if " " in i["key"]][: max(3, top_n // 2)]
    covered = {w for b in bigrams for w in b["key"].split()}
    chosen.extend(bigrams)
    for it in items:
        if " " not in it["key"] and it["key"] not in covered:
            chosen.append(it)
    chosen.sort(key=lambda d: d["score"], reverse=True)
    return chosen[:top_n]


def extract_definitions(sentences: list[str]) -> list[dict]:
    """Find 'X is/are/refers to/means ...' and 'X: ...' style definitions in the notes."""
    import re
    pat = re.compile(
        r"^(?P<term>[A-Za-z][\w\-/ ()']{1,55}?)\s+(?:is|are|refers to|means|is defined as|are defined as|can be defined as|is called|are called)\s+(?P<definition>.{12,})$")
    colon = re.compile(r"^(?P<term>[A-Z][\w\-/ ()']{1,45}):\s+(?P<definition>.{12,})$")
    out, seen = [], set()
    for s in sentences:
        s = s.strip()
        m = colon.match(s) or pat.match(s)
        if not m:
            continue
        term = re.sub(r"^(?:the|a|an)\s+", "", m.group("term").strip(), flags=re.I).strip(" -:")
        definition = m.group("definition").strip()
        words = term.split()
        if not (1 <= len(words) <= 5) or term.lower() in tp.STOPWORDS or term.lower() in seen:
            continue
        if words[0].lower() in {"it", "this", "that", "these", "those", "there", "which", "they", "he", "she", "we"}:
            continue
        if any(w.lower() in {"because", "when", "if", "while", "since", "although", "and", "or", "but", "that", "which", "who", "where", "whose", "with", "can"} for w in words):
            continue
        term = term[0].upper() + term[1:]
        seen.add(term.lower())
        out.append({"term": term, "definition": definition, "sentence": s})
    return out
