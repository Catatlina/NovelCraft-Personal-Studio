"""Feature Flag system — zero-dependency, env-driven, runtime toggleable.

Usage:
    from app.core.feature_flags import is_enabled, get_flag

    if is_enabled("new_editor"):
        return new_editor_response()
"""
import os
from typing import Any

# Env: FEATURE_FLAGS="new_editor:true,beta_ui:false,a_b_test:a"
_FLAGS: dict[str, str] = {}
_loaded = False


def _load():
    global _loaded, _FLAGS
    if _loaded:
        return
    raw = os.getenv("FEATURE_FLAGS", "")
    for pair in raw.split(","):
        pair = pair.strip()
        if ":" in pair:
            k, v = pair.split(":", 1)
            _FLAGS[k.strip()] = v.strip()
    # Also load from DB if available (non-blocking)
    try:
        from app.db import connect as _connect
        db = _connect()
        rows = db.execute("SELECT key, value FROM feature_flags WHERE active=true")
        for key, value in rows:
            if key not in _FLAGS:
                _FLAGS[key] = str(value)
        db.close()
    except Exception:
        pass
    _loaded = True


def is_enabled(key: str) -> bool:
    """Check if feature flag is truthy."""
    _load()
    v = _FLAGS.get(key, "false")
    return v.lower() in ("true", "1", "yes", "on")


def get_flag(key: str, default: str = "false") -> str:
    """Get string value of flag (for A/B tests, percentage, etc)."""
    _load()
    return _FLAGS.get(key, default)


def all_flags() -> dict[str, str]:
    """Return all active flags (for admin debug)."""
    _load()
    return dict(_FLAGS)
