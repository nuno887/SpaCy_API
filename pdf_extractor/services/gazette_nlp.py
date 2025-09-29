from __future__ import annotations
from typing import Optional, List
import unicodedata
import spacy
from spacy.language import Language
from spacy.pipeline import EntityRuler
from spacy.matcher import Matcher
from ..config import ALLOWED_TIPOS

def ascii_lower(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode("ascii").lower().strip()

class GazetteNLP:
    def __init__(self, nlp: Optional[Language] = None):
        self.nlp = nlp or self._build_pipeline()
        self.matcher = Matcher(self.nlp.vocab)
        self._add_org_head_patterns()

    def _build_pipeline(self) -> Language:
        # Prefer Portuguese model if available; else blank 'pt'
        for name in ("pt_core_news_lg","pt_core_news_md","pt_core_news_sm"):
            try:
                return self._with_rules(spacy.load(name))
            except Exception:
                continue
        return self._with_rules(spacy.blank("pt"))

    def _with_rules(self, nlp: Language) -> Language:
        if "sentencizer" not in nlp.pipe_names and "parser" not in nlp.pipe_names:
            nlp.add_pipe("sentencizer")
        # bootstrap ruler so later you can replace with your trained NER
        ruler = nlp.add_pipe("entity_ruler", name="gazette_ruler", config={"overwrite_ents": True})
        ruler.add_patterns(self._kind_patterns())
        ruler.add_patterns(self._num_year_patterns())
        return nlp

    def _kind_patterns(self) -> List[dict]:
        # tag KIND on your controlled tipos (ASCII/lowercase matching via LOWER)
        kinds = sorted(ALLOWED_TIPOS)
        return [{"label":"KIND","pattern":[{"LOWER":k}]} for k in kinds]

    def _num_year_patterns(self) -> List[dict]:
        # DOC_NUM: numeric token(s) (we keep it simple; training can do better later)
        # DOC_YEAR: 4-digit number in a plausible range (filter in code)
        return [
            {"label":"DOC_NUM", "pattern":[{"LIKE_NUM":True}]},
            {"label":"DOC_YEAR","pattern":[{"LIKE_NUM":True}]},
        ]

    def _add_org_head_patterns(self):
        # ORG_HEAD via Matcher: runs of uppercase alphabetic tokens, with optional hyphen or short preps
        # Example: "CÂMARA MUNICIPAL DE LISBOA", "DIREÇÃO-GERAL DA SAÚDE"
        # Pattern 1: UPPER+ (allow several tokens)
        self.matcher.add("ORG_HEAD", [[{"IS_ALPHA":True, "IS_UPPER":True, "OP":"+"}]])
        # Pattern 2: UPPER+ - UPPER+
        self.matcher.add("ORG_HEAD", [[
            {"IS_ALPHA":True, "IS_UPPER":True, "OP":"+"},
            {"TEXT":"-"},
            {"IS_ALPHA":True, "IS_UPPER":True, "OP":"+"},
        ]])

    # helpers
    def is_org_heading(self, text: str) -> bool:
        doc = self.nlp.make_doc(text.strip())
        matches = self.matcher(doc)
        # Heuristic: treat as org heading if match exists and the line has letters and mostly uppercase
        if not matches:
            return False
        letters = [ch for ch in text if ch.isalpha()]
        if not letters:
            return False
        upp = sum(1 for ch in letters if ch.isupper())
        return upp / max(1, len(letters)) > 0.75
