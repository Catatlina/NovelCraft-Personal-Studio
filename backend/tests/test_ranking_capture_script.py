"""Executable capture script contracts for ranking collection.

The script is allowed to automate public-page capture and local OCR. It is not
allowed to turn missing OCR, challenges, or selector drift into fake success.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _script_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "capture_ranking.py"
    spec = importlib.util.spec_from_file_location("capture_ranking_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tesseract_tsv_is_parsed_into_confidence_bearing_items():
    parse_tesseract_tsv = _script_module().parse_tesseract_tsv

    tsv = "\n".join([
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
        "5\t1\t1\t1\t1\t1\t10\t10\t50\t20\t91\t雾城",
        "5\t1\t1\t1\t1\t2\t61\t10\t50\t20\t88\t修理铺",
        "5\t1\t1\t1\t2\t1\t10\t40\t50\t20\t35\t登录",
        "5\t1\t1\t1\t3\t1\t10\t70\t50\t20\t96\t星海旧账",
    ])

    items = parse_tesseract_tsv(tsv)

    assert [item["title"] for item in items] == ["雾城修理铺", "星海旧账"]
    assert items[0]["collector"] == "browser_ocr"
    assert 0.88 <= items[0]["confidence"] <= 0.91


def test_fanqie_private_glyph_without_ocr_becomes_ocr_required(monkeypatch, tmp_path):
    capture_ranking = _script_module()

    monkeypatch.setattr(capture_ranking, "run_tesseract_ocr", lambda _path: ([], {"ocr_available": False}, "tesseract binary not found"))

    artifact = capture_ranking.build_artifact(
        "fanqie",
        "https://fanqienovel.com/rank/all",
        "榜单页",
        [{"rank": 1, "title": "私有码\ue001", "confidence": 1.0}],
        tmp_path / "fanqie.png",
        tmp_path / "profile",
    )

    assert artifact["status"] == "ocr_required"
    assert artifact["items"] == []
    assert artifact["evidence"]["ocr_available"] is False
    assert "tesseract" in artifact["error"]


def test_fanqie_private_glyph_with_real_ocr_output_can_succeed(monkeypatch, tmp_path):
    capture_ranking = _script_module()

    monkeypatch.setattr(
        capture_ranking,
        "run_tesseract_ocr",
        lambda _path: ([
            {"rank": 1, "title": "雾城修理铺", "author": "", "confidence": 0.87, "collector": "browser_ocr"},
        ], {"ocr_available": True, "ocr_engine": "tesseract", "ocr_min_confidence": 0.87}, None),
    )

    artifact = capture_ranking.build_artifact(
        "fanqie",
        "https://fanqienovel.com/rank/all",
        "榜单页",
        [{"rank": 1, "title": "私有码\ue001", "confidence": 1.0}],
        tmp_path / "fanqie.png",
        tmp_path / "profile",
    )

    assert artifact["status"] == "succeeded"
    assert artifact["collector"] == "browser_ocr"
    assert artifact["items"][0]["title"] == "雾城修理铺"


def test_challenge_marker_always_requires_user_action(tmp_path):
    build_artifact = _script_module().build_artifact

    artifact = build_artifact(
        "qidian",
        "https://www.qidian.com/rank/",
        "安全验证 请完成验证码",
        [{"rank": 1, "title": "不应采信", "confidence": 1.0}],
        Path(tmp_path / "qidian.png"),
        Path(tmp_path / "profile"),
    )

    assert artifact["status"] == "user_action_required"
    assert artifact["items"] == []
    assert "challenge" in artifact["error"]


def test_tencent_captcha_html_requires_user_action_but_generic_script_word_does_not(tmp_path):
    capture_ranking = _script_module()
    qidian_html = tmp_path / "qidian.html"
    qidian_html.write_text('<script src="https://ssl.captcha.qq.com/TCaptcha.js"></script>', encoding="utf-8")
    qidian = capture_ranking.build_artifact(
        "qidian", "https://www.qidian.com/rank/", "", [{"rank": 1, "title": "不应采信"}],
        tmp_path / "qidian.png", tmp_path / "profile", html_snapshot=qidian_html,
    )
    assert qidian["status"] == "user_action_required"

    fanqie_html = tmp_path / "fanqie.html"
    fanqie_html.write_text("<script>window.captchaConfig = false</script>", encoding="utf-8")
    fanqie = capture_ranking.build_artifact(
        "fanqie", "https://fanqienovel.com/rank/all", "", [],
        tmp_path / "fanqie.png", tmp_path / "profile", html_snapshot=fanqie_html,
    )
    assert fanqie["status"] == "schema_changed"
