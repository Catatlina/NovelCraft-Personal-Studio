"""NC-SEA-001~003: Overseas markets, translation pipeline, publishing."""
from __future__ import annotations
import json
import re
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

# Every configured market MUST have a compliance entry — a market without rules
# cannot be released to (validate_market_release enforces this).
MARKET_COMPLIANCE = {
    "en_US": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["child_exploitation","terrorism"]},
    "en_UK": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["child_exploitation","terrorism","hate_speech"]},
    "ja_JP": {"content_rating": ["G","PG","PG13"], "banned_topics": ["adult_content","violence_extreme"]},
    "ko_KR": {"content_rating": ["G","PG","PG13"], "banned_topics": ["adult_content","gambling_promo"]},
    "th_TH": {"content_rating": ["G","PG","PG13"], "banned_topics": ["royal_defamation","adult_content"]},
    "es_ES": {"content_rating": ["G","PG","PG13","R"], "banned_topics": ["hate_speech"]},
}

COMPLIANCE_RULES: dict[str, dict[str, list[str]]] = {
    "child_exploitation": {
        "patterns": [r"child\s+exploitation", r"minor\s+sexual", r"underage\s+sexual", r"儿童\s*(?:色情|剥削)"],
    },
    "terrorism": {
        "patterns": [r"terror(?:ism|ist)", r"bomb\s*making", r"make\s+(?:a\s+)?bomb", r"恐怖主义", r"炸弹\s*制作"],
    },
    "hate_speech": {
        "patterns": [r"hate\s+speech", r"racial\s+slur", r"种族\s*(?:仇恨|歧视)", r"仇恨言论"],
    },
    "adult_content": {
        "patterns": [r"explicit\s+sexual", r"porn(?:ography)?", r"成人内容", r"露骨\s*性"],
    },
    "violence_extreme": {
        "patterns": [r"graphic\s+(?:gore|torture)", r"extreme\s+violence", r"酷刑细节", r"极端暴力"],
    },
    "gambling_promo": {
        "patterns": [r"gambling\s+promo", r"betting\s+bonus", r"博彩推广", r"赌博推广"],
    },
    "royal_defamation": {
        "patterns": [r"royal\s+defamation", r"defame\s+(?:the\s+)?monarchy", r"王室\s*(?:诽谤|侮辱)"],
    },
}

MARKET_TIMEZONES = {
    "en_US": "America/New_York", "en_UK": "Europe/London", "ja_JP": "Asia/Tokyo",
    "ko_KR": "Asia/Seoul", "th_TH": "Asia/Bangkok", "es_ES": "Europe/Madrid",
}


def get_market_config(market: str = "") -> dict:
    """NC-SEA-001: Get market configuration for a target region."""
    if market:
        cfg = OVERSEAS_MARKETS.get(market)
        if not cfg:
            return {"error": "unknown market"}
        return {**cfg, "compliance": MARKET_COMPLIANCE.get(market, {}),
                "timezone": MARKET_TIMEZONES.get(market, "UTC"),
                "content_ratings": CONTENT_RATINGS}
    return {"markets": list(OVERSEAS_MARKETS.keys()), "count": len(OVERSEAS_MARKETS)}


def check_market_compliance(market: str, content: str) -> dict:
    """NC-SEA-001: Check content against market-specific compliance rules.

    This is a deterministic rules engine, not a claim of legal advice or a
    semantic AI audit. It uses per-market rule IDs plus multilingual/alias
    patterns so obvious phrasing variants cannot bypass a plain substring list.
    """
    rules = MARKET_COMPLIANCE.get(market, {})
    banned = rules.get("banned_topics", [])
    normalized = re.sub(r"\s+", " ", content or "").strip()
    issues = []
    matched_rules = []
    for topic in banned:
        rule = COMPLIANCE_RULES.get(topic, {"patterns": [re.escape(topic)]})
        matches = [pattern for pattern in rule["patterns"] if re.search(pattern, normalized, flags=re.IGNORECASE)]
        if matches:
            issues.append(f"banned_topic: {topic}")
            matched_rules.append({"topic": topic, "patterns": matches})
    return {"market": market, "clean": len(issues) == 0, "issues": issues,
            "matched_rules": matched_rules, "engine": "deterministic_rules_v1",
            "allowed_ratings": rules.get("content_rating", [])}


def validate_market_release(market: str, content: str, rating: str) -> dict:
    """NC-SEA-001: 发市前校验 — 市场存在、分级为作者声明且被市场允许、内容合规。
    分级由作者/编辑声明，系统只校验是否允许，不假装机器能替人定级。"""
    if market not in OVERSEAS_MARKETS:
        return {"allowed": False, "blockers": [f"unknown market: {market}"]}
    blockers = []
    if market not in MARKET_COMPLIANCE:
        blockers.append(f"market {market} has no compliance ruleset configured")
    if rating not in CONTENT_RATINGS:
        blockers.append(f"unknown content rating: {rating}")
    else:
        allowed = MARKET_COMPLIANCE.get(market, {}).get("content_rating", [])
        if allowed and rating not in allowed:
            blockers.append(f"rating {rating} not allowed in {market} (allowed: {allowed})")
    compliance = check_market_compliance(market, content)
    if not compliance["clean"]:
        blockers.extend(compliance["issues"])
    return {"allowed": not blockers, "market": market, "rating": rating,
            "blockers": blockers, "languages": OVERSEAS_MARKETS[market]["languages"],
            "platforms": OVERSEAS_MARKETS[market]["platforms"],
            "timezone": MARKET_TIMEZONES.get(market, "UTC")}


# ===== NC-SEA-002: Translation pipeline =====

# Built-in genre terminology base; per-project terms come from the persistent
# glossary store (knowledge_items kind='terminology') and take precedence.
TERMINOLOGY_DB: dict[str, dict[str, dict[str, str]]] = {
    "zh": {
        "en": {"主角": "protagonist", "金丹": "Golden Core", "元婴": "Nascent Soul", "修仙": "cultivation"},
        "ja": {"主角": "主人公", "金丹": "金丹", "元婴": "元婴", "修仙": "修仙"},
    }
}


def get_glossary(project_id: str, source_lang: str = "zh", target_lang: str = "en") -> dict[str, str]:
    """NC-SEA-002: 术语表 = 内置基础 + 项目自定义（自定义覆盖内置）。"""
    terms = dict(TERMINOLOGY_DB.get(source_lang, {}).get(target_lang, {}))
    if project_id:
        db = connect()
        rows = db.execute(
            """SELECT meta FROM knowledge_items
               WHERE kind='terminology' AND project_id=%s AND is_deleted=FALSE
                 AND meta->>'source_lang'=%s AND meta->>'target_lang'=%s""",
            (project_id, source_lang, target_lang),
        ).fetchall()
        db.close()
        for r in rows:
            meta = r.get("meta") or {}
            if meta.get("term") and meta.get("translation"):
                terms[meta["term"]] = meta["translation"]
    return terms


def set_glossary_term(project_id: str, source_lang: str, target_lang: str,
                      term: str, translation: str) -> dict:
    """NC-SEA-002: 新增/更新项目术语（同术语幂等更新）。"""
    if not (project_id and term.strip() and translation.strip()):
        return {"status": "error", "message": "project_id/term/translation are required"}
    db = connect()
    existing = db.execute(
        """SELECT id FROM knowledge_items WHERE kind='terminology' AND project_id=%s AND is_deleted=FALSE
           AND meta->>'source_lang'=%s AND meta->>'target_lang'=%s AND meta->>'term'=%s""",
        (project_id, source_lang, target_lang, term.strip()),
    ).fetchone()
    meta = {"source_lang": source_lang, "target_lang": target_lang,
            "term": term.strip(), "translation": translation.strip()}
    if existing:
        db.execute("UPDATE knowledge_items SET meta=%s, updated_at=now() WHERE id=%s",
                   (encode(meta), existing["id"]))
        tid = existing["id"]
    else:
        tid = new_id()
        db.execute(
            "INSERT INTO knowledge_items (id, project_id, kind, title, body, meta) VALUES (%s,%s,'terminology',%s,%s,%s)",
            (tid, project_id, f"{term.strip()} → {translation.strip()}", "", encode(meta)),
        )
    db.commit(); db.close()
    return {"status": "ok", "term_id": str(tid), "term": term.strip(), "translation": translation.strip()}


# ---- 人名本地化：中文名 → 目标市场英文名（如 张翰 → John），全书一致 ----

def get_name_map(novel_id: str, target_lang: str = "en") -> dict[str, str]:
    """NC-SEA-002: 读取小说已持久化的人名映射。"""
    db = connect()
    row = db.execute("SELECT meta FROM contents WHERE id=%s AND type='novel'", (novel_id,)).fetchone()
    db.close()
    if not row:
        return {}
    meta = row.get("meta") or {}
    return dict((meta.get("name_maps") or {}).get(target_lang, {}))


def _persist_name_map(novel_id: str, target_lang: str, name_map: dict[str, str]) -> None:
    db = connect()
    row = db.execute("SELECT meta FROM contents WHERE id=%s AND type='novel'", (novel_id,)).fetchone()
    if not row:
        db.close()
        raise ValueError("novel not found")
    meta = row.get("meta") or {}
    maps = meta.get("name_maps") or {}
    maps[target_lang] = name_map
    db.execute("UPDATE contents SET meta = meta || %s, updated_at=now() WHERE id=%s",
               (encode({"name_maps": maps}), novel_id))
    db.commit(); db.close()


def collect_character_names(novel_id: str) -> list[str]:
    """从人物卡与实体状态收集本书出场人名。"""
    db = connect()
    chars = db.execute(
        "SELECT title, meta->>'character_name' AS cname FROM contents "
        "WHERE parent_id=%s AND type='character' AND is_deleted=FALSE", (novel_id,),
    ).fetchall()
    entities = db.execute(
        """SELECT DISTINCT es.entity_name FROM entity_states es
           JOIN contents c ON c.id = es.chapter_id
           WHERE c.parent_id=%s AND es.entity_type='character'""", (novel_id,),
    ).fetchall()
    db.close()
    names = []
    for r in chars:
        name = (r.get("cname") or r.get("title") or "").strip()
        if name:
            names.append(name)
    for r in entities:
        name = (r.get("entity_name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def build_novel_name_map(novel_id: str, project_id: str, target_lang: str = "en") -> dict:
    """NC-SEA-002: 为整本书生成并持久化人名映射（中文名→英文名，如 张翰→John）。
    已有映射保持不变（跨章一致性）；仅对未映射人名调用真实网关。"""
    existing = get_name_map(novel_id, target_lang)
    names = collect_character_names(novel_id)
    unmapped = [n for n in names if n not in existing]
    if not unmapped:
        return {"status": "ok", "name_map": existing, "newly_mapped": 0, "source": "cached"}

    from app.gateway import complete
    output = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="localize_names", prompt_name="overseas.localize_names",
        variables={
            "names": "、".join(unmapped[:80]),
            "target_lang": target_lang,
            "existing_map": json.dumps(existing, ensure_ascii=False) if existing else "(无)",
        },
    )
    proposed = output.get("name_map", {}) or {}
    merged = dict(existing)
    rejected = []
    used_targets = set(merged.values())
    for source_name in unmapped:
        target = str(proposed.get(source_name, "")).strip()
        # 目标名必须真正本地化：非空、不含中文、且不与已有目标名冲突
        if not target or any("一" <= ch <= "鿿" for ch in target) or target in used_targets:
            rejected.append(source_name)
            continue
        merged[source_name] = target
        used_targets.add(target)
    _persist_name_map(novel_id, target_lang, merged)
    return {"status": "ok", "name_map": merged, "newly_mapped": len(merged) - len(existing),
            "rejected": rejected, "source": "ai_gateway"}


def set_name_mapping(novel_id: str, target_lang: str, source_name: str, target_name: str) -> dict:
    """NC-SEA-002: 人工覆写单个人名映射（编辑终审权）。"""
    if not (source_name.strip() and target_name.strip()):
        return {"status": "error", "message": "source_name/target_name are required"}
    name_map = get_name_map(novel_id, target_lang)
    name_map[source_name.strip()] = target_name.strip()
    _persist_name_map(novel_id, target_lang, name_map)
    return {"status": "ok", "name_map": name_map}


def apply_name_map(text: str, name_map: dict[str, str]) -> tuple[str, dict[str, int]]:
    """确定性兜底替换：译文中残留的中文原名强制替换为映射英文名。"""
    applied: dict[str, int] = {}
    for source_name, target_name in sorted(name_map.items(), key=lambda kv: -len(kv[0])):
        if source_name in text:
            count = text.count(source_name)
            text = text.replace(source_name, target_name)
            applied[source_name] = count
    return text, applied


def translate_text(text: str, source_lang: str = "zh", target_lang: str = "en",
                   project_id: str = "", novel_id: str = "") -> dict:
    """NC-SEA-002: Translate via AI gateway with terminology + name-map consistency."""
    if not project_id:
        raise ValueError("project_id is required for real AI translation")
    terms = get_glossary(project_id, source_lang, target_lang)
    name_map = get_name_map(novel_id, target_lang) if novel_id else {}
    glossary = "\n".join(f"{k} → {v}" for k, v in terms.items())
    names_block = "\n".join(f"{k} → {v}" for k, v in name_map.items())
    from app.gateway import complete
    result = complete(
        run_id=None, node_key=None, project_id=project_id,
        task_type="translate_segment", prompt_name="overseas.translate_segment",
        variables={
            "text": text[:5000],
            "source_lang": source_lang,
            "target_lang": target_lang,
            "glossary": glossary if terms else "(无)",
            "name_map": names_block if name_map else "(无)",
        },
    )
    translated = result.get("translated", result.get("text", ""))
    if not translated:
        raise RuntimeError("AI translation response is empty")
    translated, names_applied = apply_name_map(translated, name_map)
    leftover = [n for n in name_map if n in translated]
    return {
        "source_lang": source_lang, "target_lang": target_lang,
        "original_length": len(text), "translated_length": len(translated),
        "terminology_applied": len(terms), "name_map_applied": names_applied,
        "unlocalized_names": leftover, "text": translated,
        "method": "ai_gateway",
    }


def localize_names(chinese_name: str, target_market: str, novel_id: str = "") -> dict:
    """NC-SEA-002: 查询单个人名的本地化结果（来源：小说持久化映射）。
    无映射时如实返回 unmapped，绝不静默原样冒充已本地化。"""
    target_lang = "en" if target_market.startswith("en") else target_market.split("_")[0]
    if novel_id:
        name_map = get_name_map(novel_id, target_lang)
        if chinese_name in name_map:
            return {"source": "novel_map", "name": chinese_name,
                    "localized": name_map[chinese_name], "target_lang": target_lang}
    return {"source": "unmapped", "name": chinese_name, "localized": None,
            "target_lang": target_lang,
            "hint": "先调用 POST /overseas/name-map 生成全书人名映射或人工设置"}


def localization_consistency_report(novel_id: str, target_lang: str = "en") -> dict:
    """NC-SEA-002: 一致性报告 — 已译章节中：映射人名是否残留中文原名、
    术语原文是否残留、人名映射是否唯一。"""
    name_map = get_name_map(novel_id, target_lang)
    db = connect()
    novel = db.execute("SELECT project_id FROM contents WHERE id=%s AND type='novel'", (novel_id,)).fetchone()
    chapters = db.execute(
        """SELECT id, title, meta->'translations'->>%s AS translated
           FROM contents WHERE parent_id=%s AND type='chapter' AND is_deleted=FALSE
           ORDER BY COALESCE((meta->>'seq')::int, 0)""",
        (target_lang, novel_id),
    ).fetchall()
    db.close()
    if not novel:
        return {"status": "error", "message": "novel not found"}
    terms = get_glossary(novel["project_id"], "zh", target_lang)

    issues = []
    checked = 0
    for ch in chapters:
        translated = ch.get("translated") or ""
        if not translated:
            continue
        checked += 1
        for source_name in name_map:
            if source_name in translated:
                issues.append({"chapter_id": str(ch["id"]), "chapter": ch["title"],
                               "type": "name_not_localized", "detail": f"译文残留原名「{source_name}」（应为 {name_map[source_name]}）"})
        for term in terms:
            if term in translated:
                issues.append({"chapter_id": str(ch["id"]), "chapter": ch["title"],
                               "type": "term_not_translated", "detail": f"译文残留术语「{term}」（应为 {terms[term]}）"})

    duplicate_targets = {}
    for source_name, target in name_map.items():
        duplicate_targets.setdefault(target, []).append(source_name)
    collisions = [{"type": "name_collision", "detail": f"多个角色映射到同一英文名 {t}: {srcs}"}
                  for t, srcs in duplicate_targets.items() if len(srcs) > 1]

    return {"status": "ok", "target_lang": target_lang, "chapters_checked": checked,
            "name_map_size": len(name_map), "issues": issues + collisions,
            "consistent": not (issues or collisions)}


def cultural_adaptation(text: str, target_market: str) -> dict:
    """NC-SEA-002: 文化适配快速探测（确定性检查表）。深度适配由
    translate_chapter 管线中的 cultural_localize 真实 AI 节点完成。"""
    idiom_notes = {
        "打脸": "face-slapping → public humiliation/comeuppance",
        "装逼": "flexing/showing off",
        "内卷": "rat race/cut-throat competition",
        "躺平": "lying flat/opting out",
        "江湖": "jianghu (martial-arts underworld) — 需注释或意译",
        "气运": "fortune/destiny blessing",
    }
    adaptations = [f"{k} → {v}" for k, v in idiom_notes.items() if k in text]
    return {"market": target_market, "adaptations": adaptations, "count": len(adaptations),
            "note": "确定性检查表命中；语义级适配走 cultural_localize AI 节点"}


# ===== NC-SEA-003: Overseas publishing + currency =====

CURRENCY_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 149.5, "KRW": 1310.0, "THB": 34.5, "CNY": 7.24}


def convert_revenue(amount: float, from_currency: str, to_currency: str = "CNY") -> dict:
    """NC-SEA-003: Convert revenue between currencies."""
    usd_amount = amount / CURRENCY_RATES.get(from_currency, 1.0)
    converted = usd_amount * CURRENCY_RATES.get(to_currency, 1.0)
    return {"amount": amount, "from": from_currency, "to": to_currency, "converted": round(converted, 2)}


def publish_overseas(content_id: str, market: str, platform: str, project_id: str = "") -> dict:
    """NC-SEA-003: Publish content to overseas platform with timezone awareness."""
    mkt = OVERSEAS_MARKETS.get(market, {})
    if platform not in mkt.get("platforms", []):
        return {"status": "error", "message": f"{platform} not available in {market}"}
    db = connect()
    if not project_id:
        row = db.execute("SELECT project_id FROM contents WHERE id=%s AND is_deleted=FALSE", (content_id,)).fetchone()
        if not row:
            db.close()
            return {"status": "error", "message": "content not found"}
        project_id = str(row["project_id"])
    pid = new_id()
    db.execute(
        "INSERT INTO published_posts (id, project_id, platform, content_id, title, status, meta) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (pid, project_id, f"overseas_{platform}", content_id, f"Overseas publish: {market}/{platform}",
         "draft", encode({"market": market, "platform": platform, "published_at": datetime.utcnow().isoformat(),
         "mode": "manual_required", "instructions": f"Manual publish required to {platform} in {market} market"})),
    )
    db.commit(); db.close()
    return {"status": "draft", "market": market, "platform": platform, "post_id": pid,
            "mode": "manual_required", "message": f"Overseas publishing is manual only. Content saved as draft in {platform}."}
