from __future__ import annotations
from typing import List
from ..domain.doc import Doc
from ..domain.bundle import PdfBundle

def validate_doc(doc: Doc) -> List[str]:
    return doc.validate()

def validate_bundle(bundle: PdfBundle) -> List[str]:
    issues: List[str] = []
    if bundle.pdf_name.strip() == "":
        issues.append("Bundle pdf_name empty")
    if not bundle.source_path:
        issues.append("Bundle source_path empty")
    if not bundle.docs:
        issues.append("Bundle has no docs")
    for d in bundle.docs:
        issues.extend(validate_doc(d))
    return issues
