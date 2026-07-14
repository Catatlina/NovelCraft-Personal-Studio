from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _gate_module():
    spec = importlib.util.spec_from_file_location(
        "verify_ai_truthfulness", ROOT / "scripts/verify_ai_truthfulness.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_truthfulness_gate_blocks_ai_like_function_without_gateway(tmp_path):
    module = _gate_module()
    bad = tmp_path / "bad_generate.py"
    bad.write_text(
        """
def generate_article(topic):
    return {"title": f"震惊！{topic}背后的真相"}
""",
        encoding="utf-8",
    )

    findings = module.analyze_file(bad)
    codes = {finding.code for finding in findings}
    assert "ai-gateway-required" in codes
    assert "fixed-template" in codes


def test_truthfulness_gate_blocks_hardcoded_capability_claim(tmp_path):
    module = _gate_module()
    bad = tmp_path / "bad_status.py"
    bad.write_text(
        """
STATUS = {"wired": True, "status": "active"}
""",
        encoding="utf-8",
    )

    findings = module.analyze_file(bad)
    assert [finding.code for finding in findings].count("hardcoded-capability") == 2


def test_truthfulness_gate_accepts_gateway_backed_generation(tmp_path):
    module = _gate_module()
    good = tmp_path / "good_generate.py"
    good.write_text(
        """
from app.gateway import complete

def generate_article(project_id, topic):
    return complete(run_id=None, node_key=None, project_id=project_id,
                    task_type="gen_daily_brief", prompt_name="social.gen_hotspot_content",
                    variables={"topic": topic})
""",
        encoding="utf-8",
    )

    assert module.analyze_file(good) == []
