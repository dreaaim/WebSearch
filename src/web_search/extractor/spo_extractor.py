from dataclasses import dataclass
from typing import List, Optional
import re

try:
    import spacy
    from spacy.language import Language
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    Language = None

from ..core.llm_client import LLMClientBase, create_llm_client
from ..config.settings import Settings


@dataclass
class SPOTriple:
    subject: str
    predicate: str
    object: str

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object
        }

    def __str__(self) -> str:
        return f"{self.subject} | {self.predicate} | {self.object}"


class SPOExtractor:
    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        use_llm_fallback: bool = True,
        llm_client: Optional[LLMClientBase] = None,
        settings: Optional[Settings] = None
    ):
        self._spacy_model = spacy_model
        self._use_llm_fallback = use_llm_fallback
        self._nlp = None
        self._llm_client = llm_client
        self._settings = settings

    def _load_spacy(self):
        if not HAS_SPACY:
            return None
        if self._nlp is None:
            try:
                self._nlp = spacy.load(self._spacy_model)
            except OSError:
                try:
                    self._nlp = spacy.load("en_core_web_sm")
                except OSError:
                    return None
        return self._nlp

    def extract_spo(self, text: str) -> List[SPOTriple]:
        return self.extract_spo_sync(text)

    def extract_spo_sync(self, text: str) -> List[SPOTriple]:
        nlp = self._load_spacy()
        if nlp is not None:
            return self._extract_with_spacy(text)
        if self._use_llm_fallback:
            return self._extract_with_llm(text)
        return self._extract_simple_patterns(text)

    def _extract_with_spacy(self, text: str) -> List[SPOTriple]:
        triples: List[SPOTriple] = []
        doc = self._nlp(text)

        for sent in doc.sents:
            subject = None
            predicate = None
            obj = None

            for token in sent:
                if token.dep_ in ("nsubj", "nsubjpass"):
                    subject = self._get_subtree_text(token)
                elif token.dep_ == "ROOT":
                    predicate = token.lemma_
                elif token.dep_ in ("dobj", "pobj", "attr"):
                    obj = self._get_subtree_text(token)

            if subject and predicate and obj:
                triples.append(SPOTriple(
                    subject=self._clean_text(subject),
                    predicate=self._clean_text(predicate),
                    object=self._clean_text(obj)
                ))

        if not triples:
            for ent1 in doc.ents:
                for ent2 in doc.ents:
                    if ent1.end <= ent2.start:
                        triples.append(SPOTriple(
                            subject=ent1.text,
                            predicate="related_to",
                            object=ent2.text
                        ))
                        break

        return triples

    def _get_subtree_text(self, token) -> str:
        subtree_tokens = sorted(token.subtree, key=lambda t: t.i)
        return " ".join(t.text for t in subtree_tokens)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_simple_patterns(self, text: str) -> List[SPOTriple]:
        triples: List[SPOTriple] = []

        patterns = [
            r'([A-Z][a-zA-Z\s]+)\s+(is|are|was|were|will be|can be|could be)\s+([^.!?]+)',
            r'([A-Z][a-zA-Z\s]+)\s+(announced|reported|revealed|confirmed|stated)\s+([^.!?]+)',
            r'([A-Z][a-zA-Z\s]+)\s+(\w+ed|\w+es)\s+([^.!?]+)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                subject = match.group(1).strip()
                predicate = match.group(2).strip()
                obj = match.group(3).strip()
                if len(subject) > 1 and len(obj) > 1:
                    triples.append(SPOTriple(
                        subject=self._clean_text(subject),
                        predicate=self._clean_text(predicate),
                        object=self._clean_text(obj)
                    ))

        return triples

    def _extract_with_llm(self, text: str) -> List[SPOTriple]:
        if self._llm_client is None:
            if self._settings:
                self._llm_client = create_llm_client(
                    self._settings.model_dump().get("llm", {})
                )
            else:
                self._llm_client = create_llm_client({})

        prompt = f"""Extract Subject-Predicate-Object triples from the following text.
Return the triples in the format: subject | predicate | object
One triple per line. If no triples found, return "NONE".

Text: {text}

Triples:"""

        try:
            response = self._llm_client.complete_sync(prompt)
            return self._parse_llm_response(response)
        except Exception:
            return self._extract_simple_patterns(text)

    def _parse_llm_response(self, response: str) -> List[SPOTriple]:
        triples: List[SPOTriple] = []
        lines = response.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.upper() == "NONE":
                continue
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    triples.append(SPOTriple(
                        subject=parts[0],
                        predicate=parts[1],
                        object=parts[2]
                    ))

        return triples

    async def extract_spo_async(self, text: str) -> List[SPOTriple]:
        return self.extract_spo_sync(text)