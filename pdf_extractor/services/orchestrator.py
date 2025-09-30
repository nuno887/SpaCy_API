# pdf_extractor/services/orchestrator.py
from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import date

from ..config import Config
from ..domain.bundle import PdfBundle
from .text_extractor import TextExtractor
from .gazette_nlp import GazetteNLP
from .sumario import SumarioParser
from .slicer import BodySlicer
from .linker import Linker
from .factory import DocFactory

import logging

class Pipeline:
    """Holds long-lived components (spaCy etc.) and runs the in-memory pipeline per request."""
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.gnlp = GazetteNLP()
        self.sumario = SumarioParser(self.gnlp)
        self.slicer = BodySlicer(self.gnlp)
        self.linker = Linker()
        self.factory = DocFactory()

    def process_pdf_bytes(self, pdf_bytes: bytes, pdf_name: str = "upload.pdf",
                          publication_date: Optional[date] = None) -> Dict[str, Any]:
        # 1) extract text (RAM)
        try:
            tx = TextExtractor(
                dpi=self.cfg.dpi,
                ocr_lang=self.cfg.ocr_lang,
                ignore_top_percent=self.cfg.ignore_top_percent,
                skip_last_page=self.cfg.skip_last_page,
            ).extract(pdf_bytes)
        except Exception as e:
            logging.exception("stage:text_extraction failed")
            raise RuntimeError(f"stage:text_extraction -> {e.__class__.__name__}: {e}") from e

        # 2) downstream pipeline over combined text
        try:
            lines = tx.combined.splitlines()

            sum_start, sum_end = self.sumario.find_range(lines)
            sum_lines = lines[sum_start:sum_end] if (sum_start is not None and sum_end is not None) else []
            items = self.sumario.parse_items(sum_lines)
        
        except Exception as e:
            logging.exception("stage:sumario failed")
            raise RuntimeError(f"stage:sumario -> {e.__class__.__name__}: {e}") from e
        
        try:      
            exclude = (sum_start, sum_end) if (sum_start is not None and sum_end is not None) else None
            header_lines = self.slicer.detect_headers(lines, exclude)
            slices = self.slicer.slices(lines, header_lines)
        except Exception as e:
            logging.exception("stage:slicing failed")
            raise RuntimeError(f"stage:slicing -> {e.__class__.__name}: {e}") from e
        
        try:
        
            links = self.linker.link(items, slices)
            docs = [self.factory.build(lk, pdf_name=pdf_name, source_path="memory://upload", publication_date=publication_date)
                    for lk in links]
        except Exception as e:
            logging.exception("stage:link_or_build failed")
            raise RuntimeError(f"stage:link_or_build -> {e.__class__.__name__}: {e}") from e

        bundle = PdfBundle(pdf_name=pdf_name, source_path="memory://upload", docs=docs, notes=list(tx.notes))
        return bundle.to_json()
