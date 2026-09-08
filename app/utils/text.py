"""
Text normalization helpers shared by search matching and title storage.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_title(text: str) -> str:
    """Lowercase, whitespace-collapsed form used for consistent matching."""
    return _WHITESPACE_RE.sub(" ", text.strip()).lower()
