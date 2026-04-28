from typing import List
import math

class BM25Scorer:
    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        avg_doc_len: float = None
    ):
        self._k1 = k1
        self._b = b
        self._avg_doc_len = avg_doc_len
        self._doc_freqs: dict = {}
        self._doc_len = 0
        self._num_docs = 0
        self._vocab: set = set()
        self._total_doc_len = 0

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def _compute_avg_doc_len(self, texts: List[str]) -> float:
        if not texts:
            return 0.0
        total_len = sum(len(self._tokenize(t)) for t in texts)
        return total_len / len(texts)

    def fit(self, texts: List[str]):
        self._num_docs = len(texts)
        self._doc_freqs = {}
        self._total_doc_len = 0

        for text in texts:
            tokens = self._tokenize(text)
            self._doc_len = len(tokens)
            self._total_doc_len += self._doc_len
            unique_tokens = set(tokens)

            for token in unique_tokens:
                if token not in self._doc_freqs:
                    self._doc_freqs[token] = 0
                self._doc_freqs[token] += 1

        self._avg_doc_len = self._total_doc_len / self._num_docs if self._num_docs > 0 else 0
        self._vocab = set(self._doc_freqs.keys())

    def compute_bm25_score(self, query: str, text: str) -> float:
        if not hasattr(self, '_num_docs') or self._num_docs == 0:
            self.fit([text])

        tokens = self._tokenize(text)
        doc_len = len(tokens)
        score = 0.0

        for term in self._tokenize(query):
            if term not in self._vocab:
                continue

            df = self._doc_freqs.get(term, 0)
            if df == 0:
                continue

            idf = math.log((self._num_docs - df + 0.5) / (df + 0.5) + 1)
            tf = tokens.count(term)
            tf_component = (tf * (self._k1 + 1)) / (tf + self._k1 * (1 - self._b + self._b * doc_len / (self._avg_doc_len + 1e-8)))
            score += idf * tf_component

        return score

    def compute_batch_scores(
        self,
        query: str,
        texts: List[str]
    ) -> List[float]:
        if not texts:
            return []

        self.fit(texts)

        scores = []
        for text in texts:
            score = self.compute_bm25_score(query, text)
            scores.append(score)
        return scores