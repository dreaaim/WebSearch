import os
from typing import List, Dict, Any
import numpy as np

class EmbeddingClientBase:
    @property
    def provider_name(self) -> str:
        return "unknown"

    @property
    def dimension(self) -> int:
        return 1536

    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        raise NotImplementedError

class MockEmbeddingClient(EmbeddingClientBase):
    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        return [np.random.randn(self._dimension) for _ in texts]

class OpenAIEmbeddingClient(EmbeddingClientBase):
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = None,
        batch_size: int = 25
    ):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        results = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            response = self._client.embeddings.create(
                model=self._model,
                input=batch
            )
            for item in response.data:
                results.append(np.array(item.embedding))
        return results

class LocalEmbeddingClient(EmbeddingClientBase):
    def __init__(
        self,
        model_path: str,
        dimension: int = 1024,
        device: str = "cpu",
        batch_size: int = 16
    ):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_path, device=device)
        self._dimension = dimension
        self._batch_size = batch_size

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def dimension(self) -> int:
        return self._dimension

    async def encode(self, texts: List[str]) -> List[np.ndarray]:
        embeddings = self._model.encode(
            texts,
            batch_size=self._batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return [np.array(e) for e in embeddings]

def create_embedding_client(config: Dict[str, Any]) -> EmbeddingClientBase:
    if not config:
        return MockEmbeddingClient()

    local_config = config.get("local", {})
    if local_config.get("enabled", False):
        return LocalEmbeddingClient(
            model_path=local_config["model_path"],
            dimension=local_config.get("dimension", 1024),
            device=local_config.get("device", "cpu"),
            batch_size=local_config.get("batch_size", 16)
        )

    openai_config = config.get("openai", {})

    api_key = openai_config.get("api_key")
    if api_key and api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")

    return OpenAIEmbeddingClient(
        model=openai_config.get("model", "text-embedding-3-small"),
        dimension=openai_config.get("dimension", 1536),
        api_base=openai_config.get("api_base", "https://api.openai.com/v1"),
        api_key=api_key,
        batch_size=openai_config.get("batch_size", 32)
    )
