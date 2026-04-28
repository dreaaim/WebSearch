from typing import List, Optional, Tuple
import numpy as np

try:
    from sentence_transformers import CrossEncoder
    HAS_CROSS_ENCODER = True
except ImportError:
    HAS_CROSS_ENCODER = False

from ..core.llm_client import LLMClientBase, create_llm_client
from ..config.settings import Settings


class NLIAnalyzer:
    def __init__(
        self,
        model_name: str = "cross-encoder/nli-deberta-v3-small",
        use_llm_fallback: bool = True,
        llm_client: Optional[LLMClientBase] = None,
        settings: Optional[Settings] = None
    ):
        self._model_name = model_name
        self._use_llm_fallback = use_llm_fallback
        self._cross_encoder = None
        self._llm_client = llm_client
        self._settings = settings

    def _load_cross_encoder(self):
        if not HAS_CROSS_ENCODER:
            return None
        if self._cross_encoder is None:
            self._cross_encoder = CrossEncoder(self._model_name)
        return self._cross_encoder

    def analyze_nli(self, statement1: str, statement2: str) -> str:
        result = self.analyze_nli_sync(statement1, statement2)
        return result

    def analyze_nli_sync(self, statement1: str, statement2: str) -> str:
        model = self._load_cross_encoder()
        if model is not None:
            scores = model.predict([(statement1, statement2)])
            return self._scores_to_label(scores[0])
        if self._use_llm_fallback:
            return self._analyze_with_llm(statement1, statement2)
        return "neutral"

    def analyze_batch(
        self,
        pairs: List[Tuple[str, str]]
    ) -> List[str]:
        return [self.analyze_nli_sync(s1, s2) for s1, s2 in pairs]

    async def analyze_nli_async(self, statement1: str, statement2: str) -> str:
        return self.analyze_nli_sync(statement1, statement2)

    def _scores_to_label(self, scores) -> str:
        if isinstance(scores, np.ndarray):
            scores = scores.tolist()
        if isinstance(scores, (list, tuple)) and len(scores) >= 3:
            label_idx = int(np.argmax(scores))
            labels = ["entailment", "neutral", "contradiction"]
            return labels[label_idx] if label_idx < len(labels) else "neutral"
        if isinstance(scores, (list, tuple)) and len(scores) == 1:
            score = scores[0]
            if score > 0.5:
                return "entailment"
            elif score < -0.5:
                return "contradiction"
            return "neutral"
        return "neutral"

    def _analyze_with_llm(self, statement1: str, statement2: str) -> str:
        if self._llm_client is None:
            if self._settings:
                self._llm_client = create_llm_client(
                    self._settings.model_dump().get("llm", {})
                )
            else:
                self._llm_client = create_llm_client({})

        prompt = f"""Given two statements, determine the NLI relationship:
Statement 1: {statement1}
Statement 2: {statement2}

Classify the relationship as one of:
- entailment: Statement 2 is supported by Statement 1
- neutral: Statement 2 is neither supported nor contradicted by Statement 1
- contradiction: Statement 2 contradicts Statement 1

Respond with only one word: entailment, neutral, or contradiction."""

        try:
            response = self._llm_client.complete_sync(prompt).strip().lower()
            if response in ["entailment", "neutral", "contradiction"]:
                return response
            return "neutral"
        except Exception:
            return "neutral"

    def get_supported_relations(self) -> List[str]:
        return ["entailment", "neutral", "contradiction"]