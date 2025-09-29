# pdf_extractor/services/text_extractor.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import io
import os

import fitz  # PyMuPDF
from PIL import Image
import pytesseract


@dataclass(slots=True)
class TextExtractionResult:
    pdf_name: str
    pages: List[str]          # page-level text after cleanup (respecting ignore_top_percent)
    combined: str             # all pages joined with \n\n
    ocr_pages: List[int]      # 0-based page indices that were OCR’d
    notes: List[str]          # informational notes (e.g., "forced OCR on page 2")


class TextExtractor:
    """
    Extracts text from a PDF:
      - Optionally ignores the top N% of each page (to drop headers)
      - Optionally skips the last page entirely
      - Tries digital text first; falls back to OCR if text is empty/very short
      - Special case for page 2: if it looks like mixed one-col header + two-col body, force OCR 
    """

    def __init__(
        self,
        dpi: int = 600,
        ocr_lang: str = "por",
        ignore_top_percent: float = 0.10,
        skip_last_page: bool = True,
        tesseract_cmd: Optional[str] = None,
        tessdata_prefix: Optional[str] = None,
        min_digital_chars: int = 3,  # threshold to decide fallback OCR
    ):
        self.dpi = dpi
        self.ocr_lang = ocr_lang
        self.ignore_top_percent = max(0.0, min(1.0, ignore_top_percent))
        self.skip_last_page = skip_last_page
        self.min_digital_chars = min_digital_chars

        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        if tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix

   
    
    # Para FastApi, não cria .txt files like the "extract"
def extract_from_bytes(self, pdf_bytes: bytes) -> TextExtractionResult:
    import fitz, io
    notes: list[str] = []
    ocr_pages: list[int] = []
    page_texts: list[str] = []

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        last_index = doc.page_count - 1
        effective_last = last_index - 1 if (self.skip_last_page and doc.page_count >= 1) else last_index
        if effective_last < 0:
            return TextExtractionResult(pdf_name="upload.pdf", pages=[], combined="", ocr_pages=[], notes=["no pages"])

        for i in range(0, effective_last + 1):
            page = doc[i]
            clip = self._page_clip_rect(page, i, self.ignore_top_percent)
            force_ocr = (i == 1) and self._should_force_ocr_page2(page, clip)
            if force_ocr:
                txt = self._extract_text_ocr(page, clip); ocr_pages.append(i); notes.append("forced OCR on page 2")
            else:
                txt = self._extract_text_digital(page, clip)
                if len(txt) < self.min_digital_chars:
                    txt = self._extract_text_ocr(page, clip); ocr_pages.append(i)
            page_texts.append(txt)

    combined = "\n\n".join(page_texts)
    return TextExtractionResult(pdf_name="upload.pdf", pages=page_texts, combined=combined, ocr_pages=ocr_pages, notes=notes)


    # ---------- helpers ----------
    def _page_clip_rect(self, page: fitz.Page, page_index: int, ignore_top_fraction: float) -> fitz.Rect:
        rect = page.rect
        if page_index == 0 or ignore_top_fraction <= 0:
            return rect
        top_cut = rect.height * ignore_top_fraction
        return fitz.Rect(rect.x0, rect.y0 + top_cut, rect.x1, rect.y1)

    def _extract_text_digital(self, page: fitz.Page, clip: fitz.Rect) -> str:
        txt = page.get_text("text", clip=clip) or ""
        return txt.strip()

    def _extract_text_ocr(self, page: fitz.Page, clip: fitz.Rect) -> str:
        pix = page.get_pixmap(dpi=self.dpi, clip=clip, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        try:
            return pytesseract.image_to_string(img, lang=self.ocr_lang).strip()
        except Exception:
            # fallback without explicit lang
            return pytesseract.image_to_string(img).strip()

    def _should_force_ocr_page2(self, page: fitz.Page, clip: fitz.Rect) -> bool:
        """
        Heuristic: Page 2 often renders as mixed layout where digital text extraction breaks.
        We look for:
          - narrow blocks at the top (header-like, single column)
          - plus blocks later distributed left/right (two columns)
        """
        blocks = page.get_text("blocks", clip=clip) or []
        if not blocks:
            return False

        # sort by top (y), then left (x)
        blocks.sort(key=lambda b: (b[1], b[0]))

        page_w = (clip.x1 - clip.x0) if clip else page.rect.width
        page_h = (clip.y1 - clip.y0) if clip else page.rect.height
        mid_x = ((clip.x0 + clip.x1) / 2) if clip else ((page.rect.x0 + page.rect.x1) / 2)
        zone_y1 = (clip.y0 if clip else page.rect.y0) + 0.15 * page_h

        def is_narrow(b):  # b = (x0, y0, x1, y1, text, block_no, ...)
            return (b[2] - b[0]) <= 0.60 * page_w

        top_blocks = [b for b in blocks if b[1] <= zone_y1]
        body_blocks = [b for b in blocks if b[1] > zone_y1]

        starts_one_col = any(is_narrow(b) for b in top_blocks)

        def cx(b): return (b[0] + b[2]) / 2
        left = [b for b in body_blocks if cx(b) < mid_x]
        right = [b for b in body_blocks if cx(b) >= mid_x]
        has_two_cols_later = (len(left) >= 1 and len(right) >= 1)

        return starts_one_col and has_two_cols_later
