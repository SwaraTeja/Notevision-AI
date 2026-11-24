"""MCQ generator. Only two reliable, note-grounded question styles are used:

1. Definition questions  - 'X is ...' sentences found in the notes (term <-> definition).
2. Fill-in-the-blank     - a key term is blanked out of a real sentence from the notes.

The correct answer always comes from the notes; distractors are other key terms / definitions
from the same notes (never invented text). Questions that cannot get 3 valid distractors are skipped."""
from __future__ import annotations

import random
import re

from modules import text_preprocessing as tp
from modules.keyword_extractor import extract_definitions, extract_keywords


def _find_span(sentence: str, key: str) -> tuple[int, int] | None:
    toks = tp.word_spans(sentence)
    words = key.split()
    for i in range(len(toks) - len(words) + 1):
        if all(tp.normalize_word(toks[i + j][0]) == words[j] for j in range(len(words))):
            return toks[i][1], toks[i + len(words) - 1][2]
    return None


def _contains(sentence: str, key: str) -> bool:
    return _find_span(sentence, key) is not None


def _shuffle_options(correct: str, distractors: list[str], rnd: random.Random) -> tuple[list[str], int]:
    options = [correct] + distractors[:3]
    rnd.shuffle(options)
    return options, options.index(correct)


def _clip(text: str, limit: int = 170) -> str:
    text = text.strip().rstrip(".")
    if len(text) <= limit:
        return text + "."
    return ""


def generate_quiz(text: str, n: int = 5, seed: int | None = None) -> list[dict]:
    rnd = random.Random(seed)
    sentences = tp.content_sentences(text, min_words=7, max_words=35)
    is_noun = tp.noun_filter(text)
    keywords = [k for k in extract_keywords(text, top_n=60) if is_noun(k["key"])][:40]
    defs = extract_definitions(tp.content_sentences(text, min_words=5, max_words=40))
    def_terms = {d["term"].lower() for d in defs}
    # distractors must be concepts that matter in the notes: repeated terms or defined terms
    strong = [k for k in keywords if k["count"] >= 2 or k["term"].lower() in def_terms]
    questions: list[dict] = []
    used_sentences: set[str] = set()
    used_terms: set[str] = set()

    # ---- 1. definition questions (about half of the quiz)
    rnd.shuffle(defs)
    want_defs = (n + 1) // 2
    for d in defs:
        if len(questions) >= want_defs:
            break
        term, definition = d["term"], d["definition"]
        if term.lower() in definition.lower():
            continue
        others = [o for o in defs if o["term"] != term]
        if len(questions) % 2 == 0:
            # style A: which term does this statement describe?
            pool = [o["term"] for o in others if o["term"].lower() not in definition.lower()]
            pool += [k["term"].capitalize() for k in strong
                     if k["term"].lower() not in definition.lower() and k["term"].lower() != term.lower()]
            pool = list(dict.fromkeys(pool))
            if len(pool) < 3:
                continue
            opts, ans = _shuffle_options(term, rnd.sample(pool, 3), rnd)
            q = f"Which concept is described by this statement from your notes?\n\n“{definition.rstrip('.')}.”"
            qtype = "definition"
        else:
            # style B: what is X? (options are real definitions from the notes)
            correct = _clip(definition)
            pool = [c for c in (_clip(o["definition"]) for o in others) if c and c != correct]
            if not correct or len(pool) < 3:
                continue
            opts, ans = _shuffle_options(correct[0].upper() + correct[1:], [p[0].upper() + p[1:] for p in rnd.sample(pool, 3)], rnd)
            q = f"According to your notes, what is **{term}**?"
            qtype = "definition"
        questions.append({"question": q, "options": opts, "answer_index": ans, "qtype": qtype, "topic": term,
                          "explanation": f"From your notes: “{d['sentence']}”"})
        used_sentences.add(d["sentence"])
        used_terms.add(term.lower())

    # ---- 2. fill-in-the-blank questions for the remaining slots
    candidates = [s for s in sentences if s not in used_sentences]
    rnd.shuffle(candidates)
    for s in candidates:
        if len(questions) >= n:
            break
        hits = [k for k in keywords if k["term"].lower() not in used_terms and _contains(s, k["key"])]
        if not hits:
            continue
        kw = hits[0]
        span = _find_span(s, kw["key"])
        answer = s[span[0]:span[1]]
        if span[0] < 3 and len(s.split()) < 9:
            continue
        ans_words = set(kw["key"].split())
        pool = []
        for k in strong:
            kwords = set(k["key"].split())
            if k["key"] == kw["key"] or kwords & ans_words or _contains(s, k["key"]):
                continue
            pool.append(k["term"])
        # prefer distractors of a similar length so the blank is not guessable from the option shape
        pool.sort(key=lambda t: abs(len(t) - len(answer)))
        pool = list(dict.fromkeys(pool))[:10]
        if len(pool) < 3:
            continue
        distractors = rnd.sample(pool, 3)
        if answer[:1].isupper() or span[0] == 0:
            distractors = [d[:1].upper() + d[1:] for d in distractors]
        opts, ans = _shuffle_options(answer, distractors, rnd)
        blanked = s[:span[0]] + "_____" + s[span[1]:]
        questions.append({"question": f"Fill in the blank:\n\n“{blanked}”", "options": opts, "answer_index": ans,
                          "qtype": "fill_blank", "topic": kw["term"],
                          "explanation": f"From your notes: “{s}”"})
        used_terms.add(kw["term"].lower())

    rnd.shuffle(questions)
    return questions[:n]
