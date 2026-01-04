"""Tests for the memory embeddings module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mother.memory.embeddings import EmbeddingCache, EmbeddingGenerator


class TestEmbeddingCache:
    """Tests for EmbeddingCache class."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create a cache with temporary directory."""
        return EmbeddingCache(cache_dir=tmp_path)

    def test_init_creates_directory(self, tmp_path):
        """Test cache directory is created."""
        cache_dir = tmp_path / "embeddings"
        cache = EmbeddingCache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_get_key_generates_hash(self, cache):
        """Test _get_key generates consistent hash."""
        key1 = cache._get_key("test text", "model-1")
        key2 = cache._get_key("test text", "model-1")
        key3 = cache._get_key("different", "model-1")

        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32

    def test_get_key_includes_model(self, cache):
        """Test _get_key varies by model."""
        key1 = cache._get_key("test", "model-1")
        key2 = cache._get_key("test", "model-2")

        assert key1 != key2

    def test_set_and_get(self, cache):
        """Test setting and getting embeddings."""
        embedding = [0.1, 0.2, 0.3]
        cache.set("test text", "test-model", embedding)
        result = cache.get("test text", "test-model")

        assert result == embedding

    def test_get_not_cached(self, cache):
        """Test getting non-existent embedding."""
        result = cache.get("uncached", "model")
        assert result is None

    def test_set_creates_file(self, cache, tmp_path):
        """Test set creates cache file."""
        cache.set("test", "model", [0.1, 0.2])

        files = list(tmp_path.glob("*.json"))
        assert len(files) == 1

    def test_cache_persistence(self, tmp_path):
        """Test cache persists across instances."""
        cache1 = EmbeddingCache(cache_dir=tmp_path)
        cache1.set("text", "model", [0.5, 0.5])

        cache2 = EmbeddingCache(cache_dir=tmp_path)
        result = cache2.get("text", "model")

        assert result == [0.5, 0.5]

    def test_get_handles_corrupt_file(self, cache, tmp_path):
        """Test get handles corrupt cache file."""
        key = cache._get_key("corrupt", "model")
        cache_file = tmp_path / f"{key}.json"
        cache_file.write_text("not valid json{")

        result = cache.get("corrupt", "model")
        assert result is None


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a generator with mocked cache."""
        return EmbeddingGenerator(api_key="test-key", use_cache=False)

    @pytest.fixture
    def generator_with_cache(self, tmp_path):
        """Create a generator with real cache."""
        gen = EmbeddingGenerator(api_key="test-key", use_cache=True)
        gen.cache = EmbeddingCache(cache_dir=tmp_path)
        return gen

    def test_init_with_cache(self):
        """Test initialization with cache enabled."""
        gen = EmbeddingGenerator(api_key="test", use_cache=True)
        assert gen.cache is not None

    def test_init_without_cache(self):
        """Test initialization with cache disabled."""
        gen = EmbeddingGenerator(api_key="test", use_cache=False)
        assert gen.cache is None

    def test_init_default_model(self):
        """Test default model is set."""
        gen = EmbeddingGenerator()
        assert gen.model == "text-embedding-3-small"

    def test_init_custom_model(self):
        """Test custom model."""
        gen = EmbeddingGenerator(model="text-embedding-ada-002")
        assert gen.model == "text-embedding-ada-002"

    def test_generate_empty_text(self, generator):
        """Test generate returns None for empty text."""
        assert generator.generate("") is None
        assert generator.generate("   ") is None
        assert generator.generate(None) is None if hasattr(generator, "generate") else True

    def test_generate_uses_cache(self, generator_with_cache):
        """Test generate uses cache when available."""
        cached_embedding = [0.1, 0.2, 0.3]
        generator_with_cache.cache.set("test text", generator_with_cache.model, cached_embedding)

        result = generator_with_cache.generate("test text")
        assert result == cached_embedding

    def test_generate_calls_api(self, generator):
        """Test generate calls OpenAI API."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        generator._client = mock_client

        result = generator.generate("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    def test_generate_truncates_long_text(self, generator):
        """Test generate truncates long text."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1])]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        generator._client = mock_client

        long_text = "x" * 10000
        generator.generate(long_text)

        call_args = mock_client.embeddings.create.call_args
        assert len(call_args[1]["input"]) <= 8000

    def test_generate_caches_result(self, generator_with_cache):
        """Test generate caches the result."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        generator_with_cache._client = mock_client

        generator_with_cache.generate("cache test")

        # Should be cached now
        cached = generator_with_cache.cache.get("cache test", generator_with_cache.model)
        assert cached == [0.4, 0.5, 0.6]

    def test_generate_handles_api_error(self, generator):
        """Test generate handles API errors gracefully."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API error")
        generator._client = mock_client

        result = generator.generate("test")
        assert result is None

    def test_generate_batch_empty_texts(self, generator):
        """Test generate_batch with empty texts."""
        results = generator.generate_batch(["", "   ", None])
        assert results == [None, None, None]

    def test_generate_batch_uses_cache(self, generator_with_cache):
        """Test generate_batch uses cache."""
        generator_with_cache.cache.set("text1", generator_with_cache.model, [0.1])
        generator_with_cache.cache.set("text2", generator_with_cache.model, [0.2])

        results = generator_with_cache.generate_batch(["text1", "text2"])
        assert results == [[0.1], [0.2]]

    def test_generate_batch_mixed_cached(self, generator_with_cache):
        """Test generate_batch with some cached texts."""
        generator_with_cache.cache.set("cached", generator_with_cache.model, [0.5])

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.9])]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        generator_with_cache._client = mock_client

        results = generator_with_cache.generate_batch(["cached", "uncached"])

        assert results[0] == [0.5]  # From cache
        assert results[1] == [0.9]  # From API

    def test_generate_batch_caches_results(self, generator_with_cache):
        """Test generate_batch caches new embeddings."""
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.7, 0.8])]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        generator_with_cache._client = mock_client

        generator_with_cache.generate_batch(["batch test"])

        cached = generator_with_cache.cache.get("batch test", generator_with_cache.model)
        assert cached == [0.7, 0.8]

    def test_generate_batch_handles_error(self, generator_with_cache):
        """Test generate_batch handles API error."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("Batch error")
        generator_with_cache._client = mock_client

        results = generator_with_cache.generate_batch(["text1", "text2"])
        # Results should contain None for failed items
        assert None in results or results == [None, None]

    def test_client_lazy_init(self, generator):
        """Test client is lazily initialized."""
        assert generator._client is None

        with patch.object(generator, "_client", None):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.return_value = MagicMock()
                generator._client = None  # Ensure it's None
                _ = generator.client

            # Client should now be set
            mock_openai.assert_called_once()

    def test_client_cached(self, generator):
        """Test client is cached after initialization."""
        mock_client = MagicMock()
        generator._client = mock_client

        assert generator.client is mock_client
