from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .gazette_nlp import GazetteNLP

@dataclass(frozen=True, slots=True)
class BodySlice:
    start_line: int
    end_line: int
    header_text: str
    text: str
    section_body: Optional[str] = None
    kind: Optional[str] = None
    number: Optional[str] = None
    year: Optional[str] = None

class BodySlicer:
    def __init__(self, nlp: GazetteNLP):
        self.gnlp = nlp

    def _extract_kind_num_year(self, line: str) -> tuple[Optional[str], Optional[str], Optional[str], int]:
        """Return (tipo, number, year, last_token_idx_of_header_part) if line looks like a header,
        else (None, None, None, -1). Header must START with KIND."""
        doc = self.gnlp.nlp(line.strip())
        if not doc.ents:
            return None, None, None, -1

        # KIND must start at token 0
        kind_ent = next((e for e in doc.ents if e.label_ == "KIND" and e.start == 0), None)
        if not kind_ent:
            return None, None, None, -1

        # collect num/year within this sentence
        num = None; year = None
        for e in doc.ents:
            if e.label_ == "DOC_NUM" and any(ch.isdigit() for ch in e.text):
                num = "".join(ch for ch in e.text if ch.isdigit())
            if e.label_ == "DOC_YEAR" and e.text.isdigit() and 1900 <= int(e.text) <= 2100:
                year = e.text

        last_idx = kind_ent.end - 1
        # expand last_idx to include following num/year tokens if they exist
        if num or year:
            # find rightmost entity among KIND/NUM/YEAR
            rightmost_end = max([kind_ent.end] + [e.end for e in doc.ents if e.label_ in ("DOC_NUM","DOC_YEAR")], default=kind_ent.end)
            last_idx = rightmost_end - 1

        # header purity: after last_idx there should be no alphanum tokens (allow punctuation only)
        for t in doc[last_idx+1:]:
            if t.is_alpha or any(ch.isdigit() for ch in t.text):
                return None, None, None, -1

        tipo = doc[kind_ent.start:kind_ent.end].text.lower().strip()
        return tipo, num, year, last_idx

    def detect_headers(self, lines: List[str], exclude_range: Optional[Tuple[int,int]]) -> List[int]:
        """Return line indices that are headers (outside the Sumário)."""
        headers: List[int] = []
        def in_sum(i: int) -> bool:
            return exclude_range is not None and exclude_range[0] <= i < exclude_range[1]

        current_section_org: Optional[str] = None
        for i, ln in enumerate(lines):
            if in_sum(i):
                continue
            raw = ln.strip()
            if not raw:
                continue
            # Update section org when we see an org heading
            if self.gnlp.is_org_heading(raw):
                current_section_org = raw
                continue

            tipo, num, year, last_idx = self._extract_kind_num_year(raw)
            if tipo:
                headers.append(i)
        return headers

    def slices(self, lines: List[str], header_lines: List[int]) -> List[BodySlice]:
        if not header_lines:
            return []
        header_lines = sorted(set(header_lines))
        boundaries = header_lines[1:] + [len(lines)]

        # track most recent org heading above each header
        slices: List[BodySlice] = []
        current_org = None
        org_by_line: dict[int, Optional[str]] = {}
        # pass to precompute org headings
        last_seen_org: Optional[str] = None
        for i, ln in enumerate(lines):
            if self.gnlp.is_org_heading(ln):
                last_seen_org = ln.strip()
            org_by_line[i] = last_seen_org

        for start, end in zip(header_lines, boundaries):
            header_text = lines[start].strip()
            # enrich kind/num/year for slice
            tipo, num, year, _ = self._extract_kind_num_year(header_text)
            section = org_by_line.get(start)
            chunk = "\n".join(lines[start:end]).strip()
            slices.append(BodySlice(
                start_line=start,
                end_line=end-1,
                header_text=header_text,
                text=chunk,
                section_body=section,
                kind=tipo,
                number=num,
                year=year
            ))
        return slices