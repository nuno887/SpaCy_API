from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import List, Dict, Any, Optional

from .value_objects import Organization, Person, Relation, Provenance
from ..config import ALLOWED_TIPOS

@dataclass(slots=True)
class Doc:
    # Entity (identity by id)
    id: str

    # Core fields
    _PdfName: str
    _TipoDocumento: str
    _BodyTexto: str
    _BodySumario: str
    _DataDate: Optional[date]

    # Enrichment (can be empty at extraction time)
    _Entidade: List[Organization] = field(default_factory=list)
    _DataEntidades: List[Organization] = field(default_factory=list)
    _DataPessoas: List[Person] = field(default_factory=list)
    _DataRelations: List[Relation] = field(default_factory=list)

    # Handy metadata (optional)
    section_body: Optional[str] = None       # owner org (first org from Sumário block)
    section_body_raw: Optional[str] = None   #full multi-line Sumário block
    section_orgs: List[str] = field(default_factory=list) #all orgs parsed from the block (ordered, deduped)

    header_text: Optional[str] = None
    provenance: Optional[Provenance] = None
    quality_flags: List[str] = field(default_factory=list)

    # Equality by id (Entity semantics)
    def __hash__(self) -> int:
        return hash(self.id)
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Doc) and self.id == other.id

    # Lightweight validation (no exceptions here)
    def validate(self) -> List[str]:
        issues: List[str] = []
        if not self._BodyTexto.strip():
            issues.append("BodyTexto is empty")
        if not self._TipoDocumento:
            issues.append("TipoDocumento missing")
        elif self._TipoDocumento not in ALLOWED_TIPOS:
            issues.append(f"TipoDocumento '{self._TipoDocumento}' not in allowed set")
        return issues

    def to_json(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "_PdfName": self._PdfName,
            "_TipoDocumento": self._TipoDocumento,
            "_BodyTexto": self._BodyTexto,
            "_BodySumario": self._BodySumario,
            "_DataDate": self._DataDate.isoformat() if self._DataDate else None,
            "_Entidade": [asdict(o) for o in self._Entidade],
            "_DataEntidades": [asdict(o) for o in self._DataEntidades],
            "_DataPessoas": [asdict(p) for p in self._DataPessoas],
            "_DataRelations": [asdict(r) for r in self._DataRelations],
            "section_body": self.section_body,
            "section_body_raw": self.section_body_raw,
            "section_orgs": list(self.section_orgs),
            "header_text": self.header_text,
            "provenance": asdict(self.provenance) if self.provenance else None,
            "quality_flags": list(self.quality_flags),
        }

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "Doc":
        from .value_objects import Organization, Person, Relation, Provenance
        def map_org(x): return Organization(**x)
        def map_person(x): return Person(**x)
        def map_rel(x): return Relation(**x)
        prov = Provenance(**d["provenance"]) if d.get("provenance") else None
        from datetime import date
        dt = date.fromisoformat(d["_DataDate"]) if d.get("_DataDate") else None
        return Doc(
            id=d["id"],
            _PdfName=d["_PdfName"],
            _TipoDocumento=d["_TipoDocumento"],
            _BodyTexto=d["_BodyTexto"],
            _BodySumario=d.get("_BodySumario",""),
            _DataDate=dt,
            _Entidade=[map_org(x) for x in d.get("_Entidade",[])],
            _DataEntidades=[map_org(x) for x in d.get("_DataEntidades",[])],
            _DataPessoas=[map_person(x) for x in d.get("_DataPessoas",[])],
            _DataRelations=[map_rel(x) for x in d.get("_DataRelations",[])],
            section_body=d.get("section_body"),
            section_body_raw=d.get("section_body_raw"),
            section_orgs=list(d.get("section_orgs", [])),
            header_text=d.get("header_text"),
            provenance=prov,
            quality_flags=list(d.get("quality_flags",[])),
        )
