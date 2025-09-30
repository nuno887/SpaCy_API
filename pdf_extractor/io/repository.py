from __future__ import annotations
import json
from pathlib import Path
from ..domain.bundle import PdfBundle

def save_bundle(bundle: PdfBundle, dest_root: str) -> None:
    root = Path(dest_root) / Path(bundle.source_path).parent.name
    docs_dir = root / "docs"
    root.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # write bundle.json
    (root / "bundle.json").write_text(json.dumps(bundle.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")

    # write each doc’s body to a file (ordinal ordering)
    for idx, d in enumerate(bundle.docs, start=1):
        stem = f"{idx:04d}-{d._TipoDocumento}.txt"
        (docs_dir / stem).write_text(d._BodyTexto, encoding="utf-8")
