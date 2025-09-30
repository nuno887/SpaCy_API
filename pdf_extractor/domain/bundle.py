from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any
from .doc import Doc

@dataclass(slots=True)
class PdfBundle:
    pdf_name: str
    source_path: str
    docs: List[Doc] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
        return {
            "pdf_name": self.pdf_name,
            "source_path": self.source_path,
            "notes": list(self.notes),
            "docs": [d.to_json() for d in self.docs],
        }

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "PdfBundle":
        return PdfBundle(
            pdf_name=d["pdf_name"],
            source_path=d["source_path"],
            notes=list(d.get("notes",[])),
            docs=[Doc.from_json(x) for x in d.get("docs",[])],
        )
