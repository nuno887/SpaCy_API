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
    section_sumario: Optional[str] = None

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

        # 2) pick first org heading after Sumário as anchor A, then the next occurrence of the same heading as end.
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

    def _extract_kind_num_year(self, text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        # Run NLP and look for ents labeled by the ruler/NER
        doc = self.gnlp.nlp(text.strip())
        # Head MUST start with KIND (first token(s) belong to a KIND span)
        if not doc.ents:
            return None, None, None
        first_ent = next((e for e in doc.ents if e.label_ == "KIND" and e.start == 0), None)
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

    def parse_items(self, sum_lines: List[str]) -> List[SumarioItem]:
        items: List[SumarioItem] = []
        section_org: Optional[str] = None
        i = 0
        while i < len(sum_lines):
            raw = sum_lines[i].strip()
            if not raw:
                i += 1
                continue

            # org subheading inside Sumário
            if self.gnlp.is_org_heading(raw):
                section_org = raw
                i += 1
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
                    if self.gnlp.is_org_heading(nxt):
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
                    section_sumario=section_org
                ))
                i = j
                continue

            i += 1
        return items
