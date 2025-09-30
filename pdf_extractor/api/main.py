# api/main.py
from __future__ import annotations
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import logging

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
    pdf: UploadFile = File(...)):

    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        content = await pdf.read()

        # run the pipeline (no date, no diagnostics)
        bundle = PIPE.process_pdf_bytes(content, pdf_name=pdf.filename, publication_date=None)

        # return ONLY docs; omit notes/source_path/etc.
        return JSONResponse(content={"docs": bundle.get("docs", [])})

      
    except ValueError as e:
        # bad input (corrupt pdf, etc.)
        logging.exception("Bad request during extraction")
        raise HTTPException(status_code=400, detail=f"Bad request: {e.__class__.__name__}: {e}")
    except Exception as e:
        # log full stack trace and surface the exact error type + message
        logging.exception("Extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e.__class__.__name__}: {e}")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
    
# uvicorn pdf_extractor.api.main:app --reload --host 0.0.0.0 --port 8000