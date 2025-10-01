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
        #Texts (guard when no body anchor)
        body_texto = sl.text if sl else ""
        body_sumario =" ".join([s for s in ([it.text] if it else []) + ([it.title] if it and it.title else [])]).strip()

        prov = Provenance(body_line_range=((sl.start_line, sl.end_line) if sl else (it.line_range if it else None)))

        quality = []
        if link.status == "matched":
            quality.append("link:matched")
        else:
            quality.append("link:no_body_anchor")
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
            # Organization solely from Sumário (fallback to body section only if item missing)
            section_body=(getattr(it, "section_sumario", None) if it else getattr(sl, "section_body", None)),
            section_body_raw=(getattr(it, "section_sumario_raw", None) if it else None),
            section_orgs=(list(getattr(it, "section_orgs", ())) if it else []),
            header_text=(sl.header_text if sl else (it.text if it else None)),

        

            provenance=prov,
            quality_flags=quality,
        )
