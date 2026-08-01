"""
V6 Adapters — 复用 V6 成熟代码
=================================

Adapter pattern: wrap V6 services to fit V7 interfaces.
Allows gradual migration from V6 to V7 without rewriting everything.
"""
from .generation_adapter import V6GenerationAdapter
from .deai_adapter import V6DeAIAdapter
from .context_adapter import V6ContextAdapter

__all__ = [
    "V6GenerationAdapter",
    "V6DeAIAdapter",
    "V6ContextAdapter",
]
