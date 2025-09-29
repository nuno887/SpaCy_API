# pdf_extractor/cli/extract.py  (replace main() body with this flow)
from __future__ import annotations
import argparse
from pathlib import Path
from ..config import Config
from ..domain.bundle import PdfBundle
from ..io.repository import save_bundle
from ..io.validators import validate_bundle
from ..services.gazette_nlp import GazetteNLP
from ..services.sumario import SumarioParser
from ..services.slicer import BodySlicer
from ..services.linker import Linker
from ..services.factory import DocFactory

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", default="output")
    ap.add_argument("--output-root", default="extracted")
    args = ap.parse_args()

    cfg = Config(input_root=args.input_root, output_root=args.output_root)

    input_root = Path(cfg.input_root)
    out_root = Path(cfg.output_root)
    out_root.mkdir(parents=True, exist_ok=True)

    # Build spaCy-based helpers
    gnlp = GazetteNLP()
    sumario = SumarioParser(gnlp)
    slicer = BodySlicer(gnlp)
    linker = Linker()
    factory = DocFactory()

    processed = 0
    for stem in sorted(p for p in input_root.iterdir() if p.is_dir()):
        completo = stem / "completo.txt"
        if not completo.exists():
            continue

        # Read combined text (from your earlier extractor)
        lines = completo.read_text(encoding="utf-8", errors="ignore").splitlines()

        # Sumário detection + items
        sum_start, sum_end = sumario.find_range(lines)
        sum_lines = lines[sum_start:sum_end] if (sum_start is not None and sum_end is not None) else []
        items = sumario.parse_items(sum_lines)

        # Body headers & slices
        exclude = (sum_start, sum_end) if (sum_start is not None and sum_end is not None) else None
        header_lines = slicer.detect_headers(lines, exclude)
        slices = slicer.slices(lines, header_lines)

        # Link & build docs
        links = linker.link(items, slices)
        docs = [factory.build(lk, pdf_name=f"{stem.name}.pdf", source_path=str(completo), publication_date=None)
                for lk in links]

        bundle = PdfBundle(pdf_name=f"{stem.name}.pdf", source_path=str(completo), docs=docs, notes=[])

        # Validate and save
        issues = validate_bundle(bundle)
        if issues:
            print(f"[{stem.name}] Warnings: {issues}")
        save_bundle(bundle, dest_root=cfg.output_root)
        processed += 1

    print(f"Processed {processed} PDF stems.")

if __name__ == "__main__":
    main()
