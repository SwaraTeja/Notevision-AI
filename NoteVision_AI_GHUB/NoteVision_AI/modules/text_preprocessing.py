"""NLP pre-processing: cleaning, sentence/word tokenisation, stop-words, stemming, lemmatisation,
POS tagging and named-entity recognition. Every NLTK resource has a safe fallback."""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache

import nltk
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

STOPWORDS = set(ENGLISH_STOP_WORDS) | {
    "also", "called", "used", "using", "use", "like", "example", "examples", "etc", "eg", "ie", "one", "two",
    "may", "can", "will", "many", "much", "such", "type", "types", "way", "ways", "known", "based", "makes",
    "make", "given", "include", "includes", "including", "often", "different", "various", "kind", "get", "gets",
    "new", "better", "common", "two", "three", "several", "certain", "usually", "typically", "main", "important", "thing", "things", "set", "number", "simple", "process", "see",
}
# domain-neutral words we never want to drop even if they look generic
_KEEP = {"data", "model", "system", "network", "learning", "algorithm"}
STOPWORDS -= _KEEP

_stemmer = PorterStemmer()
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-]*")


# ------------------------------------------------------------------ resources
@lru_cache(maxsize=1)
def ensure_resources() -> dict:
    """Make sure NLTK data is present (downloads once). Returns what is available."""
    status = {}
    needed = {"punkt": "tokenizers/punkt_tab", "wordnet": "corpora/wordnet",
              "tagger": "taggers/averaged_perceptron_tagger_eng"}
    pkgs = {"punkt": "punkt_tab", "wordnet": "wordnet", "tagger": "averaged_perceptron_tagger_eng"}
    for key, path in needed.items():
        try:
            nltk.data.find(path)
            status[key] = True
        except LookupError:
            try:
                status[key] = bool(nltk.download(pkgs[key], quiet=True))
            except Exception:
                status[key] = False
    status["wordnet_zip_ok"] = status["wordnet"]
    return status


# ---------------------------------------------------------------- cleaning
def clean_text(text: str) -> str:
    """Normalise OCR output: fix hyphenated line breaks, odd characters and whitespace."""
    t = text.replace("\r", "\n").replace("\u00ad", "")
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)                       # re-join words split across lines
    t = t.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    t = re.sub(r"[^\S\n]+", " ", t)                              # collapse spaces/tabs
    t = re.sub(r"[^\w\s.,;:!?()\[\]'\"%/+\-=<>&*•#@]", " ", t)     # drop stray OCR symbols
    t = re.sub(r"[ ]*\n[ ]*", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


_BULLET_RE = re.compile(r"^\s*(?:[-•*>]+|\d+[.)]|[a-zA-Z][.)])\s+")


def split_sentences(text: str) -> list[str]:
    """Sentence tokenisation that understands wrapped OCR lines, bullets and short headings."""
    ensure_resources()
    sentences: list[str] = []
    for para in re.split(r"\n\s*\n", clean_text(text)):
        lines = [l.strip() for l in para.split("\n") if l.strip()]
        merged: list[str] = []
        for line in lines:
            line = _BULLET_RE.sub("", line)
            if (merged and not re.search(r"[.!?:]$", merged[-1])
                    and line[:1].islower()):
                merged[-1] += " " + line                           # wrapped line of the same sentence
            else:
                merged.append(line)
        for seg in merged:
            try:
                parts = nltk.sent_tokenize(seg)
            except LookupError:
                parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", seg)
            sentences.extend(p.strip() for p in parts if p.strip())
    return sentences


def is_heading(sentence: str) -> bool:
    words = sentence.split()
    return len(words) < 4 or (len(words) <= 8 and not re.search(r"[.!?]$", sentence) and ":" not in sentence
                              and not re.search(r"\b(is|are|was|were|has|have|can|uses|used)\b", sentence, re.I))


def content_sentences(text: str, min_words: int = 5, max_words: int = 45) -> list[str]:
    return [s for s in split_sentences(text)
            if min_words <= len(s.split()) <= max_words and not is_heading(s)]


# ------------------------------------------------------------------ tokens
def normalize_word(word: str) -> str:
    """Cheap singularisation so 'algorithms' and 'algorithm' count as one term."""
    w = word.lower()
    if len(w) > 4:
        if w.endswith("ies"):
            return w[:-3] + "y"
        if w.endswith(("sses", "xes", "ches", "shes")):
            return w[:-2]
        if w.endswith("s") and not w.endswith(("ss", "us", "is", "ics")):
            return w[:-1]
    return w


def word_spans(sentence: str) -> list[tuple[str, int, int]]:
    out = []
    for m in WORD_RE.finditer(sentence):
        tok = m.group(0).strip("-")
        if len(tok) >= 3 or (tok.isupper() and len(tok) >= 2):
            out.append((tok, m.start(), m.end()))
    return out


def is_content_word(word: str) -> bool:
    return word.lower() not in STOPWORDS and not word.isdigit()


def stem(word: str) -> str:
    return _stemmer.stem(word.lower())


def analyzer_stems(text: str) -> list[str]:
    """Stemmed content words + stemmed bigrams. Used by TF-IDF retrieval."""
    toks = [t for t, _, _ in word_spans(text)]
    stems = [stem(t) if is_content_word(t) else None for t in toks]
    out = [s for s in stems if s]
    out += [f"{a} {b}" for a, b in zip(stems, stems[1:]) if a and b]
    return out


# --------------------------------------------------------------- full pipeline
def preprocess(text: str, max_tokens_shown: int = 60) -> dict:
    """Run the complete NLP pipeline and return every intermediate result for display."""
    res = ensure_resources()
    cleaned = clean_text(text)
    sentences = split_sentences(cleaned)
    tokens = [m.group(0) for m in re.finditer(r"[A-Za-z][A-Za-z0-9'\-]*|\d+", cleaned)]
    lower = [t.lower() for t in tokens]
    no_stop = [t for t in lower if t not in STOPWORDS and len(t) > 1]
    stems = [stem(t) for t in no_stop]

    lemmatizer = None
    if res.get("wordnet"):
        try:
            from nltk.stem import WordNetLemmatizer
            lemmatizer = WordNetLemmatizer()
            lemmatizer.lemmatize("tests")
        except Exception:
            lemmatizer = None
    lemmas = [lemmatizer.lemmatize(t) for t in no_stop] if lemmatizer else [normalize_word(t) for t in no_stop]

    processed_text = " ".join(lemmas)
    return {
        "cleaned": cleaned,
        "sentences": sentences,
        "tokens": tokens,
        "lowercase": lower,
        "no_stopwords": no_stop,
        "stems": stems,
        "lemmas": lemmas,
        "processed_text": processed_text,
        "pos": pos_tags(cleaned),
        "entities": named_entities(cleaned),
        "stats": {
            "characters": len(cleaned), "words": len(tokens), "sentences": len(sentences),
            "unique_words": len(set(lower)), "after_stopwords": len(no_stop),
        },
        "lemmatizer": "WordNet" if lemmatizer else "rule-based fallback",
        "table": [{"token": t, "stem": stem(t), "lemma": l}
                  for t, l in list(zip(no_stop, lemmas))[:max_tokens_shown]],
    }


def pos_tags(text: str, limit: int = 4000) -> dict:
    """Part-of-speech tags using NLTK's averaged perceptron tagger."""
    res = ensure_resources()
    sample = text[:limit]
    tags: list[tuple[str, str]] = []
    engine = "none"
    if res.get("tagger"):
        try:
            toks = nltk.word_tokenize(sample)
            tags = [(w, t) for w, t in nltk.pos_tag(toks) if re.match(r"\w", w)]
            engine = "NLTK"
        except Exception:
            tags = []
    return {"engine": engine, "tags": tags, "counts": dict(Counter(t for _, t in tags))}


def named_entities(text: str, limit: int = 6000) -> dict:
    """Simple rule-based NER: finds capitalised names and acronyms (no extra library needed)."""
    found: Counter = Counter()
    for s in split_sentences(text):
        for m in re.finditer(r"(?<!^)(?<![.!?]\s)\b((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)|[A-Z]{2,})\b", s):
            ent = m.group(1)
            if ent.lower() not in STOPWORDS and len(ent) > 2:
                found[ent] += 1
    return {"engine": "rule-based (capitalised words and acronyms)",
            "entities": [{"entity": e, "label": "Proper noun / acronym", "count": c}
                         for e, c in found.most_common(40)]}


def noun_filter(text: str = ""):
    """Return a predicate key->bool: does this keyword behave like a noun / noun phrase?
    Uses WordNet sense frequencies (noun vs verb) because POS taggers are unreliable on terse notes.
    Words unknown to WordNet (e.g. 'overfitting') are accepted as domain terms."""
    if not ensure_resources().get("wordnet"):
        return lambda key: True
    from nltk.corpus import wordnet as wn

    def freq(word: str, pos: str) -> int:
        return sum(l.count() for syn in wn.synsets(word, pos) for l in syn.lemmas() if l.name().lower() == word)

    cache: dict[str, bool] = {}

    def noun_like(word: str) -> bool:
        if word in cache:
            return cache[word]
        base = wn.morphy(word, "n") or word
        if word.endswith("ly") or (word.endswith("ed") and len(word) > 5):
            ok = False
        elif not wn.synsets(base) and not wn.synsets(word):
            ok = True                                   # unknown to WordNet: assume domain term
        else:
            n = len(wn.synsets(base, "n"))
            ok = n > 0 and freq(base, "v") <= 2 * freq(base, "n")
        cache[word] = ok
        return ok

    return lambda key: noun_like(key.split()[-1])
