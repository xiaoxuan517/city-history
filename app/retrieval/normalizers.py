from __future__ import annotations

from textwrap import shorten
from typing import Any


def normalize_page(page: Any) -> str | None:
    if page in ("", None, "na"):
        return None
    return str(page)


def normalize_chunk_index(chunk_index: Any) -> int | None:
    if chunk_index in (None, ""):
        return None
    return int(chunk_index)


def single_line_preview(text: str, *, width: int) -> str:
    return shorten(text.replace("\n", " "), width=width, placeholder="...")
