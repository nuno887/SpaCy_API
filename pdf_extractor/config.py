from dataclasses import dataclass
import unicodedata

@dataclass(slots=True)
class Config:
    input_root: str = "output"                   # where <pdf-stem>/completo.txt lives
    output_root: str = "extracted"
    dpi: int = 600
    ocr_lang: str = "por"
    ignore_top_percent: float = 0.10
    skip_last_page: bool = True

ALLOWED_TIPOS = {
    "despacho","aviso","declaracao","edital","deliberacao",
    "contrato","resolucao","revogacao","caducidade","ato","acto"
}


def normalize_tipo(s: str | None) -> str:
    if not s:
        return "unknown"
    s_norm = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower().strip()
    return s_norm if s_norm in ALLOWED_TIPOS else "unknown"