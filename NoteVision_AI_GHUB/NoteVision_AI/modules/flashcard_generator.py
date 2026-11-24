"""Flashcards built from the notes: definitions first, then key terms with their best context sentence."""
from __future__ import annotations

from modules import text_preprocessing as tp
from modules.keyword_extractor import extract_definitions, extract_keywords


def generate_flashcards(text: str, max_cards: int = 30) -> list[dict]:
    sentences = tp.content_sentences(text, min_words=5, max_words=45)
    cards, seen = [], set()
    for d in extract_definitions(sentences):
        cards.append({"front": f"What is {d['term']}?", "back": d["sentence"]})
        seen.add(d["term"].lower())
    is_noun = tp.noun_filter(text)
    for kw in extract_keywords(text, top_n=60):
        if not is_noun(kw["key"]):
            continue
        if len(cards) >= max_cards:
            break
        term = kw["term"]
        if any(term in s for s in seen) or term in seen:
            continue
        ctx = [s for s in sentences if term in s.lower()]
        if not ctx:
            continue
        best = max(ctx, key=lambda s: (s.lower().count(term), -abs(len(s.split()) - 20)))
        cards.append({"front": f"Explain: {term.title()}", "back": best})
        seen.add(term)
    return cards[:max_cards]
