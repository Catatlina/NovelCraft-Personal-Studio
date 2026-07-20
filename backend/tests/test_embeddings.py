"""Stage-3 ③: semantic embeddings — backend resolution, zero-pad ordering
invariant, remote protocol, explicit hash test backend, and semantic quality."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest


TEST_FILE = Path(__file__).resolve()
ROOT = TEST_FILE.parents[2]
KNOWLEDGE_HUB_SOURCE = (
    ROOT / "backend/app/services/knowledge_hub.py"
    if (ROOT / "backend/app/services/knowledge_hub.py").exists()
    else TEST_FILE.parents[1] / "app/services/knowledge_hub.py"
)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def test_zero_padding_preserves_cosine_ordering():
    from app.core.embeddings import _pad

    a, b, c = [1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 0.0, 1.0]
    assert _cosine(a, b) > _cosine(a, c)
    pa, pb, pc = _pad(a), _pad(b), _pad(c)
    assert len(pa) == 1536
    assert abs(_cosine(pa, pb) - _cosine(a, b)) < 1e-9  # 填充零不改变余弦
    assert _cosine(pa, pb) > _cosine(pa, pc)


def test_backend_resolution_and_hash_forcing(monkeypatch):
    from app.core import embeddings

    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("NOVELCRAFT_ALLOW_HASH_EMBEDDING", "true")
    assert embeddings.resolve_backend() == "hash"

    monkeypatch.setenv("EMBEDDING_BACKEND", "remote")
    monkeypatch.delenv("NOVELCRAFT_ALLOW_HASH_EMBEDDING", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="remote API key is missing"):
        embeddings.resolve_backend()

    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    assert embeddings.resolve_backend() == "remote"


def test_remote_backend_protocol(monkeypatch):
    import urllib.request

    from app.core import embeddings

    monkeypatch.setenv("EMBEDDING_BACKEND", "remote")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    captured = {}

    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({"data": [
                {"index": 1, "embedding": [0.0] * 512},
                {"index": 0, "embedding": [1.0] + [0.0] * 511},
            ]}).encode()

    def fake_urlopen(request, timeout=0):
        captured["body"] = json.loads(request.data.decode())
        return FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    vectors, backend = embeddings.embed_texts(["第一条", "第二条"])
    assert backend == "remote"
    assert captured["body"]["dimensions"] == 512  # text-embedding-3 显式降维
    assert len(vectors) == 2 and len(vectors[0]) == 1536
    assert vectors[0][0] == 1.0  # 按 index 还原顺序


def test_remote_failure_is_terminal(monkeypatch):
    import urllib.request

    from app.core import embeddings

    monkeypatch.setenv("EMBEDDING_BACKEND", "remote")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")

    def down(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", down)
    with pytest.raises(OSError, match="network unreachable"):
        embeddings.embed_texts(["离线时不得伪装语义入库"])


def test_partial_remote_response_cannot_silently_drop_chunks(monkeypatch):
    from app.core import embeddings

    monkeypatch.setenv("EMBEDDING_BACKEND", "remote")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
    monkeypatch.setattr(embeddings, "_embed_remote", lambda _texts: [[1.0, 0.0]])
    with pytest.raises(ValueError, match="embedding count mismatch"):
        embeddings.embed_texts(["第一块", "第二块"])


def test_hash_backend_disallowed_outside_explicit_test_mode(monkeypatch):
    from app.core import embeddings

    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    monkeypatch.setenv("NOVELCRAFT_ENV", "production")
    monkeypatch.delenv("NOVELCRAFT_ALLOW_HASH_EMBEDDING", raising=False)
    with pytest.raises(RuntimeError, match="hash vectors are non-semantic"):
        embeddings.resolve_backend()


def test_search_filters_vectors_by_embedding_backend():
    source = KNOWLEDGE_HUB_SOURCE.read_text(encoding="utf-8")
    assert "embed_query_with_backend" in source
    assert "COALESCE(ki.meta->>'embedding_backend', 'hash') = %s" in source


def test_rebuild_records_backend_provenance():
    source = KNOWLEDGE_HUB_SOURCE.read_text(encoding="utf-8")
    assert "embedding_backend" in source
    assert "reindex_project_embeddings" in source


def test_rebuild_releases_read_connection_before_embedding_failure(monkeypatch):
    from app.services import knowledge_hub

    class FakeDb:
        def __init__(self):
            self.closed = False

        def execute(self, _sql, _params=()):
            return self

        def fetchone(self):
            return {"body": "需要生成语义向量的知识正文"}

        def close(self):
            self.closed = True

    opened = []

    def fake_connect():
        db = FakeDb()
        opened.append(db)
        return db

    monkeypatch.setattr(knowledge_hub, "connect", fake_connect)
    monkeypatch.setattr(
        knowledge_hub,
        "embed_texts",
        lambda _chunks: (_ for _ in ()).throw(RuntimeError("embedding provider unavailable")),
    )

    with pytest.raises(RuntimeError, match="embedding provider unavailable"):
        knowledge_hub.rebuild_item_embeddings("item-1")

    assert len(opened) == 1
    assert opened[0].closed is True


@pytest.mark.skipif(os.getenv("EMBEDDING_SEMANTIC_TEST") != "1",
                    reason="真实语义对照需本地模型（首跑下载 ~100MB）：EMBEDDING_SEMANTIC_TEST=1 启用")
def test_local_model_is_actually_semantic(monkeypatch):
    """hash 后端做不到的语义匹配：地底嗡鸣 ≈ 深渊低语 ≫ 白菜价格。"""
    monkeypatch.setenv("EMBEDDING_BACKEND", "local")
    from app.core import embeddings

    vectors, backend = embeddings.embed_texts([
        "他在凌晨听见地底传来低沉的嗡鸣声",
        "深渊的低语在地下回响，像某种呼吸",
        "今天菜市场的白菜价格上涨了两块钱",
    ])
    assert backend == "local"
    query, related, unrelated = vectors
    assert _cosine(query, related) > _cosine(query, unrelated) + 0.1
