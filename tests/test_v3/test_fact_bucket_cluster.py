import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock, patch


def create_fact(fact_id, statement):
    from web_search.cluster.fact_bucket_cluster import ExtractedFact
    return ExtractedFact(
        fact_id=fact_id,
        statement=statement,
        confidence_score=1.0
    )


class MockEmbeddingClient:
    def __init__(self, embeddings=None):
        self._embeddings = embeddings or []

    async def encode(self, texts):
        return [np.array(e) for e in self._embeddings[:len(texts)]]

    def encode_sync(self, texts):
        return [np.array(e) for e in self._embeddings[:len(texts)]]


class TestClusterEmbeddingSimilarity:
    def setup_method(self):
        self.embedding1 = [1.0, 0.0, 0.0]
        self.embedding2 = [1.0, 0.0, 0.0]
        self.embedding3 = [0.0, 1.0, 0.0]

    def test_cluster_embedding_similarity(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            mock_client = MockEmbeddingClient([
                np.array(self.embedding1),
                np.array(self.embedding2),
                np.array(self.embedding3)
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            facts = [
                create_fact("f1", "Beijing is the capital of China"),
                create_fact("f2", "Beijing is the capital of China"),
                create_fact("f3", "The weather is sunny today")
            ]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert len(result) >= 1
            for bucket in result:
                assert bucket.cluster_embedding is not None
                assert len(bucket.cluster_embedding) == 3


class TestClusterHierarchicalAlgorithm:
    def setup_method(self):
        self.embedding1 = [1.0, 0.0, 0.0]
        self.embedding2 = [0.95, 0.05, 0.0]
        self.embedding3 = [0.0, 1.0, 0.0]
        self.embedding4 = [0.0, 0.95, 0.05]

    def test_cluster_hierarchical_algorithm(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            mock_client = MockEmbeddingClient([
                np.array(self.embedding1),
                np.array(self.embedding2),
                np.array(self.embedding3),
                np.array(self.embedding4)
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            facts = [
                create_fact("f1", "Statement about technology"),
                create_fact("f2", "Statement about technology similar"),
                create_fact("f3", "Statement about weather"),
                create_fact("f4", "Statement about weather similar")
            ]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert len(result) >= 2
            total_facts = sum(len(bucket.facts) for bucket in result)
            assert total_facts == 4

    def test_hierarchical_clustering_groups_similar_facts(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            identical_emb = [0.9, 0.1, 0.0]
            mock_client = MockEmbeddingClient([
                np.array(identical_emb),
                np.array(identical_emb),
                np.array([0.1, 0.9, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.8,
                use_hierarchical=True
            )

            facts = [
                create_fact("f1", "Same statement"),
                create_fact("f2", "Same statement"),
                create_fact("f3", "Different statement")
            ]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            similar_bucket = None
            for bucket in result:
                if len(bucket.facts) == 2:
                    similar_bucket = bucket
                    break

            assert similar_bucket is not None
            assert len(similar_bucket.facts) == 2


class TestClusterGreedyAlgorithm:
    def setup_method(self):
        pass

    def test_cluster_greedy_algorithm(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            mock_client = MockEmbeddingClient([
                np.array([1.0, 0.0, 0.0]),
                np.array([0.9, 0.1, 0.0]),
                np.array([0.0, 1.0, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=False
            )

            facts = [
                create_fact("f1", "Statement A"),
                create_fact("f2", "Statement A similar"),
                create_fact("f3", "Statement B")
            ]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert len(result) >= 1
            total_facts = sum(len(bucket.facts) for bucket in result)
            assert total_facts == 3

    def test_greedy_clustering_unassigned_becomes_singleton(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            mock_client = MockEmbeddingClient([
                np.array([1.0, 0.0, 0.0]),
                np.array([0.0, 0.0, 1.0]),
                np.array([0.0, 1.0, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.9,
                use_hierarchical=False
            )

            facts = [
                create_fact("f1", "Cluster A"),
                create_fact("f2", "Cluster B"),
                create_fact("f3", "Cluster C")
            ]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert len(result) == 3
            for bucket in result:
                assert len(bucket.facts) == 1


class TestClusterThresholdControl:
    def setup_method(self):
        pass

    def test_cluster_threshold_control(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            similar_emb = [0.9, 0.1, 0.0]
            mock_client = MockEmbeddingClient([
                np.array(similar_emb),
                np.array(similar_emb),
                np.array([0.0, 0.9, 0.1])
            ])

            low_threshold_cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.5,
                use_hierarchical=True
            )

            high_threshold_cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.95,
                use_hierarchical=True
            )

            facts = [
                create_fact("f1", "Statement 1"),
                create_fact("f2", "Statement 2"),
                create_fact("f3", "Statement 3")
            ]

            import asyncio
            low_result = asyncio.get_event_loop().run_until_complete(
                low_threshold_cluster.cluster(facts)
            )
            high_result = asyncio.get_event_loop().run_until_complete(
                high_threshold_cluster.cluster(facts)
            )

            assert len(low_result) <= len(high_result)


class TestClusterReturnsListOfBuckets:
    def setup_method(self):
        pass

    def test_cluster_returns_list_of_buckets(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster, FactBucket

            mock_client = MockEmbeddingClient([
                np.array([1.0, 0.0, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            facts = [create_fact("f1", "Single fact statement")]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], FactBucket)
            assert result[0].bucket_id is not None
            assert len(result[0].facts) == 1
            assert result[0].cluster_embedding is not None

    def test_cluster_returns_empty_list_for_empty_input(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster

            mock_client = MockEmbeddingClient()

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster([]))

            assert isinstance(result, list)
            assert len(result) == 0

    def test_cluster_single_fact_returns_single_bucket(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster, FactBucket

            mock_client = MockEmbeddingClient([
                np.array([0.5, 0.5, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            facts = [create_fact("f1", "Only one fact")]

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(cluster.cluster(facts))

            assert len(result) == 1
            assert isinstance(result[0], FactBucket)
            assert result[0].facts[0].fact_id == "f1"


class TestClusterSync:
    def setup_method(self):
        pass

    def test_cluster_sync_returns_list_of_buckets(self):
        with patch('web_search.core.embedding_client.create_embedding_client'):
            from web_search.cluster.fact_bucket_cluster import FactBucketCluster, FactBucket

            mock_client = MockEmbeddingClient([
                np.array([1.0, 0.0, 0.0])
            ])

            cluster = FactBucketCluster(
                embedding_client=mock_client,
                similarity_threshold=0.75,
                use_hierarchical=True
            )

            facts = [create_fact("f1", "Sync test fact")]

            result = cluster.cluster_sync(facts)

            assert isinstance(result, list)
            assert len(result) == 1
            assert isinstance(result[0], FactBucket)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])