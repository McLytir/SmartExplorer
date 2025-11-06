from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import List, Optional

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional dependency
    fitz = None  # type: ignore
try:
    import pytesseract  # type: ignore
    from pytesseract import Output as TesseractOutput  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore
    TesseractOutput = None  # type: ignore
try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None  # type: ignore


@dataclass(frozen=True)
class PdfOverlayBox:
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class PdfOverlayPage:
    width: int
    height: int
    boxes: List[PdfOverlayBox]
    image_png: bytes


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


def _ocr_boxes_from_pixmap(pix, *, max_boxes: int = 200) -> List[PdfOverlayBox]:
    if not pytesseract or not Image or not TesseractOutput:
        return []
    try:
        img = Image.open(io.BytesIO(pix.tobytes("png")))
    except Exception:
        return []

    lang_candidates = [
        os.getenv("SMARTEXPLORER_OCR_LANG", "jpn+eng").strip() or "",
        "eng",
        "",
    ]
    data = None
    for lang in lang_candidates:
        try:
            kwargs = {"output_type": TesseractOutput.DICT}
            if lang:
                kwargs["lang"] = lang
            data = pytesseract.image_to_data(img, **kwargs)
            if data:
                break
        except Exception:
            data = None
            continue

    if not data or "text" not in data:
        return []

    texts = data.get("text", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    widths = data.get("width", [])
    heights = data.get("height", [])
    confs = data.get("conf", [])

    boxes: List[PdfOverlayBox] = []
    for idx, text in enumerate(texts):
        if len(boxes) >= max_boxes:
            break
        try:
            conf_val = float(confs[idx])
        except Exception:
            conf_val = 0.0
        if conf_val < 40.0:
            continue
        txt = (text or "").strip()
        if not txt:
            continue
        try:
            x = float(lefts[idx])
            y = float(tops[idx])
            w = float(widths[idx])
            h = float(heights[idx])
        except Exception:
            continue
        if w <= 1 or h <= 1:
            continue
        boxes.append(PdfOverlayBox(
            text=txt,
            x=x,
            y=y,
            width=w,
            height=h,
        ))
    return boxes


def first_page_overlay(path: str, *, scale: float = 2.0, max_boxes: int = 200) -> Optional[PdfOverlayPage]:
    """
    Extract overlay data for the first page of a PDF.

    Returns a rendered PNG as bytes along with text boxes in pixel coordinates.
    The `scale` parameter controls the rendering resolution (1.0 = 72 dpi).
    """
    if not fitz:
        return None

    doc = None
    try:
        doc = fitz.open(path)
    except Exception:
        return None

    if doc is None:
        return None

    try:
        if doc.page_count <= 0:
            return None
        page = doc.load_page(0)
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            return None

        scale = max(0.5, min(scale, 4.0))
        matrix = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        png_bytes = pix.tobytes("png")
        if not png_bytes:
            return None

        scale_x = pix.width / rect.width if rect.width else 1.0
        scale_y = pix.height / rect.height if rect.height else 1.0

        boxes: List[PdfOverlayBox] = []
        try:
            dict_data = page.get_text("dict")
        except Exception:
            dict_data = None

        if dict_data and isinstance(dict_data, dict):
            for block in dict_data.get("blocks", []):
                if not isinstance(block, dict):
                    continue
                if int(block.get("type", 0) or 0) != 0:
                    continue
                for line in block.get("lines", []):
                    if not isinstance(line, dict):
                        continue
                    for span in line.get("spans", []):
                        if not isinstance(span, dict):
                            continue
                        text = (span.get("text") or "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox")
                        if (
                            not isinstance(bbox, (list, tuple))
                            or len(bbox) != 4
                        ):
                            continue
                        x0, y0, x1, y1 = bbox
                        width = float(x1 - x0)
                        height = float(y1 - y0)
                        if width <= 0 or height <= 0:
                            continue
                        dir_vec = span.get("dir")
                        # Skip strongly vertical text for now; their bounding boxes often
                        # overlap heavily with long runs of single glyphs.
                        if isinstance(dir_vec, (list, tuple)) and len(dir_vec) == 2:
                            dx, dy = dir_vec
                            if abs(dy) > abs(dx) * 1.5:
                                continue
                        boxes.append(PdfOverlayBox(
                            text=text.replace("\n", " ").strip(),
                            x=float(x0) * scale_x,
                            y=float(y0) * scale_y,
                            width=max(1.0, width * scale_x),
                            height=max(1.0, height * scale_y),
                        ))
                        if len(boxes) >= max_boxes:
                            break
                    if len(boxes) >= max_boxes:
                        break
                if len(boxes) >= max_boxes:
                    break

        if not boxes:
            # Fallback to coarse blocks if fine spans missing
            try:
                blocks = page.get_text("blocks")
            except Exception:
                blocks = []
            for block in blocks:
                if len(block) < 6:
                    continue
                x0, y0, x1, y1, text, block_type = block[:6]
                if block_type != 0:
                    continue  # skip images / other content
                if not text or not text.strip():
                    continue
                boxes.append(PdfOverlayBox(
                    text=text.strip(),
                    x=float(x0) * scale_x,
                    y=float(y0) * scale_y,
                    width=max(1.0, float(x1 - x0) * scale_x),
                    height=max(1.0, float(y1 - y0) * scale_y),
                ))
                if len(boxes) >= max_boxes:
                    break
        if not boxes:
            boxes.extend(_ocr_boxes_from_pixmap(pix, max_boxes=max_boxes))

        return PdfOverlayPage(
            width=int(pix.width),
            height=int(pix.height),
            boxes=boxes,
            image_png=png_bytes,
        )
    except Exception:
        return None
    finally:
        try:
            doc.close()
        except Exception:
            pass
