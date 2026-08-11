"""V6.1.2 single-chapter closed loop.

Pipeline (per chapter):
  generate -> review_7dim_structured -> classify issues (A/B/C routing)
  -> repair_local (with 2nd review + rollback) / fact_reconcile
  -> extract entities -> persist Story Bible (entity_states/knowledge_items
     with confidence gating) -> record context_package + generation_cost_log.

DeepSeek-only. Phase A consumes only style_cards.author_card / genre_card.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from typing import Any

from ..db import connect, decode, encode, new_id, row_to_dict
from .. import gateway
from ..repositories import loop_repos as repo
from .content_policy import analyze_content_policy
from .pov_quality import analyze_third_person_narrative
from ..v7.quality.opening_variation import (
    build_opening_history,
    inspect_opening,
    opening_prompt_block,
    select_opening_plan,
)

# Repair is triggered below this average 7-dim score. Overridable so the repair
# branch can be exercised against real text without faking a review result.
REVIEW_SCORE_THRESHOLD = float(os.environ.get("LOOP_REVIEW_THRESHOLD", "80"))
# The generation prompts already demand >= 2000 chars; this is the enforcement.
MIN_CHAPTER_CHARS = int(os.environ.get("LOOP_MIN_CHAPTER_CHARS", "2000"))
MAX_EXPAND_ATTEMPTS = int(os.environ.get("LOOP_MAX_EXPAND", "2"))
SEV_ORDER = {"high": 3, "medium": 2, "low": 1}
# issue.type -> repair bucket. A = local patch; B = fact reconcile + patch.
_LOCAL_TYPES = {"style", "continuity", "emotion", "pacing"}
_FACT_TYPES = {"plot", "logic", "character"}

# Story Bible confidence gating
ENTITY_CONFIDENCE_DEFAULT = 0.9   # AI-extracted from our own text
ENTITY_CONFIDENCE_MIN = 0.6       # below this the entity is dropped
FACT_CONFIDENCE_DEFAULT = 0.85
FACT_HARD_THRESHOLD = 0.8         # >= -> hard/approved, else soft/pending review


def _as_conf(value: Any, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _iter_known_facts(known_info: Any):
    """Yield {'text','confidence'} world-fact items from the extractor's known_info.

    The extractor is loose: known_info may be a list of {layer,text}, a dict of
    {layer: [text,...]}, or a plain dict/str.  Only world-level facts are
    promoted into knowledge_items.
    """
    if isinstance(known_info, list):
        for it in known_info:
            if isinstance(it, dict) and it.get("text") and it.get("layer") == "world_facts":
                yield {"text": str(it["text"]), "confidence": it.get("confidence")}
    elif isinstance(known_info, dict):
        for item in known_info.get("world_facts", []) or []:
            if isinstance(item, str) and item.strip():
                yield {"text": item.strip(), "confidence": None}
            elif isinstance(item, dict) and item.get("text"):
                yield {"text": str(item["text"]), "confidence": item.get("confidence")}


def _avg_score(score_7dim: dict) -> float:
    if not score_7dim:
        return 0.0
    vals = [float(d.get("score", 0)) for d in score_7dim.values() if isinstance(d, dict)]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _domain_logic_check(text: str, protagonist: dict | None,
                        canon: list[str], *,
                        overdue: list[dict] | None = None,
                        open_after: list[dict] | None = None,
                        cap_tree: dict[str, list[dict]] | None = None) -> list[str]:
    """Offline (no LLM) genre-agnostic sanity gate. Returns human-readable flags.

    Cheap, high-signal checks only — this must stay free to run every chapter:
      * protagonist presence — if a lead is anchored, it must appear in the body;
      * near-duplicate names — a token >=0.8 similar to a canonical name but not
        equal is a likely name-confusion (Defect 2);
      * overdue foreshadowings that survived the chapter unresolved (§4.5);
      * capability over-reach — a skill's stated ``limitations`` keyword shows up
        as something the character just did (§4.3 防降智).
    """
    flags: list[str] = []
    if isinstance(protagonist, dict) and protagonist.get("name"):
        name = protagonist["name"]
        pov = str(protagonist.get("pov") or "").strip()
        if "第一" in pov:
            # First-person narration: the protagonist uses "我", not their name.
            # Check for "我" instead to avoid false positives.
            if "我" not in text:
                flags.append(f"主角「{name}」（第一人称）本章无「我」（可能漂移）")
        elif name not in text:
            flags.append(f"主角「{name}」未在本章正文出现（可能漂移）")
    if canon:
        # Only check tokens whose length equals the canonical name length.
        # Without this, "那老太太"(4 chars) falsely matches "老太太"(3 chars)
        # because SequenceMatcher gives high substring similarity.
        # Skip 2-char names entirely — in Chinese, 2-char words are common nouns
        # ("线球","毛线","老太太" fragments) and produce too many false positives.
        tokens = set(re.findall(r"[一-龥]{3,4}", text))
        name_by_len: dict[int, list[str]] = {}
        for n in canon:
            if len(n) >= 3:
                name_by_len.setdefault(len(n), []).append(n)
        for tok in tokens:
            candidates = name_by_len.get(len(tok), [])
            for name in candidates:
                if tok != name and difflib.SequenceMatcher(None, tok, name).ratio() >= 0.85:
                    flags.append(f"近似人名「{tok}」与既有「{name}」高度相似，疑似混淆")
                    break
            if len(flags) >= 4:
                break

    # overdue foreshadowings the chapter was asked to clear but did not
    if overdue:
        still = {f["id"] for f in (open_after or [])}
        for f in overdue:
            if f["id"] in still:
                flags.append(
                    f"逾期伏笔未回收：「{f['content'][:40]}」"
                    f"（应在第{f['planned_resolve_chapter']}章前回收，重要度{f['importance']}）"
                )
            if len(flags) >= 8:
                break

    # capability over-reach: the limitation text names something the character
    # must NOT be able to do; if that phrase appears as an action in this chapter
    # alongside the character, flag it for human review (warning only, no block).
    if cap_tree:
        for name, caps in list(cap_tree.items())[:6]:
            if name not in text:
                continue
            for cap in caps[:8]:
                if not isinstance(cap, dict):
                    continue
                lim = str(cap.get("limitations") or "").strip()
                if len(lim) < 4:
                    continue
                # take the most content-bearing 2-4 char chunks of the limitation
                for kw in re.findall(r"[一-龥]{3,5}", lim)[:3]:
                    if kw in text:
                        flags.append(
                            f"疑似能力越界：{name} 的「{cap.get('skill')}」限制为「{lim[:30]}」，"
                            f"但本章出现「{kw}」相关情节，请确认未越级"
                        )
                        break
                if len(flags) >= 10:
                    break
    return flags


def gather_novel_context(project_id: str, novel_id: str) -> dict:
    """Pull whatever bootstrap artifacts exist for the novel (graceful on partial)."""
    conn = connect()
    try:
        novel = row_to_dict(
            conn.execute(
                "SELECT title, meta FROM contents WHERE id=%s", (novel_id,)
            ).fetchone()
        )
    finally:
        conn.close()
    meta = decode(novel.get("meta"), {}) if novel else {}
    characters = repo._q(
        "SELECT body FROM knowledge_items WHERE content_id=%s AND kind='character' "
        "AND is_deleted=FALSE ORDER BY created_at LIMIT 20",
        (novel_id,),
    )
    worldviews = repo._q(
        "SELECT body FROM knowledge_items WHERE content_id=%s AND kind='worldview' "
        "AND is_deleted=FALSE ORDER BY created_at LIMIT 5",
        (novel_id,),
    )
    bibles = repo._q(
        "SELECT body FROM knowledge_items WHERE content_id=%s AND kind='creative_bible' "
        "AND is_deleted=FALSE ORDER BY created_at LIMIT 3",
        (novel_id,),
    )
    return {
        "title": novel.get("title") if novel else "",
        "idea": meta.get("idea", ""),
        "genre": meta.get("genre", "都市重生"),
        "style": meta.get("style", ""),
        "characters": "\n".join(str(c["body"]) for c in characters if c.get("body")),
        "worldview": "\n".join(str(c["body"]) for c in worldviews if c.get("body")),
        "synopsis": "\n".join(str(c["body"]) for c in bibles if c.get("body")),
    }


def _build_context_pkg(project_id: str, novel_id: str, chapter_seq: int,
                       style: str, bible: dict) -> tuple[str, str, list[str], dict]:
    """Assemble the fixed+variable context layers.

    Returns (context_text, context_hash, included_layer_names, layer_sizes).
    ``included`` only names layers that actually carried content, so the
    context_package row is an honest record of what the model saw.
    """
    included: list[str] = []
    layers: dict[str, int] = {}
    parts: list[str] = []

    # Chapter number is authoritative and must be stated explicitly — without it
    # the model infers the number from recent summaries and can jump (a rerun of
    # chapter 1 once came back titled "第10章").
    seq_blob = f"本章是第 {chapter_seq} 章，标题必须以「第{chapter_seq}章」开头，不得使用其他编号。"
    parts.append("【当前章序】" + seq_blob)
    included.append("chapter_seq")
    layers["chapter_seq"] = len(seq_blob)

    cfg = repo.get_book_config(project_id, novel_id)
    if cfg:
        rules = decode(cfg.get("immutable_rules"), []) or []
        if rules:
            blob = json.dumps(rules, ensure_ascii=False)
            parts.append("【不可破坏规则】" + blob)
            included.append("immutable_rules")
            layers["immutable_rules"] = len(blob)

    if style:
        parts.append("【作者风格】" + style)
        included.append("style_card")
        layers["style_card"] = len(style)

    ents = bible.get("entities", [])
    facts = bible.get("facts", [])
    if ents or facts:
        sb = json.dumps({"entities": ents, "facts": facts}, ensure_ascii=False)[:6000]
        parts.append("【Story Bible】" + sb)
        included.append("story_bible")
        layers["story_bible"] = len(sb)

    # recent summaries are the short-term layer (not the full chapter text)
    recent = repo.get_recent_summaries(novel_id, limit=10, max_seq=chapter_seq)
    if recent:
        sm = "\n".join(
            f"第{r['chapter_seq']}章：{r['summary']}" for r in reversed(recent)
        )[:3000]
        parts.append("【近期摘要】" + sm)
        included.append("recent_summary_10")
        layers["recent_summary"] = len(sm)

    # Carry the previous chapter's tail so the next chapter opens by continuing
    # the prior scene/hook rather than inventing a new one (Defect: CH2 sofa vs
    # CH1 car-ending). Only meaningful for chapter 2+.
    if chapter_seq > 1:
        prev_tail = repo.get_previous_chapter_tail(novel_id, chapter_seq, tail_chars=800)
        if prev_tail:
            parts.append(
                "【上一章结尾】必须紧接以下结尾继续写，保持同一场景/状态/视角，"
                "不得另起炉灶：\n" + prev_tail
            )
            included.append("prev_chapter_tail")
            layers["prev_chapter_tail"] = len(prev_tail)

    # protagonist + canonical names anchor (Defects 1 & 2): keep the same lead/POV
    # across chapters, and force the model to reuse existing spellings instead of
    # inventing near-duplicate names.
    prot = repo.get_protagonist(project_id, novel_id)
    canon = repo.get_canonical_names(project_id, novel_id, max_seq=chapter_seq)
    if prot or canon:
        anchor_bits = []
        if prot:
            anchor_bits.append(f"主角：{prot['name']}（视角：{prot.get('pov') or '第三人称'}）")
        if canon:
            anchor_bits.append("人物名单（严格复用，禁止近似改名）：" + "、".join(canon[:25]))
        blob = "\n".join(anchor_bits)
        parts.append("【主角锚定】" + blob)
        included.append("anchor")
        layers["anchor"] = len(blob)

    # Foreshadowing ledger (架构 §4.5): overdue items are a hard constraint for
    # this chapter, due_soon must at least be pushed forward. Planting chapters
    # are bounded to <= current_seq so future-planted foreshadowings don't leak in.
    open_fs = repo.get_open_foreshadowings(novel_id, chapter_seq)
    if open_fs:
        overdue = [f for f in open_fs if f["state"] == "overdue"]
        due_soon = [f for f in open_fs if f["state"] == "due_soon"]
        still_open = [f for f in open_fs if f["state"] == "open"]
        fs_bits = []
        if overdue:
            fs_bits.append("⚠️ 已过期（本章必须回收并给出交代）：" + "；".join(
                f"{f['content']}（第{f['planted_at'] or '?'}章埋设，应在第{f['planned_resolve_chapter']}章前回收，"
                f"重要度{f['importance']}）" for f in overdue[:5]))
        if due_soon:
            fs_bits.append("即将到期（本章至少推进一步）：" + "；".join(
                f"{f['content']}（应在第{f['planned_resolve_chapter']}章前回收）" for f in due_soon[:5]))
        if still_open:
            fs_bits.append("未到期（保持存在感，不要遗忘）：" + "；".join(
                f["content"] for f in still_open[:8]))
        blob = "\n".join(fs_bits)[:2500]
        parts.append("【伏笔到期】" + blob)
        included.append("foreshadowing")
        layers["foreshadowing"] = len(blob)

    # Capability tree (架构 §4.3, 防降智): what the cast can and cannot do.
    cap_tree = repo.get_capability_tree(novel_id, [prot["name"]] if prot else None,
                                        max_seq=chapter_seq)
    if not cap_tree and canon:
        cap_tree = repo.get_capability_tree(novel_id, canon[:8], max_seq=chapter_seq)
    if cap_tree:
        cap_bits = []
        for name, caps in list(cap_tree.items())[:6]:
            items = "；".join(
                f"{c.get('skill')}（{c.get('level')}，第{c.get('acquired_chapter') or '?'}章习得"
                + (f"，限制：{c.get('limitations')}" if c.get("limitations") else "") + "）"
                for c in caps[:8] if isinstance(c, dict)
            )
            if items:
                cap_bits.append(f"{name}：{items}")
        if cap_bits:
            blob = "\n".join(cap_bits)[:2500]
            parts.append("【能力树】（只能使用已列能力且受其限制约束，禁止越级或降智）" + blob)
            included.append("capability_tree")
            layers["capability_tree"] = len(blob)

    # Relation arcs (§4.2): inject current relationship state so the model
    # maintains consistency and can naturally evolve relationships. Bounded to
    # arcs last updated strictly before this chapter.
    rel_arcs = repo.get_relation_arcs(novel_id, limit=20, max_seq=chapter_seq)
    if rel_arcs:
        rel_bits = []
        for r in rel_arcs[:12]:
            tp = r.get("turning_points")
            tp_str = ""
            if isinstance(tp, list) and tp:
                tp_str = f"（转折：{'→'.join(str(t) for t in tp[-3:])}）"
            rel_bits.append(
                f"{r['entity_a']} ↔ {r['entity_b']}：{r.get('relation_type','?')}，"
                f"阶段「{r.get('stage','')}」{tp_str}"
            )
        blob = "\n".join(rel_bits)[:2000]
        parts.append("【人物关系】（保持一致性，可自然推进但不可突变）" + blob)
        included.append("relation_arcs")
        layers["relation_arcs"] = len(blob)

    # Emotion balance warning (§5.2): soft suggestion only, not a hard gate.
    # Warns if the recent 20 chapters are heavily skewed toward one emotion.
    recent_emo = repo.get_recent_emotions(novel_id, limit=20)
    if len(recent_emo) >= 8:
        from collections import Counter
        counts = Counter(e["state"] for e in recent_emo)
        total = len(recent_emo)
        dominant, cnt = counts.most_common(1)[0]
        pct = cnt / total * 100
        # Flag if any emotion exceeds 60% of recent chapters
        if pct >= 60:
            hint = (f"近{total}章「{dominant}」占比{pct:.0f}%，"
                    f"建议安排情绪释放或转换（仅供参考，不强制）")
            blob = json.dumps({
                "emotion_balance_warning": {"triggered": True, "dominant": dominant,
                                            "pct": round(pct), "hint": hint},
                "recent_5": [{"ch": e["chapter_seq"], "s": e["state"]}
                             for e in recent_emo[:5]],
            }, ensure_ascii=False)
            parts.append("【情绪曲线】" + blob)
            included.append("emotion_balance")
            layers["emotion_balance"] = len(blob)

    context_text = "\n\n".join(parts)
    return context_text, _hash(context_text), included, layers


_TITLE_SEQ_RE = re.compile(r"^\s*第\s*[0-9零一二三四五六七八九十百千两]+\s*章\s*[:：、.\-—]?\s*")


def normalize_chapter_title(title: str, chapter_seq: int) -> str:
    """Force the stored title to carry the *authoritative* chapter number.

    The model is not trustworthy about numbering: ``bootstrap.gen_chapter1``
    once returned "第10章 ..." for chapter 1, and next-chapter prompts mix
    "第一章" with "第2章".  The DB seq is the single source of truth, so we
    strip whatever prefix the model produced and re-stamp it.
    """
    raw = str(title or "").strip()
    subtitle = _TITLE_SEQ_RE.sub("", raw).strip()
    if not subtitle:
        subtitle = raw or "无题"
    return f"第{chapter_seq}章 {subtitle}"


def _chapter_tiptap_body(paragraphs: list[str], text: str) -> dict:
    """Canonical chapter body.

    The frontend editor/reader renders via a TipTap doc (top-level `content`),
    exactly like the original generation flow writes (see CH1). An earlier
    regen path persisted only `{paragraphs, text}`, which the frontend's
    docToText() could not render -> the chapter showed a blank body. We keep
    `text`/`paragraphs` as siblings for any backend reader, but ALWAYS include
    the TipTap `content` so the chapter displays.
    """
    return {
        "type": "doc",
        "content": [
            # paragraph carries BOTH a bare `text` (what the frontend's
            # docToText()/Editor read) and a nested `content` (standard TipTap
            # doc for the editor to load). Matches the original textToDoc shape.
            {"type": "paragraph", "text": p, "content": [{"type": "text", "text": p}]}
            for p in paragraphs if p
        ],
        "paragraphs": paragraphs,
        "text": text,
    }


def _build_archive_text(ai: dict) -> str:
    """Render the curated 小说永久档案 (author_intent) into a prompt block.

    Consumed by narrative.gen_next_chapter as $archive. Returns "" when the novel
    has no archive configured (other novels are unaffected). See author_intent
    keys: character_cards / plot_timeline / foreshadow_list / hard_constraints.
    """
    if not isinstance(ai, dict):
        return ""
    blocks: list[str] = []

    cards = ai.get("character_cards") or []
    if isinstance(cards, list) and cards:
        lines = ["一、人物卡（严禁改名/另起称呼；外号仅可用括号内标注的别名）："]
        for c in cards:
            if not isinstance(c, dict):
                continue
            name = (c.get("name") or "").strip()
            if not name:
                continue
            aliases = c.get("aliases") or []
            alias_txt = "（外号：" + "、".join(str(a) for a in aliases if str(a).strip()) + "）" if aliases else ""
            role = (c.get("role") or "").strip()
            traits = (c.get("traits") or "").strip()
            bits = [name + alias_txt]
            if role:
                bits.append("身份：" + role)
            if traits:
                bits.append(traits)
            lines.append("- " + "；".join(bits))
        blocks.append("\n".join(lines))

    tl = ai.get("plot_timeline") or []
    if isinstance(tl, list) and tl:
        lines = ["二、已发生剧情时间线（本章须承接最新一章结尾，不得跳脱）："]
        for t in tl:
            if isinstance(t, dict):
                ch = t.get("chapter") or t.get("seq") or ""
                summary = t.get("summary") or ""
                if str(ch).strip() and summary.strip():
                    lines.append(f"- 第{str(ch).strip()}章：{summary.strip()}")
            elif isinstance(t, str) and t.strip():
                lines.append("- " + t.strip())
        blocks.append("\n".join(lines))

    fs = ai.get("foreshadow_list") or []
    if isinstance(fs, list) and fs:
        lines = ["三、当前伏笔清单（须持续推进；可埋新伏笔，但勿强行回收已有伏笔）："]
        for f in fs:
            if isinstance(f, dict):
                fid = f.get("id") or ""
                desc = f.get("description") or f.get("desc") or ""
                if desc.strip():
                    lines.append(f"- 伏笔{fid}：{desc.strip()}" if str(fid).strip() else f"- {desc.strip()}")
            elif isinstance(f, str) and f.strip():
                lines.append("- " + f.strip())
        blocks.append("\n".join(lines))

    hc = ai.get("hard_constraints") or []
    if isinstance(hc, list) and hc:
        lines = ["四、硬红线（绝对禁止，违反即判违规）："]
        for h in hc:
            if isinstance(h, str) and h.strip():
                lines.append("- " + h.strip())
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _save_chapter_content(project_id: str, novel_id: str, chapter_seq: int,
                          title: str, paragraphs: list[str]) -> str:
    title = normalize_chapter_title(title, chapter_seq)
    text = "\n\n".join(paragraphs)
    conn = connect()
    try:
        # reuse an existing chapter row for this seq if present (idempotent re-run)
        existing = row_to_dict(
            conn.execute(
                "SELECT id FROM contents WHERE parent_id=%s AND type='chapter' AND seq=%s "
                "AND is_deleted=FALSE",
                (novel_id, chapter_seq),
            ).fetchone()
        )
        if existing:
            cid = existing["id"]
            conn.execute(
                "UPDATE contents SET title=%s, body=%s, updated_at=now() WHERE id=%s",
                (title, encode(_chapter_tiptap_body(paragraphs, text)), cid),
            )
        else:
            cid = new_id("content")
            conn.execute(
                "INSERT INTO contents (id, project_id, parent_id, type, title, body, seq, status, scope_status, created_at) "
                "VALUES (%s, %s, %s, 'chapter', %s, %s, %s, 'draft', 'canonical', now())",
                (cid, project_id, novel_id, title, encode(_chapter_tiptap_body(paragraphs, text)), chapter_seq),
            )
        conn.commit()
    finally:
        conn.close()
    return cid


def _mark_chapter_quality_status(content_id: str, status: str, reason: str) -> None:
    """Persist an explicit quality state instead of silently publishing a risk."""
    conn = connect()
    try:
        conn.execute(
            "UPDATE contents SET status=%s, meta=COALESCE(meta,'{}'::jsonb) || %s, updated_at=now() WHERE id=%s",
            (status, encode({"quality_status": status, "quality_reason": reason[:1000]}), content_id),
        )
        conn.commit()
    finally:
        conn.close()


def _apply_replacements(text: str, replacements: list[dict]) -> str:
    out = text
    applied = 0
    for r in replacements or []:
        anchor = r.get("anchor", "")
        repl = r.get("replacement", "")
        if anchor and anchor in out:
            out = out.replace(anchor, repl, 1)
            applied += 1
    return out, applied


def _semantic_coherence_check(run_id: str, project_id: str, user_id: str | None, text: str,
                              prev_tail: str, archive_text: str, facts: str) -> tuple[list[str], list[dict]]:
    """⑤ Semantic coherence judge (replaces lexical-only blind spots).

    Cross-references the freshly generated chapter against the curated archive
    (character cards / timeline / foreshadow list / established facts) and the
    previous chapter's tail. Returns (high_severity_violations, all_violations).

    Violation types: name_drift / ooc / plot_contradiction / foreshadow_dropped
    / bridge_broken / factual_error. Only `high` severity (or the structural
    types name_drift / bridge_broken / plot_contradiction) forces a rewrite.

    Provider failure is itself an unverified result. It blocks automatic
    delivery rather than being converted into a clean/low-severity result.
    """
    try:
        out = gateway.complete(
            run_id=run_id, node_key="coherence_verify", project_id=project_id,
            task_type="coherence_verify", prompt_name="narrative.coherence_verify",
            user_id=user_id,
            variables={
                "archive": archive_text or "（无永久档案）",
                "prev_tail": prev_tail or "（首章，无前章结尾）",
                "chapter_text": text,
            },
        )
    except Exception as exc:  # pragma: no cover - provider failure is a gate failure
        detail = f"coherence judge failed: {type(exc).__name__}"
        return [f"[coherence_unverified] {detail}"], [{
            "type": "coherence_unverified", "severity": "high", "detail": detail,
        }]
    vs = out.get("violations") or []
    high: list[str] = []
    for v in vs:
        if not isinstance(v, dict):
            continue
        sev = str(v.get("severity", "")).strip().lower()
        t = str(v.get("type", "")).strip()
        is_structural = t in ("name_drift", "bridge_broken", "plot_contradiction")
        if sev == "high" or is_structural:
            ev = str(v.get("evidence", "")).strip()
            line = f"[{t}] {v.get('detail', '')}"
            if ev:
                line += f" 证据：{ev}"
            high.append(line)
    return high, vs


def run_single_chapter(project_id: str, novel_id: str, chapter_seq: int,
                       *, user_id: str | None = None, run_id: str | None = None,
                       max_rewrites: int = 3) -> dict:
    # ai_calls.run_id is FK -> workflow_runs.id, so a run row must exist.
    run_id = run_id or repo.ensure_workflow_run(
        project_id, novel_id, workflow_key="chapter_loop",
        context={"chapter_seq": chapter_seq},
    )
    report: dict[str, Any] = {
        "run_id": run_id, "project_id": project_id, "novel_id": novel_id,
        "chapter_seq": chapter_seq, "steps": [],
    }
    quality_blocked = False
    quality_block_reasons: list[str] = []

    # 0. context
    ctx = gather_novel_context(project_id, novel_id)
    style_cards = repo.get_style_cards(project_id) or {}
    author_card = decode(style_cards.get("author_card"), {}) or {}
    genre_card = decode(style_cards.get("genre_card"), {}) or {}
    style = ctx.get("style") or json.dumps({**genre_card, **author_card}, ensure_ascii=False)
    bible = repo.get_story_bible(project_id, novel_id, max_seq=chapter_seq)
    # previous-chapter hard facts (fact-lock): injected into gen_next_chapter as a
    # non-negotiable constraint when the novel opts in via author_intent.continuity_facts.
    _bcfg = repo.get_book_config(project_id, novel_id)
    _bai = decode(_bcfg.get("author_intent"), {}) or {} if _bcfg else {}
    prev_facts_var = str(_bai.get("continuity_facts") or "") if isinstance(_bai, dict) else ""
    continuity_facts = prev_facts_var
    archive_var = _build_archive_text(_bai) or "（本书未配置永久档案，按既有设定与上下文续写）"
    context_text, context_hash, included, layers = _build_context_pkg(
        project_id, novel_id, chapter_seq, style, bible
    )
    legacy_history = build_opening_history(
        [
            {"chapter_number": row.get("seq"), "text": row.get("text") or ""}
            for row in repo.get_recent_chapter_bodies(novel_id, limit=3)
            if int(row.get("seq") or 0) < chapter_seq
        ],
        limit=3,
    )
    opening_plan = select_opening_plan(
        chapter_seq,
        previous_history=legacy_history,
        plot_brief={"chapter_type": "normal"},
    )
    opening_contract = opening_prompt_block(opening_plan)
    context_text = context_text + "\n\n" + opening_contract
    included.append("opening_variation")
    layers["opening_variation"] = len(opening_contract)
    context_hash = _hash(context_text)
    repo.ensure_book_config(project_id, novel_id, genre=ctx.get("genre", "都市重生"))

    # 1. generate with layered retry (§6.3 task_retry_policy)
    # Strategy: retry_same → reduce_context → fallback_prompt
    _gen_max = 3
    _gen_exc = None
    out = {}
    for _gen_attempt in range(_gen_max):
        try:
            if chapter_seq == 1:
                out = gateway.complete(
                    run_id=run_id, node_key="gen_chapter1", project_id=project_id,
                    task_type="gen_chapter1", prompt_name="bootstrap.gen_chapter1",
                    user_id=user_id,
                    variables={
                        "selected_title": ctx.get("title", ""),
                        "style": style,
                        "idea": ctx.get("idea", ""),
                        "synopsis": ctx.get("synopsis", ""),
                        "selling_points": "",
                        "worldview": ctx.get("worldview", ""),
                        "characters": ctx.get("characters", ""),
                        "outline": "",
                        "opening_contract": opening_contract,
                    },
                )
            else:
                # reduce_context: on 2nd+ attempt, trim context to 60% of original
                gen_ctx = context_text
                if _gen_attempt == 1:
                    gen_ctx = context_text[:int(len(context_text) * 0.6)]
                elif _gen_attempt >= 2:
                    # fallback_prompt: use minimal context
                    gen_ctx = context_text[:2000]
                out = gateway.complete(
                    run_id=run_id, node_key="gen_next", project_id=project_id,
                    task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
                    user_id=user_id,
                    variables={
                        "context": gen_ctx,
                        "current_title": f"第{chapter_seq}章",
                        "current_body": "",
                        "review_feedback": "",
                        "prev_facts": prev_facts_var,
                        "archive": archive_var,
                        "opening_contract": opening_contract,
                    },
                )
            chapter = out.get("chapter", {})
            if chapter:
                break  # success
        except Exception as exc:
            _gen_exc = exc
            if _gen_attempt < _gen_max - 1:
                report["steps"].append({"step": "gen_retry",
                                        "attempt": _gen_attempt + 1,
                                        "error": f"{type(exc).__name__}: {str(exc)[:80]}"})
                continue
            raise
    chapter = out.get("chapter", {}) if out else {}
    paragraphs = chapter.get("body", []) if isinstance(chapter, dict) else []
    title = chapter.get("title", f"第{chapter_seq}章") if isinstance(chapter, dict) else f"第{chapter_seq}章"
    text = "\n\n".join(paragraphs)
    gen_chars = len(text)

    # 1b. length gate — the prompts demand >= MIN_CHAPTER_CHARS but the model
    # often under-delivers; expand instead of accepting a short chapter.
    expand_attempts = 0
    while len(text) < MIN_CHAPTER_CHARS and expand_attempts < MAX_EXPAND_ATTEMPTS:
        expand_attempts += 1
        exp = gateway.complete(
            run_id=run_id, node_key=f"expand{expand_attempts}", project_id=project_id,
            task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
            user_id=user_id,
            variables={
                "context": context_text,
                "current_title": title,
                "current_body": text,
                "archive": archive_var,
                "prev_facts": prev_facts_var,
                "review_feedback": (
                    f"字数不足：当前 {len(text)} 字，必须扩写至 {MIN_CHAPTER_CHARS} 字以上，"
                    "不得删减既有情节，只做加密加细。"
                ),
                "opening_contract": opening_contract,
            },
        )
        exp_chapter = exp.get("chapter", {})
        exp_paras = exp_chapter.get("body", []) if isinstance(exp_chapter, dict) else []
        exp_text = "\n\n".join(exp_paras)
        if len(exp_text) > len(text):  # never accept a shorter rewrite
            paragraphs, text = exp_paras, exp_text
            title = exp_chapter.get("title") or title

    content_id = _save_chapter_content(project_id, novel_id, chapter_seq, title, paragraphs)
    report["steps"].append({
        "step": "generate", "content_id": content_id, "chars": len(text),
        "chars_first_pass": gen_chars, "expand_attempts": expand_attempts,
        "length_ok": len(text) >= MIN_CHAPTER_CHARS,
    })

    # 1c. Product-wide narrative/content preflight.  The prompt contract is
    # the primary control; this local check only decides whether the legacy
    # compatibility path may spend another rewrite call and whether the final
    # chapter can enter the normal quality loop.
    _cfg = repo.get_book_config(project_id, novel_id)
    _ai = decode(_cfg.get("author_intent"), {}) or {} if _cfg else {}
    _profile = (_ai.get("quality_profile") or {}) if isinstance(_ai, dict) else {}
    if not isinstance(_profile, dict):
        _profile = {}
    if isinstance(_ai, dict) and not _profile.get("genre"):
        _profile["genre"] = _ai.get("genre") or _ai.get("category") or ""
    pov_check = analyze_third_person_narrative(text)
    content_check = analyze_content_policy(text, _profile)
    opening_check = inspect_opening(
        text,
        requested_mode=opening_plan.get("mode"),
        chapter_number=chapter_seq,
        recent_modes=opening_plan.get("forbidden_recent_modes") or [],
    )
    if not pov_check["passed"] or not content_check["passed"] or not opening_check["passed"]:
        feedback_parts = []
        if not pov_check["passed"]:
            feedback_parts.append(
                "叙述视角违规：必须改为第三人称限知。引号内对白/短信/书信中的‘我’可以保留，"
                "引号外叙述不得出现‘我、我们、咱们、俺、吾、余’。"
            )
        if not content_check["passed"]:
            feedback_parts.append(
                "内容安全/架空现实违规：删除脏话、敏感表达；都市题材将现实人名、地名、公司、平台、品牌和事件"
                "全部改成原创虚构实体。普通词‘草’只有在明确植物语境下保留，脏话用干净替代表达。"
            )
        if not opening_check["passed"]:
            feedback_parts.append(
                "开场类型门禁未通过：必须执行指定的" + str(opening_plan.get("label") or opening_plan.get("mode"))
                + "，只重写前300-500字的起笔，保留原有事件、人物、时间线和因果；禁止身体部位+疼痛/一阵/像有人模板。"
            )
        _rp = gateway.complete(
            run_id=run_id, node_key="policy_fix", project_id=project_id,
            task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
            user_id=user_id,
            variables={"context": context_text, "current_title": title,
                       "current_body": text,
                       "review_feedback": "严重违规，必须完整重写表达但保留已发生事件、人物关系、时间线和因果："
                                         + "；".join(feedback_parts),
                       "opening_contract": opening_contract},
        )
        _rp_ch = _rp.get("chapter", {}) or {}
        _rp_paras = _rp_ch.get("body", []) if isinstance(_rp_ch, dict) else []
        _rp_text = "\n\n".join(_rp_paras) if _rp_paras else text
        if len(_rp_text) >= MIN_CHAPTER_CHARS:
            paragraphs, text = _rp_paras, _rp_text
            title = _rp_ch.get("title") or title
            _save_chapter_content(project_id, novel_id, chapter_seq, title, paragraphs)
            pov_check = analyze_third_person_narrative(text)
            content_check = analyze_content_policy(text, _profile)
            opening_check = inspect_opening(
                text,
                requested_mode=opening_plan.get("mode"),
                chapter_number=chapter_seq,
                recent_modes=opening_plan.get("forbidden_recent_modes") or [],
            )
            report["steps"].append({
                "step": "policy_fix", "applied": True,
                "pov_passed": pov_check["passed"],
                "content_policy_passed": content_check["passed"],
            })
        else:
            report["steps"].append({"step": "policy_fix", "applied": False,
                                    "reason": "rewrite too short"})
    report["steps"].append({
        "step": "generation_policy_preflight",
        "pov": pov_check,
        "content_policy": content_check,
        "opening": opening_check,
    })
    if not pov_check["passed"]:
        quality_blocked = True
        quality_block_reasons.append("third_person_narrative_required")
    if not content_check["passed"]:
        quality_blocked = True
        quality_block_reasons.extend(
            str(item.get("code") or "content_policy_failed")
            for item in content_check.get("failures") or []
        )
    if not opening_check["passed"]:
        quality_blocked = True
        quality_block_reasons.extend(
            str(item.get("code") or "opening_variation_failed")
            for item in opening_check.get("flags") or []
        )

    # 1d. continuity fact-lock guard (deterministic backstop for model priors that
    # ignore soft prompt rules). Active only when the novel opts in via
    # author_intent.continuity_* config. Forces a rewrite anchored to the previous
    # chapter's ACTUAL tail until the chapter respects the locked facts.
    if chapter_seq > 1:
        _cfg = repo.get_book_config(project_id, novel_id)
        _ai = decode(_cfg.get("author_intent"), {}) or {} if _cfg else {}
        banned = repo.get_continuity_banned_tokens(project_id, novel_id) or []
        rules = repo.get_continuity_rules(project_id, novel_id) or []
        facts = repo.get_continuity_facts(project_id, novel_id) or ""
        continuity_facts = facts or continuity_facts
        chars = repo.get_continuity_characters(project_id, novel_id) or []
        cards_raw = repo.get_character_cards(project_id, novel_id) or []
        must_names = [c["name"] for c in cards_raw
                      if isinstance(c, dict) and c.get("must_use_canonical") and c.get("name")]
        # Semantic cross-chapter verification is mandatory for every
        # continuation; optional author rules only add deterministic checks.
        if banned or rules or facts or chapter_seq > 1:
            import re as _re
            _death_toks = ["尸体", "丧命", "遇难", "砸死", "压死", "断气",
                           "没了呼吸", "死了", "死掉", "死在", "死人", "死了一"]
            _magic_toks = ["像活的一样", "活的一样", "会发热", "发热", "发烫",
                           "在提醒我", "提醒我这块", "会预警", "暗红色的光",
                           "隔着衣服都烫", "烫了一下", "绿光的眼睛", "泛着暗红",
                           "会说话的", "活物一样"]
            _surname = ("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹"
                        "严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马"
                        "苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬"
                        "安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪"
                        "祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜"
                        "阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏"
                        "蔡田樊胡凌霍万柯卢莫房裘缪干解应宗丁宣贲邓郁单杭洪"
                        "包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊惠甄加封芮羿储"
                        "靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰"
                        "秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜"
                        "黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能"
                        "苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿"
                        "通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容"
                        "向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧"
                        "殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋"
                        "沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓")
            # Only flag the "老X" form (老陈/老孙/老李…) where X is a surname —
            # a strong signal of a newly-named character. We deliberately do NOT
            # match a lone surname char (江/石/陈…) because those appear constantly
            # inside ordinary words (江衍, 石头, 矿工) and would cause false positives.
            _name_re = _re.compile(r'老[' + _surname + r']')

            def _violations(t: str, prev_tail: str = "") -> list[str]:
                v: list[str] = []
                for b in banned:
                    if b and b in t:
                        v.append(f"出现禁用词『{b}』")
                if "no_new_deaths" in rules:
                    for d in _death_toks:
                        if d in t:
                            v.append(f"违禁新增死亡（含『{d}』）；上一章全员生还，本章严禁出现伤亡")
                            break
                if "no_magic_items" in rules:
                    for m in _magic_toks:
                        if m in t:
                            v.append(f"违禁引入超自然/魔法元素（含『{m}』）；上一章为纯现实背景")
                            break
                if "no_new_named_characters" in rules:
                    for nm in _name_re.findall(t):
                        if nm not in chars:
                            v.append(f"新增未授权命名角色（『{nm}』）；本章只允许沿用：{('、'.join(chars) or '无')}")
                if must_names and prev_tail:
                    for mn in must_names:
                        if mn and mn in prev_tail and mn not in t:
                            v.append(f"上一章结尾出现的『{mn}』本章必须沿用其本名，严禁改名或改用其他称呼（外号仅可用档案标注的别名）")
                            break
                return v

            prev_tail = repo.get_previous_chapter_tail(novel_id, chapter_seq, tail_chars=800)
            v0 = _violations(text, prev_tail)
            # ⑤ semantic coherence verify (only when lexical is clean, to bound cost)
            semantic_high: list[str] = []
            if not v0:
                semantic_high, _all_sem = _semantic_coherence_check(
                    run_id, project_id, user_id, text, prev_tail, archive_var, facts)
            fb = ""
            if v0:
                fb = ("【情节承接严重违规】你违背了上一章已确认的硬事实，必须重写：\n"
                      + "\n".join(f"- {x}" for x in v0) + "\n")
                if facts:
                    fb += "\n上一章已确认事实（严禁违背）：\n" + facts + "\n"
                fb += "\n必须紧接上一章结尾原文继续：\n" + (prev_tail or "")
            elif semantic_high:
                fb = ("【语义连贯校验未通过】本章与永久档案/上一章存在连贯性冲突，必须重写：\n"
                      + "\n".join(f"- {x}" for x in semantic_high) + "\n")
                if facts:
                    fb += "\n上一章已确认事实（严禁违背）：\n" + facts + "\n"
                fb += "\n必须紧接上一章结尾原文继续：\n" + (prev_tail or "")
            if fb:
                report["steps"].append({"step": "continuity_guard", "triggered": True,
                                        "lexical": v0[:5], "semantic": semantic_high[:5]})
                applied = False
                for _cg in range(max_rewrites):
                    cg = gateway.complete(
                        run_id=run_id, node_key=f"continuity_fix{_cg+1}",
                        project_id=project_id, task_type="gen_next_chapter",
                        prompt_name="narrative.gen_next_chapter", user_id=user_id,
                        variables={"context": context_text, "current_title": title,
                                   "current_body": "", "review_feedback": fb,
                                   "prev_facts": facts, "archive": archive_var,
                                   "opening_contract": opening_contract},
                    )
                    cg_ch = cg.get("chapter", {}) or {}
                    cg_paras = cg_ch.get("body", []) if isinstance(cg_ch, dict) else []
                    cg_text = "\n\n".join(cg_paras) if cg_paras else ""
                    # accept only when BOTH lexical and semantic are clean
                    if cg_text and len(cg_text) >= MIN_CHAPTER_CHARS and not _violations(cg_text, prev_tail):
                        sem2, _ = _semantic_coherence_check(
                            run_id, project_id, user_id, cg_text, prev_tail, archive_var, facts)
                        if not sem2:
                            paragraphs, text = cg_paras, cg_text
                            title = cg_ch.get("title") or title
                            _save_chapter_content(project_id, novel_id, chapter_seq, title, paragraphs)
                            report["steps"].append({"step": "continuity_guard", "applied": True,
                                                    "attempt": _cg + 1})
                            applied = True
                            break
                report["steps"].append({
                    "step": "continuity_guard",
                    "applied": applied,
                    "reason": None if applied else "exhausted retries; violations remain",
                    "remaining_lexical": _violations(text)[:5] if (not applied and v0) else [],
                    "remaining_semantic": semantic_high[:5] if (not applied and not v0) else [],
                })
                if not applied:
                    quality_blocked = True
                    quality_block_reasons.extend(v0[:3] or semantic_high[:3])

    # 2. review (structured)
    rev = gateway.complete(
        run_id=run_id, node_key="review", project_id=project_id,
        task_type="review_7dim_structured", prompt_name="bootstrap.review_7dim_structured",
        user_id=user_id,
        variables={
            "chapter_text": text,
            "characters": ctx.get("characters", ""),
            "worldview": ctx.get("worldview", ""),
        },
    )
    score_7dim = decode(rev.get("score_7dim"), {}) if isinstance(rev.get("score_7dim"), str) else rev.get("score_7dim", {})
    issues = rev.get("issues", []) or []
    overall = _avg_score(score_7dim)
    review_hash = _hash(json.dumps({"s": score_7dim, "i": issues}, ensure_ascii=False, sort_keys=True))
    repo.save_review(content_id, score_7dim, issues, review_hash,
                     model="deepseek-chat", overall=overall, run_id=run_id,
                     review_type="bootstrap")
    report["steps"].append({"step": "review", "overall_score": overall, "issues": len(issues)})

    # 2b. emotion curve writeback (§5.2): zero LLM, pure rule from review dims
    emo_state = repo.classify_emotion(score_7dim)
    repo.save_emotion_state(project_id, content_id, chapter_seq, emo_state)

    # 3. classify + repair if below threshold
    repairs_done = 0
    if overall < REVIEW_SCORE_THRESHOLD and issues:
        local_issues = [i for i in issues if (i.get("type") in _LOCAL_TYPES) or (i.get("repair_scope") == "local")]
        fact_issues = [i for i in issues if i.get("type") in _FACT_TYPES]

        if local_issues:
            repair_text = "\n".join(
                f"[{i.get('type')}/{i.get('severity')}] {i.get('description','')} (位置：{i.get('location','')})"
                for i in local_issues
            )
            # §6.4 protected_elements: high-importance foreshadowings must not be
            # altered by repair. Extract from open foreshadowings + first chapter events.
            protected = []
            for f in open_before:
                if isinstance(f, dict) and f.get("importance", 0) >= 8:
                    protected.append(f["content"][:60])
            # Also protect the protagonist's first appearance (ch1 anchor)
            if chapter_seq == 1:
                prot_known = repo.get_protagonist(project_id, novel_id)
                if prot_known and prot_known.get("name"):
                    protected.append(f"主角{prot_known['name']}首次出场的关键段落")
            protect_text = "\n".join(f"- {p}" for p in protected[:10]) if protected else ""
            rp = gateway.complete(
                run_id=run_id, node_key="repair", project_id=project_id,
                task_type="repair_local", prompt_name="bootstrap.repair_local",
                user_id=user_id,
                variables={"chapter_text": text, "repair_issues": repair_text,
                           "_chapter_outline": "", "_protected_elements": protect_text},
            )
            replacements = rp.get("replacements", []) or []
            # §6.4 post-repair check: verify protected elements survived
            new_text, applied = _apply_replacements(text, replacements)
            if protected:
                for p in protected:
                    # Check if a protected substring was removed (not present in new text)
                    # but was present in old text. Allow if it was modified in-place.
                    if p in text and p not in new_text:
                        report["steps"].append({"step": "protected_violation",
                                                "element": p[:40], "action": "reverted"})
                        # Revert: use original text for this repair attempt
                        new_text = text
                        applied = 0
                        break
            # 2nd review on repaired text
            rev2 = gateway.complete(
                run_id=run_id, node_key="review2", project_id=project_id,
                task_type="review_7dim_structured", prompt_name="bootstrap.review_7dim_structured",
                user_id=user_id,
                variables={"chapter_text": new_text, "characters": ctx.get("characters", ""), "worldview": ctx.get("worldview", "")},
            )
            s7_2 = (decode(rev2.get("score_7dim"), {})
                    if isinstance(rev2.get("score_7dim"), str) else rev2.get("score_7dim", {}))
            score2 = _avg_score(s7_2)
            repo.save_review(content_id, s7_2, rev2.get("issues", []) or [],
                             _hash(new_text), model="deepseek-chat", overall=score2,
                             run_id=run_id, review_type="post_repair")
            rolled_back = score2 < overall
            final_text = text if rolled_back else new_text
            rid = repo.save_repair_version(
                project_id, content_id, chapter_seq=chapter_seq, repair_type="local",
                repair_scope="local", before_text=text, after_text=new_text,
                reason=f"local issues: {len(local_issues)}", model="deepseek-chat",
            )
            repo.update_repair_status(
                rid, "rollback" if rolled_back else "applied",
                second_review_score=score2, rolled_back=rolled_back,
                reason=f"before={overall} after={score2}",
            )
            if not rolled_back:
                text = final_text
                overall = score2
                _save_chapter_content(project_id, novel_id, chapter_seq, title, [p for p in new_text.split("\n\n") if p.strip()])
                repairs_done += 1
            report["steps"].append({
                "step": "repair_local", "candidates": len(local_issues),
                "replacements_applied": applied, "second_score": score2,
                "rolled_back": rolled_back,
            })

        if fact_issues:
            fact_text = "\n".join(
                f"[{i.get('type')}/{i.get('severity')}] {i.get('description','')}" for i in fact_issues
            )
            reconcile = gateway.complete(
                run_id=run_id, node_key="fact_reconcile", project_id=project_id,
                task_type="write_fact_reconcile", prompt_name="bootstrap.write_fact_reconcile",
                user_id=user_id,
                variables={"chapter_text": text, "repair_issues": fact_text,
                           "_context_window": context_text, "_worldview_text": ctx.get("worldview", "")},
            )
            reconciliation = reconcile.get("reconciliation") or {}
            conflicts_found = int(reconciliation.get("conflicts_found") or 0)
            passed_reconcile = reconciliation.get("passed") is True and conflicts_found == 0
            reconcile_repairs = reconciliation.get("repairs") or reconciliation.get("replacements") or []
            repaired_text, replacements_applied = _apply_replacements(text, reconcile_repairs)
            repair_review_score = None
            repair_review_issues: list[dict] = []
            repair_accepted = False
            if not passed_reconcile and replacements_applied:
                # Fact reconciliation is allowed to repair only exact anchors
                # returned by the provider.  The repaired text must then pass a
                # second structured review before it can clear the blocker.
                rev_fact = gateway.complete(
                    run_id=run_id, node_key="fact_reconcile_review", project_id=project_id,
                    task_type="review_7dim_structured", prompt_name="bootstrap.review_7dim_structured",
                    user_id=user_id,
                    variables={"chapter_text": repaired_text,
                               "characters": ctx.get("characters", ""),
                               "worldview": ctx.get("worldview", "")},
                )
                s7_fact = (decode(rev_fact.get("score_7dim"), {})
                           if isinstance(rev_fact.get("score_7dim"), str)
                           else rev_fact.get("score_7dim", {}))
                repair_review_score = _avg_score(s7_fact)
                repair_review_issues = rev_fact.get("issues", []) or []
                high_fact_issues = [
                    i for i in repair_review_issues
                    if isinstance(i, dict)
                    and i.get("severity") == "high"
                    and i.get("type") in _FACT_TYPES
                ]
                repair_accepted = (
                    not high_fact_issues
                    and repair_review_score >= overall
                )
                report["steps"].append({
                    "step": "fact_reconcile_repair_review",
                    "replacements_applied": replacements_applied,
                    "score": repair_review_score,
                    "high_fact_issues": len(high_fact_issues),
                    "accepted": repair_accepted,
                })
                if repair_accepted:
                    before_fact_repair = text
                    text = repaired_text
                    overall = repair_review_score
                    issues = repair_review_issues
                    _save_chapter_content(
                        project_id, novel_id, chapter_seq, title,
                        [p for p in re.split(r"\n{2,}|\n", text) if p.strip()],
                    )
                    rid = repo.save_repair_version(
                        project_id, content_id, chapter_seq=chapter_seq,
                        repair_type="fact_reconcile", repair_scope="local",
                        before_text=before_fact_repair, after_text=text,
                        reason=f"fact conflicts: {conflicts_found}", model="deepseek-chat",
                    )
                    repo.update_repair_status(
                        rid, "applied", second_review_score=repair_review_score,
                        rolled_back=False,
                        reason=f"fact repair accepted; replacements={replacements_applied}",
                    )
                    repairs_done += 1
            report["steps"].append({
                "step": "fact_reconcile",
                "candidates": len(fact_issues),
                "conflicts_found": conflicts_found,
                "passed": passed_reconcile,
                "replacements_proposed": len(reconcile_repairs),
                "replacements_applied": replacements_applied,
                "repair_accepted": repair_accepted,
            })
            if not passed_reconcile and not repair_accepted:
                quality_blocked = True
                quality_block_reasons.append(
                    f"fact_reconcile not passed (conflicts_found={conflicts_found})"
                )

        # Step 5: C-class major structural issue -> replan + rewrite.
        # Triggered by repair_scope=="chapter" (or high-severity plot/logic). Only
        # from ch2+ (ch1 has no prior context to replan against).
        major_issues = [
            i for i in issues
            if i.get("repair_scope") == "chapter"
            or (i.get("severity") == "high" and i.get("type") in ("plot", "logic"))
        ]
        if major_issues and chapter_seq > 1:
            replan_text = "\n".join(
                f"[{i.get('type')}/{i.get('severity')}] {i.get('description','')}" for i in major_issues
            )
            rp = gateway.complete(
                run_id=run_id, node_key="replan", project_id=project_id,
                task_type="replan_chapter", prompt_name="bootstrap.replan_chapter",
                user_id=user_id,
                variables={"_chapter_outline": text[:2000], "repair_issues": replan_text,
                           "_book_state": context_text[:2000] or "（无）", "_arc_summary": ""},
            )
            revised = rp.get("revised_outline") or {}
            # §5.4 outline versioning: save each replan as a versioned outline
            if revised:
                repo.save_outline_version(
                    project_id, novel_id, chapter_seq, chapter_seq,
                    revised, rationale=f"replan due to {len(major_issues)} major issues",
                )
            feedback = "按重新规划的细纲重写本章：" + json.dumps(
                {k: revised.get(k) for k in ("outline", "chapter_goal", "beats", "function_type") if revised.get(k)},
                ensure_ascii=False,
            )
            rw = gateway.complete(
                run_id=run_id, node_key="rewrite", project_id=project_id,
                task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
                user_id=user_id,
                variables={"context": context_text, "current_title": title,
                           "current_body": text, "review_feedback": feedback,
                           "opening_contract": opening_contract},
            )
            rw_chapter = rw.get("chapter", {}) or {}
            rw_paras = rw_chapter.get("body", []) if isinstance(rw_chapter, dict) else []
            rw_text = "\n\n".join(rw_paras) if rw_paras else text
            if len(rw_text) < MIN_CHAPTER_CHARS:
                rw_text = text  # never accept a too-short rewrite
            rev2 = gateway.complete(
                run_id=run_id, node_key="review2", project_id=project_id,
                task_type="review_7dim_structured", prompt_name="bootstrap.review_7dim_structured",
                user_id=user_id,
                variables={"chapter_text": rw_text, "characters": ctx.get("characters", ""),
                           "worldview": ctx.get("worldview", "")},
            )
            s7_2 = (decode(rev2.get("score_7dim"), {})
                    if isinstance(rev2.get("score_7dim"), str) else rev2.get("score_7dim", {}))
            score2 = _avg_score(s7_2)
            repo.save_review(content_id, s7_2, rev2.get("issues", []) or [], _hash(rw_text),
                             model="deepseek-chat", overall=score2, run_id=run_id,
                             review_type="post_repair")
            rolled_back = score2 < overall
            rid = repo.save_repair_version(
                project_id, content_id, chapter_seq=chapter_seq, repair_type="replan",
                repair_scope="chapter", before_text=text, after_text=rw_text,
                reason=f"major issues: {len(major_issues)}", model="deepseek-chat",
            )
            repo.update_repair_status(
                rid, "rollback" if rolled_back else "applied",
                second_review_score=score2, rolled_back=rolled_back,
                reason=f"before={overall} after={score2}",
            )
            if not rolled_back:
                text = rw_text
                overall = score2
                _save_chapter_content(project_id, novel_id, chapter_seq,
                                      rw_chapter.get("title") or title,
                                      [p for p in rw_text.split("\n\n") if p.strip()])
                repairs_done += 1
            report["steps"].append({"step": "replan_rewrite", "candidates": len(major_issues),
                                     "second_score": score2, "rolled_back": rolled_back})

    # 3b. final semantic humanization.  This is deliberately after local/fact
    # repair and replan so the last prose pass cannot be mistaken for the source
    # of a quality fix.  A final review follows it because even a style-only
    # rewrite must prove that continuity and facts survived.
    humanize_feedback = "\n".join(
        f"[{i.get('type')}/{i.get('severity')}] {i.get('description', '')}"
        for i in issues if isinstance(i, dict)
    )
    style_profile = style if isinstance(style, str) else json.dumps(style, ensure_ascii=False)
    forbidden_changes = "\n".join(
        item for item in (archive_var, continuity_facts, prev_facts_var) if item
    )
    try:
        from .deai_pipeline import DeaiPipeline

        humanized = DeaiPipeline(project_id, content_id, title).final_humanize(
            text,
            source_facts=continuity_facts,
            forbidden_changes=forbidden_changes,
            quality_retry_feedback=humanize_feedback,
            style_profile=style_profile,
            run_id=run_id,
            user_id=user_id,
        )
        humanize_gate = humanized.get("quality_gate") or {}
        if humanize_gate.get("passed") is False:
            quality_blocked = True
            quality_block_reasons.append(
                "final_humanize candidate rejected: "
                + str(humanize_gate.get("message") or humanize_gate.get("code") or "unverified")
            )
        humanized_text = humanized["final_text"]
        humanized_paragraphs = [
            p for p in re.split(r"\n{2,}|\n", humanized_text) if p.strip()
        ]
        text = humanized_text
        paragraphs = humanized_paragraphs
        _save_chapter_content(project_id, novel_id, chapter_seq, title, paragraphs)
        report["steps"].append({
            "step": "final_humanize",
            "applied": humanize_gate.get("passed", True) is not False,
            "quality_blocked": humanize_gate.get("passed") is False,
            "changes": len(humanized.get("changes") or []),
            "ai_patterns_removed": len(humanized.get("ai_patterns_removed") or []),
            "chars": len(text),
        })

        final_semantic_high: list[str] = []
        if chapter_seq > 1:
            final_prev_tail = repo.get_previous_chapter_tail(
                novel_id, chapter_seq, tail_chars=800
            )
            final_semantic_high, _ = _semantic_coherence_check(
                run_id, project_id, user_id, text, final_prev_tail,
                archive_var, continuity_facts,
            )
        final_review = gateway.complete(
            run_id=run_id, node_key="final_humanize_review", project_id=project_id,
            task_type="review_7dim_structured", prompt_name="bootstrap.review_7dim_structured",
            user_id=user_id,
            variables={
                "chapter_text": text,
                "characters": ctx.get("characters", ""),
                "worldview": ctx.get("worldview", ""),
            },
        )
        final_score_7dim = (
            decode(final_review.get("score_7dim"), {})
            if isinstance(final_review.get("score_7dim"), str)
            else final_review.get("score_7dim", {})
        )
        final_issues = final_review.get("issues", []) or []
        final_overall = _avg_score(final_score_7dim)
        repo.save_review(
            content_id, final_score_7dim, final_issues, _hash(text),
            model="deepseek-chat", overall=final_overall, run_id=run_id,
            review_type="final_humanize_review",
        )
        high_final_issues = [
            i for i in final_issues
            if isinstance(i, dict)
            and i.get("severity") == "high"
            and i.get("type") in {"continuity", "plot", "logic", "character"}
        ]
        report["steps"].append({
            "step": "final_humanize_review",
            "overall_score": final_overall,
            "issues": len(final_issues),
            "semantic_violations": len(final_semantic_high),
            "high_structural_issues": len(high_final_issues),
        })
        if final_semantic_high:
            quality_blocked = True
            quality_block_reasons.extend(final_semantic_high[:3])
        if final_overall < REVIEW_SCORE_THRESHOLD or high_final_issues:
            quality_blocked = True
            quality_block_reasons.append(
                f"final_humanize_review below gate (score={final_overall}, "
                f"high_structural_issues={len(high_final_issues)})"
            )
        overall = final_overall
        score_7dim = final_score_7dim
        issues = final_issues
    except Exception as exc:
        # The chapter remains persisted for human review, but this is never
        # converted into a successful delivery or a heuristic fallback.
        quality_blocked = True
        quality_block_reasons.append(f"final_humanize_unverified: {type(exc).__name__}")
        report["steps"].append({
            "step": "final_humanize",
            "applied": False,
            "quality_blocked": True,
            "error": f"{type(exc).__name__}: {str(exc)[:120]}",
        })

    # Do not let an unverified chapter poison the long-term Story Bible.  The
    # raw chapter and quality evidence remain available for a human repair, but
    # entity/fact/archive writeback waits until the chapter passes the gate.
    if quality_blocked:
        repo.save_context_package(project_id, content_id, chapter_seq, context_hash, included,
                                  token_budget=8000, actual_tokens=None, layers=layers)
        cost = _replicate_cost(project_id, run_id, content_id, chapter_seq)
        reason = "; ".join(quality_block_reasons) or "continuity or fact verification was not proven"
        _mark_chapter_quality_status(content_id, "needs_review", reason)
        repo.finish_workflow_run(run_id, "needs_review")
        report.update({
            "final_score": overall,
            "chars": len(text),
            "repairs_done": repairs_done,
            "content_id": content_id,
            "cost": cost,
            "ok": False,
            "status": "needs_review",
            "quality_blocked": True,
            "quality_block_reasons": quality_block_reasons[:10],
            "memory_write_suppressed": True,
        })
        return report

    # 4. persist Story Bible (entity extraction + confidence gating)
    ent = gateway.complete(
        run_id=run_id, node_key="extract", project_id=project_id,
        task_type="extract_entities", prompt_name="narrative.extract_entities",
        user_id=user_id,
        variables={"body": text},
    )
    # Focused second pass: protagonist + facts(with real confidence) + plot_threads
    # + world_state. Splitting out of extract_entities because a single overloaded
    # prompt reliably drops the extra top-level fields (observed: model returned
    # only `entities`).
    sf = gateway.complete(
        run_id=run_id, node_key="extract_facts", project_id=project_id,
        task_type="extract_story_facts", prompt_name="narrative.extract_story_facts",
        user_id=user_id,
        variables={"body": text},
    )
    ent_written = 0
    fact_written = 0
    plot_written = 0
    seen: set[tuple[str, str]] = set()
    # Defect 1: anchor the protagonist. Prefer the dedicated extraction call; fall
    # back to the character whose known_info is tagged protagonist_known (robust
    # when the model omits the field). POV defaults to 第三人称 for web novels.
    prot = sf.get("protagonist") or {}
    if not prot.get("name"):
        for e in ent.get("entities", []) or []:
            layers = [k.get("layer") for k in (e.get("known_info") or []) if isinstance(k, dict)]
            if "protagonist_known" in layers:
                prot = {"name": e.get("name"), "pov": "第三人称"}
                break
    if prot.get("name"):
        if chapter_seq == 1 or not repo.get_protagonist(project_id, novel_id):
            repo.save_protagonist(project_id, novel_id, prot["name"], prot.get("pov", "第三人称"))
    for e in ent.get("entities", []) or []:
        if not e.get("name"):
            continue
        key = (str(e.get("type") or "character"), str(e.get("name")).strip())
        if key in seen:  # dedup within chapter
            continue
        seen.add(key)
        e_conf = _as_conf(e.get("confidence"), ENTITY_CONFIDENCE_DEFAULT)
        if e_conf < ENTITY_CONFIDENCE_MIN:
            continue  # confidence gating: too weak to enter Story Bible
        # entity_states is per-chapter: anchor the snapshot on this chapter
        repo.upsert_entity_state(content_id, {
            "type": e.get("type", "character"), "name": e.get("name", ""),
            "state": e.get("state", ""), "location": e.get("location", ""),
            "relationships": e.get("relationships", {}),
            "possessions": e.get("possessions", []),
            "known_info": e.get("known_info"),
            "confidence": e_conf,
            "importance_level": e.get("importance_level", 5),
        })
        ent_written += 1
        for ki in _iter_known_facts(e.get("known_info")):
            f_conf = _as_conf(ki.get("confidence"), FACT_CONFIDENCE_DEFAULT)
            hard = f_conf >= FACT_HARD_THRESHOLD
            repo.save_knowledge_fact(project_id, novel_id, {
                "kind": "fact", "body": ki["text"],
                "fact_type": "hard" if hard else "soft",
                "approved": hard,
                "confidence": f_conf, "source_chapter": chapter_seq,
            })
            fact_written += 1
    # Defect 3: facts returned with real confidence + fact_type (focused call)
    for f in sf.get("facts", []) or []:
        f_text = f.get("text") if isinstance(f, dict) else str(f)
        if not f_text or not str(f_text).strip():
            continue
        f_conf = _as_conf(f.get("confidence") if isinstance(f, dict) else None, FACT_CONFIDENCE_DEFAULT)
        f_type = (f.get("fact_type") if isinstance(f, dict) else None) \
            or ("hard" if f_conf >= FACT_HARD_THRESHOLD else "soft")
        repo.save_knowledge_fact(project_id, novel_id, {
            "kind": "fact", "body": str(f_text).strip(),
            "fact_type": f_type, "approved": f_type == "hard",
            "confidence": f_conf, "source_chapter": chapter_seq,
        })
        fact_written += 1
    # Step 4: plot_threads + world_state writeback (focused call)
    for t in sf.get("plot_threads", []) or []:
        if isinstance(t, dict) and t.get("name"):
            repo.save_plot_thread(project_id, novel_id, {**t, "last_chapter_seq": chapter_seq})
            plot_written += 1
    ws = sf.get("world_state")
    world_written = 0
    if isinstance(ws, dict) and ws:
        repo.save_world_state(project_id, novel_id, chapter_seq, ws)
        world_written += 1
    report["steps"].append({
        "step": "story_bible",
        "entities_extracted": len(ent.get("entities", []) or []),
        "entities_written": ent_written,
        "facts_written": fact_written,
        "plot_threads_written": plot_written,
        "world_state_written": world_written,
        "protagonist": prot.get("name"),
    })

    # 4a2. ledger writeback: foreshadowings + capability tree + character arc
    # (架构 §4.2/§4.3/§4.5). Kept as its own focused call for the same reason as
    # extract_story_facts — overloading one prompt loses top-level fields.
    open_before = repo.get_open_foreshadowings(novel_id, chapter_seq)
    known_caps = repo.get_capability_tree(novel_id)
    ledger = gateway.complete(
        run_id=run_id, node_key="extract_ledger", project_id=project_id,
        task_type="extract_ledger", prompt_name="narrative.extract_ledger",
        user_id=user_id,
        variables={
            "body": text,
            "seq": chapter_seq,
            "open_count": len(open_before),
            "open_foreshadowings": "\n".join(
                f"- {f['content']}（重要度{f['importance']}，应在第{f['planned_resolve_chapter']}章前回收）"
                for f in open_before[:15]
            ) or "（暂无）",
            "known_capabilities": "\n".join(
                f"- {name}：" + "；".join(
                    f"{c.get('skill')}({c.get('level')})" for c in caps[:8] if isinstance(c, dict)
                ) for name, caps in list(known_caps.items())[:8]
            ) or "（暂无）",
        },
    )
    fs_written = 0
    for item in ledger.get("foreshadowings", []) or []:
        if isinstance(item, dict) and repo.save_foreshadowing(content_id, chapter_seq, item):
            fs_written += 1
    fs_resolved = 0
    for item in ledger.get("resolved", []) or []:
        c = item.get("content") if isinstance(item, dict) else str(item)
        if c and repo.resolve_foreshadowing(novel_id, c, content_id):
            fs_resolved += 1
    cap_written = 0
    for ch in ledger.get("capability_changes", []) or []:
        if isinstance(ch, dict) and ch.get("entity") and ch.get("skill"):
            # evidence is mandatory: no evidence => not a real acquisition
            if not str(ch.get("evidence") or "").strip():
                continue
            repo.upsert_capability(content_id, ch["entity"],
                                   {**ch, "acquired_chapter": chapter_seq})
            cap_written += 1
    arc_written = 0
    for a in ledger.get("arc_updates", []) or []:
        if isinstance(a, dict) and a.get("entity"):
            repo.upsert_character_arc(content_id, a["entity"], a)
            arc_written += 1
    rel_written = 0
    for rc in ledger.get("relation_changes", []) or []:
        if isinstance(rc, dict) and rc.get("entity_a") and rc.get("entity_b"):
            repo.upsert_relation_arc(
                project_id, novel_id, chapter_seq,
                rc["entity_a"], rc["entity_b"],
                rc.get("relation_type", "unknown"),
                rc.get("stage", ""),
                rc.get("turning_point", ""),
            )
            rel_written += 1
    # honest accounting: how many overdue items the chapter was told to clear
    overdue_before = [f for f in open_before if f["state"] == "overdue"]
    report["steps"].append({
        "step": "ledger",
        "foreshadowings_planted": fs_written,
        "foreshadowings_resolved": fs_resolved,
        "overdue_at_start": len(overdue_before),
        "capabilities_written": cap_written,
        "arcs_written": arc_written,
        "relations_written": rel_written,
    })

    # 4a3. 永久档案自动回写（④）：每章生成后由 AI 萃取并合并写回 author_intent，
    # 使命名门禁与 $archive 注入的真相源由系统自动维护，不再依赖手工策展；
    # 首章也会自动建立档案，使后续章节天然连贯。
    try:
        prev_archive_txt = _build_archive_text(_bai) or "（空，本书首次建立永久档案）"
        au = gateway.complete(
            run_id=run_id, node_key="archive_update", project_id=project_id,
            task_type="archive_update", prompt_name="narrative.archive_update",
            user_id=user_id,
            variables={"prev_archive": prev_archive_txt,
                       "chapter_seq": chapter_seq, "chapter_text": text},
        )
        derived = {k: au.get(k) for k in ("character_cards", "plot_timeline",
                                          "foreshadow_list", "continuity_facts",
                                          "hard_constraints")}
        if any(v is not None for v in derived.values()):
            repo.write_archive_derived(project_id, novel_id, derived)
            report["steps"].append({"step": "archive_update",
                                    "derived": [k for k, v in derived.items() if v is not None]})
    except Exception as exc:
        report["steps"].append({"step": "archive_update", "applied": False,
                                "error": f"{type(exc).__name__}: {str(exc)[:80]}"})

    # 4b. chapter summary — the short-term memory layer consumed by later chapters
    prot_for_summary = repo.get_protagonist(project_id, novel_id)
    prot_summary_var = ""
    if isinstance(prot_for_summary, dict) and prot_for_summary.get("name"):
        prot_summary_var = f"{prot_for_summary['name']}（视角：{prot_for_summary.get('pov') or '第三人称'}）"
    smy = gateway.complete(
        run_id=run_id, node_key="summarize", project_id=project_id,
        task_type="summarize_chapter", prompt_name="narrative.summarize_chapter",
        user_id=user_id,
        variables={"body": text, "chapter_seq": chapter_seq, "protagonist": prot_summary_var},
    )
    summary_text = str(smy.get("summary") or "").strip()
    if summary_text:
        key_chars = [e.get("name") for e in (smy.get("entities") or [])
                     if isinstance(e, dict) and e.get("type") == "character" and e.get("name")]
        repo.save_chapter_summary(
            project_id, content_id, chapter_seq, summary_text,
            summary_type="chapter", generated_by="deepseek",
            key_chars=key_chars[:10],
        )
    report["steps"].append({"step": "summary", "chars": len(summary_text)})

    # 4c. lock snapshot (防历史漂移) + roll-up arc summary every 10 chapters
    repo.save_chapter_snapshot(
        project_id, content_id, chapter_seq, _hash(text),
        entity_state_hash=_hash(json.dumps(bible.get("entities", []), ensure_ascii=False)),
        prompt_version=("gen_chapter1@3.3.0" if chapter_seq == 1 else "gen_next_chapter@3.6.0"),
        model="deepseek-chat",
    )
    if chapter_seq % 10 == 0:
        recent = repo.get_recent_summaries(novel_id, limit=10)
        joined = "\n".join(f"第{r['chapter_seq']}章：{r['summary']}" for r in reversed(recent))
        if joined:
            arc = gateway.complete(
                run_id=run_id, node_key="arc_summary", project_id=project_id,
                task_type="summarize_chapter", prompt_name="narrative.summarize_chapter",
                user_id=user_id,
                variables={"instructions": "将以下多章摘要压缩为一段约150字的卷级弧线总结", "body": joined},
            )
            arc_text = str(arc.get("summary") or "").strip()
            if arc_text:
                repo.save_arc_summary(project_id, novel_id, chapter_seq // 10, arc_text)
        report["steps"].append({"step": "arc_summary", "volume_seq": chapter_seq // 10})

    # Step 7: offline domain_logic gate (no LLM) — protagonist presence, name
    # confusion, un-cleared overdue foreshadowings, capability over-reach,
    # and genre-specific checks (§6.2 domain plugins).
    dom_flags = _domain_logic_check(
        text, repo.get_protagonist(project_id, novel_id),
        repo.get_canonical_names(project_id, novel_id),
        overdue=overdue_before,
        open_after=repo.get_open_foreshadowings(novel_id, chapter_seq),
        cap_tree=repo.get_capability_tree(novel_id),
    )
    # Genre-specific plugin checks (§6.2): load plugin based on book_config.genre
    from app.services.domain_plugins import run_domain_checks
    cfg_for_genre = repo.get_book_config(project_id, novel_id)
    genre = ""
    if cfg_for_genre:
        genre = decode(cfg_for_genre.get("genre"), "") or ""
    genre_flags = run_domain_checks(text, genre)
    dom_flags.extend(genre_flags)
    if dom_flags:
        report["steps"].append({"step": "domain_logic", "flags": dom_flags})

    # Step 6: style relearn every 10 chapters (real LLM call, gated to ch10/20/...)
    if chapter_seq % 10 == 0:
        bodies = repo.get_recent_chapter_bodies(novel_id, limit=10)
        corpus = "\n\n".join(f"[第{b['seq']}章]\n{b['text']}" for b in bodies if b["text"])
        if corpus:
            rl = gateway.complete(
                run_id=run_id, node_key="relearn_style", project_id=project_id,
                task_type="relearn_style", prompt_name="bootstrap.relearn_style",
                user_id=user_id, variables={"recent_chapters": corpus},
            )
            card = rl.get("author_card") or {}
            if isinstance(card, dict) and card:
                res = repo.save_style_relearn(project_id, novel_id, card)
                report["steps"].append({"step": "style_relearn",
                                        "learn_count": res["learn_count"],
                                        "applied": res["applied"]})

    # 5a. audit report every 100 chapters (§10.3): zero LLM, rule-aggregated
    if chapter_seq % 100 == 0 and chapter_seq > 0:
        # character_changes: compare arc stages at ch1 and ch100
        arc_rows = repo._q(
            "SELECT es.entity_name, es.character_arc, c.seq FROM entity_states es "
            "JOIN contents c ON c.id=es.chapter_id "
            "WHERE c.parent_id=%s AND c.is_deleted=FALSE AND es.entity_type='character' "
            "AND es.character_arc <> '{}'::jsonb ORDER BY c.seq",
            (novel_id,),
        )
        seen_names: dict[str, dict] = {}
        for r in arc_rows:
            n = r.get("entity_name")
            if n and n not in seen_names:
                seen_names[n] = {"first_seq": r.get("seq"), "first_arc": r.get("character_arc", {})}
            if n:
                seen_names[n]["last_arc"] = r.get("character_arc", {})
        char_changes = []
        for name, info in seen_names.items():
            fa = info.get("first_arc", {})
            la = info.get("last_arc", {})
            if isinstance(fa, dict) and isinstance(la, dict):
                fs = fa.get("current_arc_stage", "")
                ls = la.get("current_arc_stage", "")
                if fs and ls and fs != ls:
                    char_changes.append(f"{name}：{fs}→{ls}")
        # capability_changes: aggregate all caps from Story Bible
        cap_tree_all = repo.get_capability_tree(novel_id)
        cap_changes = []
        for cname, caps in cap_tree_all.items():
            for c in caps:
                if isinstance(c, dict) and c.get("skill"):
                    cap_changes.append(
                        f"{cname}：{c['skill']}({c.get('level','?')}@第{c.get('acquired_chapter','?')}章)")
        # foreshadowing status
        open_fs = repo.get_open_foreshadowings(novel_id, chapter_seq)
        fs_status = {"open": 0, "overdue": 0, "due_soon": 0}
        for f in open_fs:
            st = f.get("state", "open")
            if st in fs_status:
                fs_status[st] += 1
        repo.save_audit_report(
            project_id, novel_id, chapter_seq,
            character_changes=char_changes[:20],
            capability_changes=cap_changes[:20],
            foreshadowing_status=fs_status,
            style_drift={},
        )
        report["steps"].append({"step": "audit_report", "at_chapter": chapter_seq,
                                "char_changes": len(char_changes),
                                "cap_changes": len(cap_changes),
                                "foreshadowing": fs_status})

    # 5. accounting: context_package + generation_cost_log (from ai_calls of this run)
    repo.save_context_package(project_id, content_id, chapter_seq, context_hash, included,
                              token_budget=8000, actual_tokens=None, layers=layers)
    cost = _replicate_cost(project_id, run_id, content_id, chapter_seq)
    if quality_blocked:
        reason = "; ".join(quality_block_reasons) or (
            "continuity or fact verification was not proven"
        )
        _mark_chapter_quality_status(content_id, "needs_review", reason)
        repo.finish_workflow_run(run_id, "needs_review")
        report["final_score"] = overall
        report["chars"] = len(text)
        report["repairs_done"] = repairs_done
        report["content_id"] = content_id
        report["cost"] = cost
        report["ok"] = False
        report["status"] = "needs_review"
        report["quality_blocked"] = True
        report["quality_block_reasons"] = quality_block_reasons[:10]
        return report

    repo.record_book_status(
        project_id, novel_id, "serializing",
        reason=f"chapter loop started at ch{chapter_seq}",
    )
    repo.finish_workflow_run(run_id, "succeeded")
    report["final_score"] = overall
    report["chars"] = len(text)
    report["repairs_done"] = repairs_done
    report["content_id"] = content_id
    report["cost"] = cost
    report["ok"] = True
    report["status"] = "succeeded"
    return report


def _replicate_cost(project_id: str, run_id: str, content_id: str,
                    chapter_seq: int) -> dict:
    """Mirror this run's ai_calls into generation_cost_log (phase/task_type split)."""
    phase_map = {
        "gen_chapter1": ("generate", "chapter_generate"),
        "gen_next_chapter": ("generate", "chapter_generate"),
        "review_7dim_structured": ("review", "chapter_review"),
        "repair_local": ("repair", "repair_local"),
        "write_fact_reconcile": ("repair", "fact_reconcile"),
        "final_humanize": ("repair", "final_humanize"),
        "replan_chapter": ("plan", "replan_chapter"),
        "extract_entities": ("other", "entity_extract"),
        "extract_story_facts": ("other", "fact_extract"),
        "summarize_chapter": ("other", "chapter_summary"),
        "relearn_style": ("other", "style_relearn"),
        "extract_ledger": ("other", "ledger_extract"),
    }
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT prompt_name, model, prompt_tokens, completion_tokens, cost_cny, status "
            "FROM ai_calls WHERE run_id=%s", (run_id,)
        ).fetchall()
    finally:
        conn.close()
    cost_rows = []
    for r in rows:
        d = row_to_dict(r)
        # prompt_name is namespaced ("bootstrap.review_7dim_structured"); key on the leaf
        leaf = str(d.get("prompt_name") or "").rsplit(".", 1)[-1]
        phase, task_type = phase_map.get(leaf, ("other", "other"))
        cost_rows.append({
            "content_id": content_id, "chapter_seq": chapter_seq, "phase": phase,
            "task_type": task_type, "model": d.get("model"),
            "prompt_tokens": d.get("prompt_tokens") or 0,
            "completion_tokens": d.get("completion_tokens") or 0,
            "cost_cny": float(d.get("cost_cny") or 0),
            "success": (d.get("status") or "success") in ("success", "ok", "succeeded"),
        })
    if cost_rows:
        repo.save_generation_cost_log(project_id, cost_rows)
    return {
        "calls": len(cost_rows),
        "tokens": sum(r["prompt_tokens"] + r["completion_tokens"] for r in cost_rows),
        "cost_cny": round(sum(r["cost_cny"] for r in cost_rows), 6),
        "by_task": {
            t: sum(1 for r in cost_rows if r["task_type"] == t)
            for t in sorted({r["task_type"] for r in cost_rows})
        },
    }
