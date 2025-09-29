from __future__ import annotations
from datetime import date
from typing import Optional

from ..domain.doc import Doc
from ..domain.value_objects import Provenance
from ..config import ALLOWED_TIPOS, normalize_tipo
from .linker import LinkResult  # will exist when we add spaCy pieces

def make_doc_id(tipo: str, number: Optional[str], year: Optional[str], pdf_name: str) -> str:
    n = (number or "na").strip()
    y = (year or "na").strip()
    return f"{tipo}-{n}-{y}@{pdf_name}"

class DocFactory:
    def build(self, link: LinkResult, pdf_name: str, source_path: str,
              publication_date: Optional[date]) -> Doc:
        # Prefer Sumário info when available
        it = link.item
        sl = link.slice

        tipo = normalize_tipo(it.tipo if it else getattr(sl, "kind", None))
        number = (it.number if it else getattr(sl, "number", None)) or None
        year = (it.year if it else getattr(sl, "year", None)) or None

        if tipo not in ALLOWED_TIPOS:
            tipo = "unknown"

        doc_id = make_doc_id(tipo, number, year, pdf_name)

        body_texto = sl.text
        body_sumario = (it.title if it else "") or ""

        prov = Provenance(body_line_range=(sl.start_line, sl.end_line))

        quality = []
        if link.status != "matched":
            quality.append(f"link:{link.status}")
        if tipo == "unknown":
            quality.append("tipo:unknown")

        return Doc(
            id=doc_id,
            _PdfName=pdf_name,
            _TipoDocumento=tipo,
            _BodyTexto=body_texto,
            _BodySumario=body_sumario,
            _DataDate=publication_date,  # keep None during extraction if you want
            _Entidade=[],
            _DataEntidades=[],
            _DataPessoas=[],
            _DataRelations=[],
            section_body=getattr(sl, "section_body", None),
            header_text=getattr(sl, "header_text", None),
            provenance=prov,
            quality_flags=quality,
        )
