from __future__ import annotations

from typing import Optional

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency
    fitz = None  # type: ignore


def first_page_text(path: str) -> str:
    """Extract plain text from the first page of a PDF. Returns empty string if unavailable."""
    if not fitz:
        return ""
    try:
        doc = fitz.open(path)
    except Exception:
        return ""
    try:
        if doc.page_count <= 0:
            return ""
        page = doc.load_page(0)
        text = page.get_text("text") or ""
        return text.strip()
    except Exception:
        return ""
    finally:
        try:
            doc.close()
        except Exception:
            pass
