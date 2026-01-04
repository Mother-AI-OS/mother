"""Embedding generation for semantic memory search."""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger("mother.memory")


class EmbeddingCache:
    """Simple file-based cache for embeddings to reduce API calls."""

    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".local" / "share" / "mother" / "embedding_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_key(self, text: str, model: str) -> str:
        """Generate cache key from text and model."""
        content = f"{model}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, text: str, model: str) -> list[float] | None:
        """Get cached embedding if exists."""
        key = self._get_key(text, model)
        cache_file = self.cache_dir / f"{key}.json"

        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def set(self, text: str, model: str, embedding: list[float]):
        """Cache an embedding."""
        key = self._get_key(text, model)
        cache_file = self.cache_dir / f"{key}.json"

        try:
            with open(cache_file, "w") as f:
                json.dump(embedding, f)
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")


class EmbeddingGenerator:
    """Generate embeddings using OpenAI API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        use_cache: bool = True,
    ):
        self.api_key = api_key
        self.model = model
        self.cache = EmbeddingCache() if use_cache else None
        self._client = None

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def generate(self, text: str) -> list[float] | None:
        """Generate embedding for text."""
        if not text or not text.strip():
            return None

        # Check cache first
        if self.cache:
            cached = self.cache.get(text, self.model)
            if cached:
                return cached

        try:
            # Truncate very long texts (OpenAI has token limits)
            max_chars = 8000  # Safe limit for most texts
            truncated = text[:max_chars] if len(text) > max_chars else text

            response = self.client.embeddings.create(
                model=self.model,
                input=truncated,
            )

            embedding = response.data[0].embedding

            # Cache the result
            if self.cache:
                self.cache.set(text, self.model, embedding)

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def generate_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts."""
        results = []

        # Check cache for all texts first
        uncached_indices = []
        uncached_texts = []

        for i, text in enumerate(texts):
            if not text or not text.strip():
                results.append(None)
                continue

            if self.cache:
                cached = self.cache.get(text, self.model)
                if cached:
                    results.append(cached)
                    continue

            results.append(None)  # Placeholder
            uncached_indices.append(i)
            uncached_texts.append(text[:8000])  # Truncate

        # Generate embeddings for uncached texts
        if uncached_texts:
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=uncached_texts,
                )

                for j, embedding_data in enumerate(response.data):
                    idx = uncached_indices[j]
                    embedding = embedding_data.embedding
                    results[idx] = embedding

                    # Cache the result
                    if self.cache:
                        self.cache.set(texts[idx], self.model, embedding)

            except Exception as e:
                logger.error(f"Failed to generate batch embeddings: {e}")

        return results
