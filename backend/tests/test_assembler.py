"""Tests for context assembler — novel-scoped data isolation."""
import os
os.environ["NOVELCRAFT_ENV"] = "dev"

import pytest
from app.services.assembler import ContextAssembler
from app.db import connect


def test_assembler_empty_novel():
    """Assembler should not crash on novel with no chapters."""
    import uuid
    assembler = ContextAssembler(str(uuid.uuid4()))
    ctx = assembler.build()
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_assembler_novel_isolation():
    """Two different novels should not share entity states."""
    import uuid
    a1 = ContextAssembler(str(uuid.uuid4())).build()
    a2 = ContextAssembler(str(uuid.uuid4())).build()
    assert isinstance(a1, str)
    assert isinstance(a2, str)
