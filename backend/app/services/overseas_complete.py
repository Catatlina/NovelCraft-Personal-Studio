"""NC-SEA-001~003: Overseas markets, translation pipeline, publishing."""
from __future__ import annotations
from datetime import datetime
from app.db import connect, new_id, encode

# ===== NC-SEA-001: Market/Channel/Language/Compliance =====

OVERSEAS_MARKETS = {
    "en_US": {"name": "北美", "languages": ["en"], "platforms": ["medium", "substack", "royalroad", "webnovel"], "currency": "USD", "timezone": "America/New_York"},
    "en_UK": {"name": "英国", "languages": ["en"], "platforms": ["medium", "substack"], "currency": "GBP", "timezone": "Europe/London"},
    "ja_JP": {"name": "日本", "languages": ["ja"], "platforms": ["webnovel", "pixiv"], "currency": "JPY", "timezone": "Asia/Tokyo"},
    "ko_KR": {"name": "韩国", "languages": ["ko"], "platforms": ["webnovel", "kakao"], "currency": "KRW", "timezone": "Asia/Seoul"},
    "th_TH": {"name": "泰国", "languages": ["th"], "platforms": ["webnovel"], "currency": "THB", "timezone": "Asia/Bangkok"},
    "es_ES": {"name": "西班牙/拉美", "languages": ["es"], "platforms": ["medium", "substack"], "currency": "EUR", "timezone": "Europe/Madrid"},
    "de_DE": {"name": "德国", "languages": ["de"], "platforms": ["medium"], "currency": "EUR", "timezone": "Europe/Berlin"},
    "fr_FR": {"name": "法国", "languages": ["fr"], "platforms": ["medium"], "currency": "EUR", "timezone": "Europe/Paris"},
    "pt_BR": {"name": "巴西", "languages": ["pt"], "platforms": ["medium"], "currency": "BRL", "timezone": "America/Sao_Paulo"},
    "ru_RU": {"name": "俄罗斯", "languages": ["ru"], "platforms": ["webnovel"], "currency": "RUB", "timezone": "Europe/Moscow"},
}

CONTENT_RATINGS = {
    "G": "全年龄", "PG": "家长指导", "PG13": "13岁以上",
    "R": "限制级", "M": "成人内容",
}

MARKET_COMPLIANCE = {
    "en_US": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["child_exploitation","terrorism"]},
    "en_UK": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["hate_speech","terrorism"]},
    "ja_JP": {"content_rating": ["G","PG","PG13"], "banned_topics": ["adult_content","violence_extreme"]},
    "es_ES": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["hate_speech"]},
    "de_DE": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["nazi_symbols","hate_speech"]},
    "ko_KR": {"content_rating": ["G","PG","PG13"], "banned_topics": ["adult_content","gambling"]},
}


def get_market_config(market: str = "") -> dict:
    """NC-SEA-001: Get market configuration for a target region."""
    if market: return OVERSEAS_MARKETS.get(market, {"error": "unknown market"})
    return {"markets": list(OVERSEAS_MARKETS.keys()), "count": len(OVERSEAS_MARKETS)}


def get_timezone(market: str) -> str:
    """NC-SEA-001: Get timezone for a market."""
    return OVERSEAS_MARKETS.get(market, {}).get("timezone", "UTC")


def check_market_compliance(market: str, content: str) -> dict:
    """NC-SEA-001: Check content against market-specific compliance rules."""
    rules = MARKET_COMPLIANCE.get(market, {})
    banned = rules.get("banned_topics", [])
    issues = []
    for topic in banned:
        if topic.lower() in content.lower():
            issues.append(f"banned_topic: {topic}")
    return {"market": market, "clean": len(issues) == 0, "issues": issues, "allowed_ratings": rules.get("content_rating", [])}


# ===== NC-SEA-002: Translation + Name localization + Cultural adaptation =====

TERMINOLOGY_DB: dict[str, dict[str, dict[str, str]]] = {
    "zh": {
        "en": {
            "主角": "protagonist", "金丹": "Golden Core", "元婴": "Nascent Soul",
            "修仙": "cultivation", "灵气": "spiritual energy", "法宝": "magic artifact",
            "飞升": "ascension", "渡劫": "tribulation", "剑修": "sword cultivator",
            "丹药": "elixir", "功法": "cultivation technique", "神识": "divine sense",
            "储物袋": "storage pouch", "灵脉": "spirit vein", "阵法": "formation array",
            "总裁": "CEO", "霸道": "domineering", "甜宠": "sweet romance",
            "打脸": "face-slapping", "逆袭": "comeback", "穿越": "transmigration",
            "重生": "rebirth", "系统": "system", "金手指": "golden finger",
        },
        "ja": {"主角": "主人公", "金丹": "金丹", "元婴": "元婴", "修仙": "修仙"},
        "ko": {"主角": "주인공", "修仙": "수선", "金丹": "금단"},
        "es": {"主角": "protagonista", "修仙": "cultivacion", "金丹": "Nucleo Dorado"},
        "de": {"主角": "Protagonist", "修仙": "Kultivierung", "金丹": "Goldener Kern"},
        "fr": {"主角": "protagoniste", "修仙": "cultivation", "金丹": "Noyau d'Or"},
        "pt": {"主角": "protagonista", "修仙": "cultivacao", "金丹": "Nucleo Dourado"},
        "ru": {"主角": "главный герой", "修仙": "культивация", "金丹": "Золотое Ядро"},
    }
}

# Name localization: Chinese names → natural names per market
NAME_MAP: dict[str, dict[str, str]] = {
    # Urban/modern male names
    "张翰": {"en_US": "John Zhang", "en_UK": "John Zhang"},
    "林晨": {"en_US": "Leo Lin", "en_UK": "Leo Lin"},
    "李云": {"en_US": "Liam Yun", "en_UK": "Liam Yun"},
    "王浩": {"en_US": "Henry Wang", "en_UK": "Henry Wang"},
    "赵云": {"en_US": "Aaron Zhao", "en_UK": "Aaron Zhao"},
    "陈默": {"en_US": "Miles Chen", "en_UK": "Miles Chen"},
    "林逸": {"en_US": "Ian Lin", "en_UK": "Ian Lin"},
    "刘洋": {"en_US": "Owen Liu", "en_UK": "Owen Liu"},
    "周凯": {"en_US": "Kai Zhou", "en_UK": "Kai Zhou"},
    "杨光": {"en_US": "Ray Yang", "en_UK": "Ray Yang"},
    # Xianxia names — keep transliterated
    "墨渊": {"en_US": "Mo Yuan", "en_UK": "Mo Yuan"},
    "叶尘": {"en_US": "Ye Chen", "en_UK": "Ye Chen"},
    "苏铭": {"en_US": "Su Ming", "en_UK": "Su Ming"},
    "韩立": {"en_US": "Han Li", "en_UK": "Han Li"},
    # Female names
    "王雪": {"en_US": "Serena Wang", "en_UK": "Serena Wang"},
    "李月": {"en_US": "Luna Li", "en_UK": "Luna Li"},
    "陈悦": {"en_US": "Joy Chen", "en_UK": "Joy Chen"},
    "赵琳": {"en_US": "Lynn Zhao", "en_UK": "Lynn Zhao"},
    "林婉儿": {"en_US": "Wendy Lin", "en_UK": "Wendy Lin"},
    "苏晴": {"en_US": "Claire Su", "en_UK": "Claire Su"},
}


def _get_terminology(source_lang: str, target_lang: str) -> dict[str, str]:
    """Get terminology map for a language pair."""
    base_src = source_lang.split("_")[0] if "_" in source_lang else source_lang
    base_tgt = target_lang.split("_")[0] if "_" in target_lang else target_lang
    return TERMINOLOGY_DB.get(base_src, {}).get(base_tgt, {})


def translate_text(text: str, source_lang: str = "zh", target_lang: str = "en",
                   apply_terminology: bool = True, localize_names: bool = True) -> dict:
    """NC-SEA-002: Translate with terminology + name consistency checks."""

    # Step 1: Name localization
    localized_text = text
    name_replacements: list[dict] = []
    if localize_names:
        market = f"{target_lang}_US" if target_lang == "en" else target_lang
        for zh_name, localized in NAME_MAP.items():
            if zh_name in localized_text:
                en_name = localized.get(market, localized.get("en_US", zh_name))
                localized_text = localized_text.replace(zh_name, en_name)
                name_replacements.append({"original": zh_name, "localized": en_name, "market": market})

    # Step 2: Terminology map
    terms = _get_terminology(source_lang, target_lang)
    term_replacements: list[dict] = []
    if apply_terminology and terms:
        for zh_term, target_term in terms.items():
            if zh_term in localized_text and zh_term != target_term:
                term_replacements.append({"source": zh_term, "target": target_term})

    # Step 3: AI translation
    import os
    glossary = "\n".join(f"{k} -> {v}" for k, v in terms.items())
    from app.gateway import complete
    result = complete(
        run_id=None, node_key=None, project_id=os.getenv("NOVELCRAFT_DEFAULT_PROJECT", ""),
        task_type="translate_segment", prompt_name="overseas.translate_segment",
        variables={
            "body": localized_text[:5000],
            "source_lang": source_lang,
            "target_lang": target_lang,
            "glossary": glossary if terms else "(none)",
        },
    )
    translated = result.get("text", result.get("translated", ""))
    if not translated:
        return {"error": "AI translation response empty", "text": localized_text, "method": "fallback"}

    # Step 4: Consistency checks
    term_consistency = _check_term_consistency(translated, term_replacements, target_lang)
    name_consistency = _check_name_consistency(translated, name_replacements)

    return {
        "source_lang": source_lang, "target_lang": target_lang,
        "original_length": len(text), "translated_length": len(translated),
        "terminology_applied": len(terms),
        "name_replacements": name_replacements,
        "term_replacements": term_replacements,
        "text": translated,
        "consistency": {"terminology": term_consistency, "names": name_consistency},
        "method": "ai_gateway",
    }


def _check_term_consistency(translated: str, replacements: list[dict], target_lang: str) -> dict:
    """Verify AI translation preserved terminology substitutions."""
    missing = [r for r in replacements if r["target"].lower() not in translated.lower()]
    total = len(replacements)
    return {
        "total_terms": total, "preserved": total - len(missing),
        "missing": missing, "score": round((total - len(missing)) / max(total, 1) * 100, 1),
    }


def _check_name_consistency(translated: str, replacements: list[dict]) -> dict:
    """Verify localized names appear in translation."""
    missing = [r for r in replacements if r["localized"].lower() not in translated.lower()]
    total = len(replacements)
    return {
        "total_names": total, "preserved": total - len(missing),
        "missing": missing, "score": round((total - len(missing)) / max(total, 1) * 100, 1),
    }


def get_name_map() -> dict:
    """NC-SEA-002: Get full name localization map."""
    return NAME_MAP


def add_name_mapping(chinese_name: str, market: str, localized_name: str) -> dict:
    """NC-SEA-002: Add a name mapping entry."""
    if chinese_name not in NAME_MAP:
        NAME_MAP[chinese_name] = {}
    NAME_MAP[chinese_name][market] = localized_name
    return {"status": "added", "name": chinese_name, "market": market, "localized": localized_name}


def cultural_adaptation(text: str, target_market: str) -> dict:
    """NC-SEA-002: Adapt cultural references for target market."""
    adaptations = []
    patterns = {
        "en_US": [
            ("打脸", "face-slapping/public humiliation"),
            ("装逼", "flexing/showing off"),
            ("吃醋", "jealousy/envy"),
            ("开挂", "cheating/using hacks"),
            ("万", "ten thousand — convert to Western numbering"),
            ("亿", "hundred million — convert to Western numbering"),
            ("不要脸", "shameless"),
            ("走后门", "backdoor/nepotism"),
        ],
        "ja_JP": [
            ("打脸", "恥をかかせる (haji wo kakaseru)"),
            ("吃醋", "嫉妬 (shitto)"),
        ],
        "ko_KR": [
            ("打脸", "망신주기 (mangsin jugi)"),
        ],
    }
    for zh_term, adaptation in patterns.get(target_market, []):
        if zh_term in text:
            adaptations.append({"original": zh_term, "adaptation": adaptation})
    return {"market": target_market, "adaptations": adaptations, "count": len(adaptations)}


def generate_consistency_report(content_id: str, target_market: str) -> dict:
    """NC-SEA-002: Generate terminology + name consistency report for translated content."""
    db = connect()
    content = db.execute("SELECT * FROM contents WHERE id=%s", (content_id,)).fetchone()
    db.close()
    if not content:
        return {"error": "content not found"}

    body = content.get("body", "")
    text = body if isinstance(body, str) else str(body)

    # Check terminology coverage
    terms = TERMINOLOGY_DB.get("zh", {}).get(target_market.split("_")[0], {})
    term_coverage = []
    for zh_term, target_term in terms.items():
        found_zh = zh_term in text
        found_target = target_term.lower() in text.lower()
        term_coverage.append({
            "term": zh_term, "expected": target_term,
            "source_present": found_zh, "target_present": found_target,
        })

    # Check name coverage
    names_found = []
    for zh_name, localized in NAME_MAP.items():
        if zh_name in text:
            names_found.append({
                "original": zh_name,
                "expected": localized.get(target_market, localized.get("en_US", zh_name)),
                "found": text.count(zh_name),
            })

    return {
        "content_id": content_id, "market": target_market,
        "terminology_coverage": term_coverage,
        "names_found": names_found,
        "total_terms": len(term_coverage),
        "total_names": len(names_found),
    }


# ===== NC-SEA-003: Overseas publishing + currency =====

CURRENCY_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 149.5, "KRW": 1310.0, "THB": 34.5, "CNY": 7.24, "BRL": 5.05, "RUB": 89.0}


def convert_revenue(amount: float, from_currency: str, to_currency: str = "CNY") -> dict:
    """NC-SEA-003: Convert revenue between currencies."""
    usd_amount = amount / CURRENCY_RATES.get(from_currency, 1.0)
    converted = usd_amount * CURRENCY_RATES.get(to_currency, 1.0)
    return {"amount": amount, "from": from_currency, "to": to_currency, "converted": round(converted, 2)}


def get_local_publish_time(market: str) -> str:
    """NC-SEA-003: Get local publish time for a market."""
    tz_name = get_timezone(market)
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime as dt
        local = dt.now(ZoneInfo(tz_name))
        return local.isoformat()
    except Exception:
        return datetime.utcnow().isoformat() + "Z"


def publish_overseas(content_id: str, market: str, platform: str) -> dict:
    """NC-SEA-003: Publish content to overseas platform with timezone awareness."""
    mkt = OVERSEAS_MARKETS.get(market, {})
    if platform not in mkt.get("platforms", []):
        return {"status": "error", "message": f"{platform} not available in {market}"}
    db = connect()
    pid = new_id()
    local_time = get_local_publish_time(market)
    currency = mkt.get("currency", "USD")
    db.execute(
        "INSERT INTO published_posts (id, project_id, platform, content_id, title, status, meta) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (pid, None, f"overseas_{platform}", content_id, f"Overseas: {market}/{platform}",
         "draft", encode({
             "market": market, "platform": platform, "currency": currency,
             "local_time": local_time, "published_at": datetime.utcnow().isoformat(),
             "mode": "manual_required",
             "instructions": f"Manual publish required to {platform} in {market} market. Target timezone: {mkt.get('timezone','UTC')}",
         })),
    )
    db.commit(); db.close()
    return {"status": "draft", "market": market, "platform": platform, "post_id": pid,
            "local_time": local_time, "currency": currency, "mode": "manual_required"}
