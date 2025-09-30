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
    text: str           # header line (raw)
    title: str          # short continuation (1–3 following lines)
    line_range: Tuple[int,int]
    section_sumario: Optional[str] = None        # kept for backward-compat (first org or single-line)
    section_sumario_raw: Optional[str] = None    # full multi-line org block as seen in Sumário
    section_orgs: Tuple[str, ...] = tuple()      # all orgs parsed from block (ordered)

class SumarioParser:
    def __init__(self, nlp: GazetteNLP):
        self.gnlp = nlp

    def find_range(self, lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
        # 1) locate "Sumário" / "Sumario"
        start = None
        for i, ln in enumerate(lines):
            if ascii_lower(ln.strip()) in ("sumario","sumário"):
                start = i
                break
        if start is None:
            return None, None
        
      # 2) pick first ORG block (must have blank line before) after Sumário as anchor A,
      #    then the next occurrence of the same heading as end.
        first_org = None
        j = start + 1
        while j < len(lines):
            if self._is_org_block_start(lines[j]):
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
            # fallback: stop at the next ORG block or cap
            for k in range(j + 1, min(len(lines), start + 150)):
                if self._is_org_block_start(lines, k):
                    end = k
                    break
        if end is None:
            end = min(len(lines), start + 150)
        return start, end

    def _extract_kind_num_year(self, text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        # Run NLP and look for ents labeled by the ruler/NER
        doc = self.gnlp.nlp(text.strip())
        # Head MUST start with DOC_TYPE (first token(s) belong to a DOC_TYPE span)
        if not doc.ents:
            return None, None, None
        first_ent = next((e for e in doc.ents if e.label_ == "DOC_TYPE" and e.start == 0), None)
        if not first_ent:
            return None, None, None

        # find nearest number/year in the same sentence
        number = None; year = None
        for e in doc.ents:
            if e.label_ == "DOC_NUM" and any(ch.isdigit() for ch in e.text):
                number = "".join(ch for ch in e.text if ch.isdigit())
            if e.label_ == "DOC_YEAR" and e.text.isdigit() and 1900 <= int(e.text) <= 2100:
                year = e.text
        tipo = doc[first_ent.start:first_ent.end].text.lower().strip()
        # normalize to ascii lower just in case
        tipo = unicodedata.normalize("NFKD", tipo).encode("ascii","ignore").decode("ascii").lower()
        return (tipo, number, year)
    
    #Sumário-only ORG helpers (ALL CAPS, blank-line-before, multi-line, comma split)
    def _is_allcaps_org_line(self, text: str) -> bool:
        """Candidate ORG line if: non-empty, no DOC_TYPE/NUM/YEAR on the line, >=2 alpha tokens, all alpha tokens uppercase."""
        t = text.strip()
        if not t:
            return False
        doc = self.gnlp.nlp(t)
        # avoid uppercase doc headers
        if any(ent.label_ in ("DOC_TYPE", "DOC_NUM", "DOC_YEAR") for ent in doc.ents):
            return False
        
        alpha = [tok for tok in doc if tok.is_alpha]
        if len(alpha) < 2:
            return False
        return all(tok.text == tok.text.upper() for tok in alpha)
    
    def _is_org_block_start(self, sum_lines: List[str], idx: int) -> bool:
        """Start of an ORG block iff current line is an all-caps ORG line AND previous line is blank (or idx==0)."""
        if idx < 0 or idx >= len(sum_lines):
            return False
        if not self._is_allcaps_org_line(sum_lines[idx]):
            return False
        if idx == 0:
            return True
        return sum_lines[idx - 1].strip() == ""
    
    def _consume_org_block(self, sum_lines: List[str], start_idx: int) -> tuple[str, Tuple[int,int], int]:
        """Consume continguous ORG lines starting at start_idx."""
        parts: List[str] = []
        i = start_idx
        while i < len(sum_lines):
            raw = sum_lines[i].strip()
            if not raw or not self._is_allcaps_org_line(raw):
                break
            parts.append(raw)
            i += 1
        raw_block = " ".join(parts).strip()
        return raw_block, (start_idx, i-1 if i > start_idx else start_idx), i
    
    def _split_block_orgs(self, raw_block: str) -> List[str]:
        """Split a raw multi-line ORG block on commas/semicolons (hyphens are not separators); dedupe case-insensitively."""
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
        seen = set(); out: List[str] = []
        for n in names:
            key = unicodedata.normalize("NFKC", n).casefold()
            if key not in seen:
                seen.add(key); out.append(n)
        return out

    def parse_items(self, sum_lines: List[str]) -> List[SumarioItem]:
        items: List[SumarioItem] = []
        section_org: Optional[str] = None
        current_orgs:list[str] = []
        i = 0
        while i < len(sum_lines):
            raw = sum_lines[i].strip()
            if not raw:
                i += 1
                continue

           #ORG block (Sumário-only): must start at a blank-separated all-caps line
            if self._is_org_block_start(sum_lines, i):
                block_raw, _rng, next_i = self._consume_org_block(sum_lines, i)
                current_org_raw = block_raw
                current_orgs = self._split_block_orgs(block_raw)
                i = next_i
                continue


            tipo, number, year = self._extract_kind_num_year(raw)
            if tipo:
                # capture 1–3 following lines as a compact title until we hit another header/org/blank
                lead: List[str] = []
                j = i + 1
                while j < len(sum_lines):
                    nxt = sum_lines[j].strip()
                    if not nxt:
                        break
                    #stop title if a NEW org block starts here (must have blank line before)
                    if self._is_org_block_start(sum_lines, i):
                        break
                    t2, _, _ = self._extract_kind_num_year(nxt)
                    if t2:
                        break
                    lead.append(nxt)
                    if len(lead) >= 3:
                        break
                    j += 1

                items.append(SumarioItem(
                    tipo=tipo,
                    number=number,
                    year=year,
                    text=raw,
                    title=" ".join(lead).strip(),
                    line_range=(i, max(i, j-1)),
                    #Sumário-driven ownership
                    section_sumario=(current_orgs[0] if current_orgs else None),
                    section_sumario_raw=current_org_raw,
                    section_orgs=tuple(current_orgs)
                ))
                i = j
                continue

            i += 1
        return items
