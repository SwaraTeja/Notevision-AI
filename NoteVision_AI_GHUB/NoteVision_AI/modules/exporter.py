"""Download helper: plain-text export of generated study material."""
from __future__ import annotations

import re


def markdown_to_text(md: str) -> str:
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", md)
    t = re.sub(r"`(.*?)`", r"\1", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    return t.strip() + "\n"
