"""Semantic embeddings with explicit backend selection (Stage-3 ③).

Backend resolution (env EMBEDDING_BACKEND = auto|remote|local|hash, default auto):
1. remote — OpenAI-compatible /embeddings API when EMBEDDING_API_KEY is set
   (EMBEDDING_API_URL default api.openai.com, EMBEDDING_MODEL default
   text-embedding-3-small with dimensions=512);
2. local — ONNX bge-small-zh-v1.5 via fastembed (~100MB model, ~50MB deps,
   CPU-friendly: fine on a laptop or a 2-core VPS);
3. hash — deterministic blake2b vectors for tests/offline development only,
   explicitly NOT semantic and never an implicit product downgrade.

All vectors are zero-padded to the storage dimension (1536, the existing
pgvector column), which preserves cosine ordering exactly — no migration.
Switching backends requires re-embedding (POST /knowledge/reindex)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request

STORAGE_DIM = 1536
SEMANTIC_DIM = 512

_local_model = None  # lazy fastembed instance


def _pad(vector: list[float]) -> list[float]:
    if len(vector) >= STORAGE_DIM:
        return vector[:STORAGE_DIM]
    return vector + [0.0] * (STORAGE_DIM - len(vector))


def hash_embedding(text: str, dimension: int = STORAGE_DIM) -> list[float]:
    """Deterministic non-semantic test backend (bigram blake2b hashing)."""
    vector = [0.0] * dimension
    normalized = re.sub(r"\s+", "", (text or "").lower())
    tokens = [normalized[i:i + 2] for i in range(max(0, len(normalized) - 1))] or ([normalized] if normalized else [])
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _remote_available() -> bool:
    return bool(os.getenv("EMBEDDING_API_KEY", "").strip())


def _local_available() -> bool:
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False


def _hash_backend_allowed() -> bool:
    return (
        os.getenv("NOVELCRAFT_ALLOW_HASH_EMBEDDING", "").strip().lower() in {"1", "true", "yes"}
        or os.getenv("NOVELCRAFT_ENV", "").strip().lower() == "test"
    )


def _raise_no_backend(configured: str, reason: str) -> None:
    raise RuntimeError(
        f"semantic embedding backend unavailable for EMBEDDING_BACKEND={configured!r}: {reason}. "
        "Configure EMBEDDING_API_KEY for remote, install/configure fastembed for local, "
        "or set NOVELCRAFT_ALLOW_HASH_EMBEDDING=true only for explicit offline test/dev indexing."
    )


def resolve_backend() -> str:
    configured = os.getenv("EMBEDDING_BACKEND", "auto").lower()
    if configured == "remote":
        if _remote_available():
            return "remote"
        _raise_no_backend(configured, "remote API key is missing")
    if configured == "local":
        if _local_available():
            return "local"
        _raise_no_backend(configured, "local embedding package/model is unavailable")
    if configured == "hash":
        if _hash_backend_allowed():
            return "hash"
        _raise_no_backend(configured, "hash vectors are non-semantic")
    # auto: remote > local > hash
    if _remote_available():
        return "remote"
    if _local_available():
        return "local"
    if _hash_backend_allowed():
        return "hash"
    _raise_no_backend(configured, "no semantic provider is configured")


def _embed_remote(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
    base_url = os.getenv("EMBEDDING_API_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    body: dict = {"model": model, "input": texts}
    if "text-embedding-3" in model:
        body["dimensions"] = SEMANTIC_DIM
    request = urllib.request.Request(
        f"{base_url}/embeddings",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload["data"]
    if sorted(item.get("index") for item in data) != list(range(len(texts))):
        raise ValueError("embedding provider returned invalid indexes")
    ordered = sorted(data, key=lambda item: item["index"])
    return [item["embedding"] for item in ordered]


def _embed_local(texts: list[str]) -> list[list[float]]:
    global _local_model
    if _local_model is None:
        from fastembed import TextEmbedding

        _local_model = TextEmbedding(model_name=os.getenv("EMBEDDING_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5"))
    return [list(map(float, vector)) for vector in _local_model.embed(texts)]


def _validate_vectors(vectors: list[list[float]], expected_count: int) -> None:
    """Reject partial/malformed provider output before it can drop chunks via zip()."""
    if len(vectors) != expected_count:
        raise ValueError(f"embedding count mismatch: expected {expected_count}, got {len(vectors)}")
    for vector in vectors:
        if not vector or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
            raise ValueError("embedding provider returned an empty or non-finite vector")


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    """Embed a batch; returns (padded vectors, backend actually used).

    Remote/local failures are terminal. Hash vectors require explicit
    offline/test opt-in and are reported so callers can persist provenance."""
    if not texts:
        return [], resolve_backend()
    backend = resolve_backend()
    if backend == "remote":
        vectors = _embed_remote(texts)
        _validate_vectors(vectors, len(texts))
        return [_pad(v) for v in vectors], "remote"
    if backend == "local":
        vectors = _embed_local(texts)
        _validate_vectors(vectors, len(texts))
        return [_pad(v) for v in vectors], "local"
    return [hash_embedding(t) for t in texts], "hash"


def embed_query(text: str) -> list[float]:
    vectors, _backend = embed_texts([text])
    return vectors[0]


def embed_query_with_backend(text: str) -> tuple[list[float], str]:
    vectors, backend = embed_texts([text])
    return vectors[0], backend
