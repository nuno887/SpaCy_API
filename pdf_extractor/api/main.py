# api/main.py
from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import date
import uvicorn

from pdf_extractor.config import Config
from pdf_extractor.services.orchestrator import Pipeline

app = FastAPI(title="PDF Gazette Extractor", version="1.0.0")

# Build long-lived components once (spaCy loads here)
CFG = Config(
    input_root="output",
    output_root="extracted",
    dpi=300,                 # API-friendly default; OCR will still bump quality page-by-page
    ocr_lang="por",
    ignore_top_percent=0.10,
    skip_last_page=True,
)
PIPE = Pipeline(CFG)

@app.post("/extract")
async def extract_pdf(
    pdf: UploadFile = File(...),
    publication_date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) if you want to set it"),
    diagnostics: bool = Query(True, description="Include notes like forced OCR, etc."),
):
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        content = await pdf.read()
        pub_dt = date.fromisoformat(publication_date) if publication_date else None
        result = PIPE.process_pdf_bytes(content, pdf_name=pdf.filename, publication_date=pub_dt)

        # Optionally strip notes if diagnostics=False
        if not diagnostics:
            result = {**result, "notes": []}

        return JSONResponse(content=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Avoid leaking internals; log in real app
        raise HTTPException(status_code=500, detail="Extraction failed")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
