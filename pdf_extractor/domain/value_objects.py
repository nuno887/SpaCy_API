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
