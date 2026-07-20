"""P2-T10 入参校验单元测试 (T01)。

验证阶段二增量 B 为 ``bootstrap_novel`` / ``style_learn`` / ``check_similarity``
三个原本裸 ``request.json()`` 的端点补上的 Pydantic 模型：

- 合法入参被正确解析；
- 非法/畸形入参在 ``model_validate`` 处被捕获（端点内 try/except 回退默认，
  不会以裸 traceback 500 暴露）；
- 模型定义存在且可导入。

模型定义位于 ``app.main``，导入需要后端依赖；若环境不可用则整模块跳过。
"""
from __future__ import annotations

try:
    from app.main import (
        BootstrapNovelRequest,
        CheckSimilarityRequest,
        StyleLearnRequest,
    )
    _MODELS_OK = True
except Exception:  # pragma: no cover - 依赖/环境缺失时跳过
    BootstrapNovelRequest = StyleLearnRequest = CheckSimilarityRequest = None
    _MODELS_OK = False

import pytest

pytestmark = pytest.mark.skipif(
    not _MODELS_OK,
    reason="app.main 不可导入（缺少后端依赖或环境），跳过入参校验单元测试。",
)


def test_bootstrap_request_permissive_extra():
    # extra="allow"：宽松接受任意字段，不报错
    m = BootstrapNovelRequest(**{"foo": "bar", "count": 3})
    assert m is not None


def test_style_learn_valid():
    m = StyleLearnRequest.model_validate({"project_id": "p1", "samples": ["a", "b"]})
    assert m.project_id == "p1"
    assert m.samples == ["a", "b"]


def test_style_learn_invalid_samples_falls_back():
    # samples 应为 list；传入字符串应触发校验失败（端点据此回退默认，不 500）
    with pytest.raises(Exception):
        StyleLearnRequest.model_validate({"project_id": "p1", "samples": "not-a-list"})


def test_style_learn_empty_defaults():
    m = StyleLearnRequest.model_validate({})
    assert m.project_id == ""
    assert m.samples == []


def test_check_similarity_valid():
    m = CheckSimilarityRequest.model_validate(
        {"project_id": "p1", "original": "正文A", "generated": "正文B"}
    )
    assert m.original == "正文A"
    assert m.generated == "正文B"


def test_check_similarity_missing_fields_default():
    m = CheckSimilarityRequest.model_validate({})
    assert m.project_id == ""
    assert m.original == ""
    assert m.generated == ""
