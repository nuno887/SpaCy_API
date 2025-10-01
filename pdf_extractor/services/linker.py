# pdf_extractor/services/linker.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Tuple

from .sumario import SumarioItem
from .slicer import BodySlice

import logging

@dataclass(frozen=True, slots=True)
class LinkResult:
    item: Optional[SumarioItem]
    slice: Optional[BodySlice]  # None when body anchor not found
    status: Literal["matched","unmatched"]
    reason: Optional[str] = None

class Linker:
    def link(self, items: List[SumarioItem], slices: List[BodySlice]) -> List[LinkResult]:
        if not slices:
            # No body anchors available; return all items as unanchored
            return [LinkResult(item=it, slice=None, status="unanchored", reason="no_body_headers") for it in items]

        results: List[LinkResult] = []
        used: set[int] = set()

        # Build an index for exact matching
        index: Dict[Tuple[str, Optional[str], Optional[str]], List[int]] = {}
        for i, sl in enumerate(slices):
            key = ((sl.kind or "unknown"), (sl.number or None), (sl.year or None))
            index.setdefault(key, []).append(i)

        # 1) Try to match each Sumário item to a unique slice (by doc_name)

        logging.info(f"[LINK] sumario_items={len(items)} body_slices={len(slices)}")
        for it in items:
            key = (it.tipo or "unknown", it.number or None, it.year or None)
            candidates = index.get(key, [])
            anchor = None
            for idx in candidates:
                if idx not in used:
                    anchor = idx
                    break
            if anchor is not None:
                used.add(anchor)
                sl = slices[anchor]
                logging.info(f"[LINK] MATCH doc='{it.doc_name}' -> slice[{anchor}] lines = [{sl.start_line}:{sl.end_line}]")
                results.append(LinkResult(item=it, slice=sl, status= "matched"))
            else:
                #no body anchor found -> keep the Sumário item (no fallback body-only docs)
                logging.info(f"[LINK] UNMATCHED doc='{it.doc_name}' (no anchor)")
                results.append(LinkResult(item=it, slice=None, status="unmatched", reason="no_body_anchor"))


        # Keep body order for matched; unmatched go last (preserve Sumário order)
        results.sort(key=lambda r: (r.slice.start_line if r.slice else 10**9))
        return results
