# pdf_extractor/services/linker.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Tuple

from .sumario import SumarioItem
from .slicer import BodySlice

@dataclass(frozen=True, slots=True)
class LinkResult:
    item: Optional[SumarioItem]
    slice: BodySlice
    status: Literal["matched","fallback","unmatched"]
    reason: Optional[str] = None

class Linker:
    def link(self, items: List[SumarioItem], slices: List[BodySlice]) -> List[LinkResult]:
        if not slices:
            return []

        results: List[LinkResult] = []
        used: set[int] = set()

        # Build an index for exact matching
        index: Dict[Tuple[str, Optional[str], Optional[str]], List[int]] = {}
        for i, sl in enumerate(slices):
            key = ((sl.kind or "unknown"), (sl.number or None), (sl.year or None))
            index.setdefault(key, []).append(i)

        # 1) Try to match each Sumário item to a unique slice
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
                results.append(LinkResult(item=it, slice=slices[anchor], status="matched"))
            else:
                # no exact body anchor found
                pass

        # 2) Any remaining slices become fallback docs (no Sumário match)
        for i, sl in enumerate(slices):
            if i not in used:
                results.append(LinkResult(item=None, slice=sl, status="fallback", reason="no_sumario_match"))

        # Keep global body order
        results.sort(key=lambda r: r.slice.start_line)
        return results
