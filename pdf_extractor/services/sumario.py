# pdf_extractor/services/sumario.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import unicodedata

from .gazette_nlp import GazetteNLP, ascii_lower


@dataclass(frozen=True, slots=True)
class SumarioItem:
    tipo: str
    number: Optional[str]
    year: Optional[str]
    text: str                 # header line (raw)
    title: str                # ALL following lines until next header/org (keeps blanks)
    line_range: Tuple[int, int]
    section_sumario: Optional[str] = None        # first org from the current Sumário org block
    section_sumario_raw: Optional[str] = None    # full multi-line Sumário org block (joined by space)
    section_orgs: Tuple[str, ...] = tuple()      # all orgs parsed from the block (ordered, deduped)


class SumarioParser:
    def __init__(self, nlp: GazetteNLP):
        self.gnlp = nlp

    def find_range(self, lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
        # 1) locate "Sumário" / "Sumario"
        start = None
        for i, ln in enumerate(lines):
            if ascii_lower(ln.strip()) in ("sumario", "sumário"):
                start = i
                break
        if start is None:
            return None, None

        # 2) pick first ORG heading after Sumário as anchor A, then the next occurrence of the same heading as end.
        first_org = None
        j = start + 1
        while j < len(lines):
            if self.gnlp.is_org_heading(lines[j]):
                first_org = lines[j].strip()
                break
            j += 1
        if first_org is None:
            # fallback: cap block size
            return start, min(len(lines), start + 120)

        target = ascii_lower(first_org)
        end = None
        k = j + 1
        while k < len(lines):
            if ascii_lower(lines[k].strip()) == target:
                end = k
                break
            k += 1
        if end is None:
            # fallback: stop at the next org heading or cap
            for k in range(j + 1, min(len(lines), start + 150)):
                if self.gnlp.is_org_heading(lines[k]):
                    end = k
                    break
        if end is None:
            end = min(len(lines), start + 150)
        return start, end

    # ---------- helpers ----------

    def _extract_kind_num_year(self, text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Trust spaCy:
          - A line is a header if it contains a DOC_TYPE span anywhere (we ignore 'nº' variations entirely).
          - We accept leading punctuation/space before DOC_TYPE.
          - DOC_NUM: any entity with digits; we keep only digits.
          - DOC_YEAR: 4-digit number in a plausible range (1900..2100).
        """
        t = text.strip()
        if not t:
            return None, None, None

        doc = self.gnlp.nlp(t)

        # Find a DOC_TYPE whose preceding tokens are only punct/space
        kind_ent = None
        for e in doc.ents:
            if e.label_ != "DOC_TYPE":
                continue
            if all((tok.is_punct or tok.is_space) for tok in doc[:e.start]):
                kind_ent = e
                break
        if not kind_ent:
            return None, None, None

        tipo = doc[kind_ent.start:kind_ent.end].text
        # normalize tipo to ascii-lower
        tipo = unicodedata.normalize("NFKD", tipo).encode("ascii", "ignore").decode("ascii").lower().strip()

        number = None
        year = None
        for e in doc.ents:
            if e.label_ == "DOC_NUM":
                digits = "".join(ch for ch in e.text if ch.isdigit())
                if digits:
                    number = digits
            elif e.label_ == "DOC_YEAR":
                y = "".join(ch for ch in e.text if ch.isdigit())
                if len(y) == 4:
                    yi = int(y)
                    if 1900 <= yi <= 2100:
                        year = y

        return (tipo, number, year)

    def _line_starts_header(self, text: str) -> bool:
        """Header if spaCy finds a DOC_TYPE with only punct/space before it."""
        doc = self.gnlp.nlp(text.strip())
        for e in doc.ents:
            if e.label_ == "DOC_TYPE" and all((t.is_punct or t.is_space) for t in doc[:e.start]):
                return True
        return False

    def _consume_org_block(self, sum_lines: List[str], start_idx: int) -> tuple[str, Tuple[int, int], int]:
        """Consume contiguous ORG heading lines (trust spaCy is_org_heading) starting at start_idx."""
        parts: List[str] = []
        i = start_idx
        while i < len(sum_lines):
            raw = sum_lines[i].strip()
            if not raw or not self.gnlp.is_org_heading(raw):
                break
            parts.append(raw)
            i += 1
        raw_block = " ".join(parts).strip()
        return raw_block, (start_idx, i - 1 if i > start_idx else start_idx), i

    def _split_block_orgs(self, raw_block: str) -> List[str]:
        """
        Split a raw multi-line org block on commas/semicolons (hyphens are part of names),
        dedupe case-insensitively while preserving order.
        """
        if not raw_block:
            return []
        doc = self.gnlp.nlp(raw_block)
        names: List[str] = []
        current: List[str] = []
        for tok in doc:
            if tok.text in {",", ";"}:
                name = " ".join(current).strip()
                if name:
                    names.append(name)
                current = []
                continue
            current.append(tok.text)
        tail = " ".join(current).strip()
        if tail:
            names.append(tail)

        seen = set()
        out: List[str] = []
        for n in names:
            key = unicodedata.normalize("NFKD", n).casefold()
            if key not in seen:
                seen.add(key)
                out.append(n)
        return out

    # ---------- main ----------

    def parse_items(self, sum_lines: List[str]) -> List[SumarioItem]:
        """
        Trust spaCy for both ORG headings and headers.
        Title now captures ALL lines until the next header or next ORG block (does NOT stop on blanks).
        """
        items: List[SumarioItem] = []
        current_org_raw: Optional[str] = None
        current_orgs: List[str] = []
        i = 0

        while i < len(sum_lines):
            raw = sum_lines[i].strip()
            if not raw:
                i += 1
                continue

            # ORG block inside Sumário (spaCy-driven)
            if self.gnlp.is_org_heading(raw):
                block_raw, _rng, next_i = self._consume_org_block(sum_lines, i)
                current_org_raw = block_raw
                current_orgs = self._split_block_orgs(block_raw)
                i = next_i
                continue

            tipo, number, year = self._extract_kind_num_year(raw)
            if tipo:
                # Capture ALL following lines until next header or next ORG (do not stop on blanks)
                lead_lines: List[str] = []
                j = i + 1
                while j < len(sum_lines):
                    nxt = sum_lines[j]
                    if self.gnlp.is_org_heading(nxt.strip()):
                        break
                    if self._line_starts_header(nxt):
                        break
                    lead_lines.append(nxt.rstrip())
                    j += 1

                title = "\n".join(lead_lines).strip()

                items.append(SumarioItem(
                    tipo=tipo,
                    number=number,
                    year=year,
                    text=raw,
                    title=title,
                    line_range=(i, max(i, j - 1)),
                    section_sumario=(current_orgs[0] if current_orgs else None),
                    section_sumario_raw=current_org_raw,
                    section_orgs=tuple(current_orgs)
                ))
                i = j
                continue

            i += 1

        return items
