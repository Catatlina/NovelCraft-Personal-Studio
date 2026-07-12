"""NC-SEA-001~003: Overseas markets, translation pipeline, publishing."""
from __future__ import annotations
from datetime import datetime
from app.db import connect, new_id, encode

# ===== NC-SEA-001: Market/Channel/Language/Compliance =====

OVERSEAS_MARKETS = {
    "en_US": {"name": "北美", "languages": ["en"], "platforms": ["medium", "substack", "royalroad", "webnovel"], "currency": "USD"},
    "en_UK": {"name": "英国", "languages": ["en"], "platforms": ["medium", "substack"], "currency": "GBP"},
    "ja_JP": {"name": "日本", "languages": ["ja"], "platforms": ["webnovel", "pixiv"], "currency": "JPY"},
    "ko_KR": {"name": "韩国", "languages": ["ko"], "platforms": ["webnovel", "kakao"], "currency": "KRW"},
    "th_TH": {"name": "泰国", "languages": ["th"], "platforms": ["webnovel"], "currency": "THB"},
    "es_ES": {"name": "西班牙/拉美", "languages": ["es"], "platforms": ["medium", "substack"], "currency": "EUR"},
}

CONTENT_RATINGS = {
    "G": "全年龄", "PG": "家长指导", "PG13": "13岁以上",
    "R": "限制级", "M": "成人内容",
}

MARKET_COMPLIANCE = {
    "en_US": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["child_exploitation","terrorism"]},
    "ja_JP": {"content_rating": ["G","PG","PG13"], "banned_topics": ["adult_content","violence_extreme"]},
    "es_ES": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["hate_speech"]},
}


def get_market_config(market: str = "") -> dict:
    """NC-SEA-001: Get market configuration for a target region."""
    if market: return OVERSEAS_MARKETS.get(market, {"error": "unknown market"})
    return {"markets": list(OVERSEAS_MARKETS.keys()), "count": len(OVERSEAS_MARKETS)}


def check_market_compliance(market: str, content: str) -> dict:
    """NC-SEA-001: Check content against market-specific compliance rules."""
    rules = MARKET_COMPLIANCE.get(market, {})
    banned = rules.get("banned_topics", [])
    issues = []
    for topic in banned:
        if topic.lower() in content.lower():
            issues.append(f"banned_topic: {topic}")
    return {"market": market, "clean": len(issues) == 0, "issues": issues, "allowed_ratings": rules.get("content_rating", [])}


# ===== NC-SEA-002: Translation pipeline =====

TERMINOLOGY_DB: dict[str, dict[str, dict[str, str]]] = {
    "zh": {
        "en": {"主角": "protagonist", "金丹": "Golden Core", "元婴": "Nascent Soul", "修仙": "cultivation"},
        "ja": {"主角": "主人公", "金丹": "金丹", "元婴": "元婴", "修仙": "修仙"},
    }
}


def translate_text(text: str, source_lang: str = "zh", target_lang: str = "en") -> dict:
    """NC-SEA-002: Translate via AI gateway with terminology consistency."""
    import os
    terms = TERMINOLOGY_DB.get(source_lang, {}).get(target_lang, {})
    glossary = "\n".join(f"{k} → {v}" for k, v in terms.items())
    try:
        from app.gateway import complete
        result = complete(
            run_id=None, node_key=None, project_id=os.getenv("NOVELCRAFT_DEFAULT_PROJECT", ""),
            task_type="translate_segment", prompt_name="overseas.translate_segment",
            variables={
                "body": text[:5000],
                "source_lang": source_lang,
                "target_lang": target_lang,
                "glossary": glossary if terms else "(无)",
            },
        )
        translated = result.get("text", result.get("translated", text))
        return {
            "source_lang": source_lang, "target_lang": target_lang,
            "original_length": len(text), "translated_length": len(translated),
            "terminology_applied": len(terms), "text": translated,
            "method": "ai_gateway" if "text" in result else "fallback_term_only",
        }
    except Exception:
        # Fallback: terminology-only (graceful degradation)
        result = text
        applied = []
        for zh, tl in terms.items():
            if zh in result:
                result = result.replace(zh, tl)
                applied.append(f"{zh}→{tl}")
        return {
            "source_lang": source_lang, "target_lang": target_lang,
            "original_length": len(text), "translated_length": len(result),
            "terminology_applied": len(applied), "terms_used": applied,
            "text": result, "method": "fallback_terminology_only",
        }


def localize_names(chinese_name: str, target_market: str) -> str:
    """NC-SEA-002: Localize character names for Western markets."""
    name_map = {
        "李云": {"en_US": "Liam Yun", "en_UK": "Liam Yun"},
        "王雪": {"en_US": "Serena Wang", "en_UK": "Serena Wang"},
    }
    return name_map.get(chinese_name, {}).get(target_market, chinese_name)


def cultural_adaptation(text: str, target_market: str) -> dict:
    """NC-SEA-002: Adapt idioms and cultural references."""
    adaptations = []
    if target_market == "en_US":
        if "打脸" in text: adaptations.append("打脸 → owned/humiliated")
        if "装逼" in text: adaptations.append("装逼 → flexing/showing off")
    return {"market": target_market, "adaptations": adaptations, "count": len(adaptations)}


# ===== NC-SEA-003: Overseas publishing + currency =====

CURRENCY_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 149.5, "KRW": 1310.0, "THB": 34.5, "CNY": 7.24}


def convert_revenue(amount: float, from_currency: str, to_currency: str = "CNY") -> dict:
    """NC-SEA-003: Convert revenue between currencies."""
    usd_amount = amount / CURRENCY_RATES.get(from_currency, 1.0)
    converted = usd_amount * CURRENCY_RATES.get(to_currency, 1.0)
    return {"amount": amount, "from": from_currency, "to": to_currency, "converted": round(converted, 2)}


def publish_overseas(content_id: str, market: str, platform: str) -> dict:
    """NC-SEA-003: Publish content to overseas platform with timezone awareness."""
    mkt = OVERSEAS_MARKETS.get(market, {})
    if platform not in mkt.get("platforms", []):
        return {"status": "error", "message": f"{platform} not available in {market}"}
    db = connect()
    pid = new_id()
    db.execute(
        "INSERT INTO published_posts (id, project_id, platform, content_id, title, status, meta) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (pid, None, f"overseas_{platform}", content_id, f"Overseas publish: {market}/{platform}",
         "draft", encode({"market": market, "platform": platform, "published_at": datetime.utcnow().isoformat(),
         "mode": "manual_required", "instructions": f"Manual publish required to {platform} in {market} market"})),
    )
    db.commit(); db.close()
    return {"status": "draft", "market": market, "platform": platform, "post_id": pid,
            "mode": "manual_required", "message": f"Overseas publishing is manual only. Content saved as draft in {platform}."}
