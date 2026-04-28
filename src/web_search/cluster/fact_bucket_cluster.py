from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import uuid


class NLILabel(Enum):
    ENTAILMENT = "entailment"
    NEUTRAL = "neutral"
    CONTRADICTION = "contradiction"


@dataclass
class SPOTriple:
    subject: str
    predicate: str
    object: str

    def __hash__(self):
        return hash((self.subject, self.predicate, self.object))


@dataclass
class NumericValue:
    value: float
    unit: Optional[str] = None
    context: Optional[str] = None


@dataclass
class DatetimeValue:
    value: str
    parsed_date: Optional[str] = None
    context: Optional[str] = None


@dataclass
class ExtractedFact:
    fact_id: str
    statement: str
    spo_triple: Optional[SPOTriple] = None
    nli_label: Optional[NLILabel] = None
    numeric_values: List[NumericValue] = field(default_factory=list)
    datetime_values: List[DatetimeValue] = field(default_factory=list)
    confidence_score: float = 0.0
    confidence_reason: Optional[str] = None
    source_domain: Optional[str] = None
    source_name: Optional[str] = None

    @staticmethod
    def generate_id() -> str:
        return str(uuid.uuid4())


@dataclass
class FactBucket:
    bucket_id: str
    facts: List[ExtractedFact]
    cluster_embedding: List[float]

    @staticmethod
    def generate_id() -> str:
        return str(uuid.uuid4())[:8]


class FactBucketCluster:
    def __init__(
        self,
        embedding_client=None,
        similarity_threshold: float = 0.75,
        use_hierarchical: bool = True
    ):
        self._embedding_client = embedding_client
        self._similarity_threshold = similarity_threshold
        self._use_hierarchical = use_hierarchical

    async def cluster(self, facts: List[ExtractedFact]) -> List[FactBucket]:
        if not facts:
            return []

        if len(facts) == 1:
            embedding = await self._compute_embedding([facts[0].statement])
            return [FactBucket(
                bucket_id=FactBucket.generate_id(),
                facts=facts,
                cluster_embedding=embedding[0].tolist()
            )]

        statements = [f.statement for f in facts]
        embeddings = await self._compute_embedding(statements)

        similarity_matrix = self._compute_similarity_matrix(embeddings)

        if self._use_hierarchical:
            clusters = self._hierarchical_clustering(similarity_matrix, facts, embeddings)
        else:
            clusters = self._greedy_clustering(similarity_matrix, facts, embeddings)

        result = []
        for cluster_facts, cluster_emb in clusters:
            result.append(FactBucket(
                bucket_id=FactBucket.generate_id(),
                facts=cluster_facts,
                cluster_embedding=cluster_emb.tolist()
            ))

        return result

    def cluster_sync(self, facts: List[ExtractedFact]) -> List[FactBucket]:
        if not facts:
            return []

        if len(facts) == 1:
            embedding = self._compute_embedding_sync([facts[0].statement])
            return [FactBucket(
                bucket_id=FactBucket.generate_id(),
                facts=facts,
                cluster_embedding=embedding[0].tolist()
            )]

        statements = [f.statement for f in facts]
        embeddings = self._compute_embedding_sync(statements)

        similarity_matrix = self._compute_similarity_matrix(embeddings)

        if self._use_hierarchical:
            clusters = self._hierarchical_clustering(similarity_matrix, facts, embeddings)
        else:
            clusters = self._greedy_clustering(similarity_matrix, facts, embeddings)

        result = []
        for cluster_facts, cluster_emb in clusters:
            result.append(FactBucket(
                bucket_id=FactBucket.generate_id(),
                facts=cluster_facts,
                cluster_embedding=cluster_emb.tolist()
            ))

        return result

    async def _compute_embedding(self, texts: List[str]) -> List:
        if self._embedding_client is not None:
            return await self._embedding_client.encode(texts)
        from ..core.embedding_client import create_embedding_client
        client = create_embedding_client({})
        return await client.encode(texts)

    def _compute_embedding_sync(self, texts: List[str]) -> List:
        if self._embedding_client is not None:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._embedding_client.encode(texts))
        from ..core.embedding_client import create_embedding_client
        client = create_embedding_client({})
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(client.encode(texts))

    def _compute_similarity_matrix(self, embeddings: List) -> List[List[float]]:
        n = len(embeddings)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                sim = self._cosine_similarity(embeddings[i], embeddings[j])
                matrix[i][j] = sim
                matrix[j][i] = sim
        return matrix

    def _cosine_similarity(self, vec1, vec2) -> float:
        import numpy as np
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))

    def _hierarchical_clustering(
        self,
        similarity_matrix: List[List[float]],
        facts: List[ExtractedFact],
        embeddings: List
    ) -> List[tuple]:
        n = len(facts)
        if n == 0:
            return []

        import numpy as np
        similarity_matrix = np.array(similarity_matrix)
        np.clip(similarity_matrix, 0, 1, out=similarity_matrix)
        distance_matrix = 1 - similarity_matrix
        np.fill_diagonal(distance_matrix, 0)

        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform

        condensed_dist = squareform(distance_matrix)
        Z = linkage(condensed_dist, method='average')

        clusters = fcluster(Z, t=1 - self._similarity_threshold, criterion='distance')

        cluster_map = {}
        for idx, cluster_id in enumerate(clusters):
            if cluster_id not in cluster_map:
                cluster_map[cluster_id] = []
            cluster_map[cluster_id].append(idx)

        result = []
        for cluster_id, indices in cluster_map.items():
            cluster_facts = [facts[i] for i in indices]
            cluster_embs = [embeddings[i] for i in indices]
            centroid = np.mean(cluster_embs, axis=0)
            result.append((cluster_facts, centroid))

        return result

    def _greedy_clustering(
        self,
        similarity_matrix: List[List[float]],
        facts: List[ExtractedFact],
        embeddings: List
    ) -> List[tuple]:
        n = len(facts)
        if n == 0:
            return []

        assigned = [False] * n
        clusters = []

        for i in range(n):
            if assigned[i]:
                continue

            cluster_indices = [i]
            assigned[i] = True

            for j in range(i + 1, n):
                if assigned[j]:
                    continue
                sim = similarity_matrix[i][j]
                if sim >= self._similarity_threshold:
                    cluster_indices.append(j)
                    assigned[j] = True

            cluster_facts = [facts[idx] for idx in cluster_indices]
            cluster_embs = [embeddings[idx] for idx in cluster_indices]

            import numpy as np
            centroid = np.mean(cluster_embs, axis=0)
            clusters.append((cluster_facts, centroid))

        unassigned = [i for i in range(n) if not assigned[i]]
        for idx in unassigned:
            clusters.append(([facts[idx]], embeddings[idx]))

        return clusters