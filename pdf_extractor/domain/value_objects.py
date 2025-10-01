from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Union

@dataclass(frozen=True, slots=True)
class Organization:
    name: str
    kind: Optional[str] = None
    confidence: Optional[float] = None

@dataclass(frozen=True, slots=True)
class Person:
    name: str
    role: Optional[str] = None
    confidence: Optional[float] = None

@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    text: str

@dataclass(frozen=True, slots=True)
class Provenance:
    body_line_range: Optional[Tuple[int, int]] = None
    pdf_page_start: Optional[int] = None
    pdf_page_end: Optional[int] = None

Subject = Union[str, Organization, Person]
ObjectT = Union[str, Organization, Person]

@dataclass(frozen=True, slots=True)
class Relation:
    subject: Subject
    predicate: str
    object: ObjectT
    evidence_span: Optional[Span] = None

@dataclass(frozen= True, slots=True)
class SumarioDoc:
    doc_name: str   # normalized key, e.g. "despacho 216/2025"
    header_text: str    # raw Sumário header line
    title: str  # ALL lines until next item/org (joined with "\n")
    orgs: Tuple[str, ...] = ()  # all orgs parsed from the Sumário block (first = owner)
    org_block_raw: Optional[str] = None

    @property
    def primary_org(self) -> Optional[str]:
        return self.orgs[0] if self.orgs else None

    @property
    def text(self) -> str:
        return (self.header_text + ("\n" + self.title if self.title else "")).strip()
