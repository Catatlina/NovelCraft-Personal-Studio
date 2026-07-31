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
                        canon: list[str]) -> list[str]:
    """Offline (no LLM) genre-agnostic sanity gate. Returns human-readable flags.

    Two cheap, high-signal checks:
      * protagonist presence — if a lead is anchored, it must appear in the body;
      * near-duplicate names — a token within the text that is >=0.8 similar to a
        canonical name but not equal is a likely name-confusion (Defect 2).
    """
    flags: list[str] = []
    if isinstance(protagonist, dict) and protagonist.get("name") and protagonist["name"] not in text:
        flags.append(f"主角「{protagonist['name']}」未在本章正文出现（可能漂移）")
    if canon:
        tokens = set(re.findall(r"[一-龥]{2,4}", text))
        for tok in tokens:
            for name in canon:
                if tok != name and difflib.SequenceMatcher(None, tok, name).ratio() >= 0.8:
                    flags.append(f"近似人名「{tok}」与既有「{name}」高度相似，疑似混淆")
                    break
            if len(flags) >= 4:
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
    recent = repo.get_recent_summaries(novel_id, limit=10)
    if recent:
        sm = "\n".join(
            f"第{r['chapter_seq']}章：{r['summary']}" for r in reversed(recent)
        )[:3000]
        parts.append("【近期摘要】" + sm)
        included.append("recent_summary_10")
        layers["recent_summary"] = len(sm)

    # protagonist + canonical names anchor (Defects 1 & 2): keep the same lead/POV
    # across chapters, and force the model to reuse existing spellings instead of
    # inventing near-duplicate names.
    prot = repo.get_protagonist(project_id, novel_id)
    canon = repo.get_canonical_names(project_id, novel_id)
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

    context_text = "\n\n".join(parts)
    return context_text, _hash(context_text), included, layers


def _save_chapter_content(project_id: str, novel_id: str, chapter_seq: int,
                          title: str, paragraphs: list[str]) -> str:
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
                (title, encode({"paragraphs": paragraphs, "text": text}), cid),
            )
        else:
            cid = new_id("content")
            conn.execute(
                "INSERT INTO contents (id, project_id, parent_id, type, title, body, seq, status, created_at) "
                "VALUES (%s, %s, %s, 'chapter', %s, %s, %s, 'draft', now())",
                (cid, project_id, novel_id, title, encode({"paragraphs": paragraphs, "text": text}), chapter_seq),
            )
        conn.commit()
    finally:
        conn.close()
    return cid


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

    # 0. context
    ctx = gather_novel_context(project_id, novel_id)
    style_cards = repo.get_style_cards(project_id) or {}
    author_card = decode(style_cards.get("author_card"), {}) or {}
    genre_card = decode(style_cards.get("genre_card"), {}) or {}
    style = ctx.get("style") or json.dumps({**genre_card, **author_card}, ensure_ascii=False)
    bible = repo.get_story_bible(project_id, novel_id)
    context_text, context_hash, included, layers = _build_context_pkg(
        project_id, novel_id, chapter_seq, style, bible
    )
    repo.ensure_book_config(project_id, novel_id, genre=ctx.get("genre", "都市重生"))

    # 1. generate
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
            },
        )
    else:
        out = gateway.complete(
            run_id=run_id, node_key="gen_next", project_id=project_id,
            task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
            user_id=user_id,
            variables={
                "context": context_text,
                "current_title": f"第{chapter_seq}章",
                "current_body": "",
                "review_feedback": "",
            },
        )
    chapter = out.get("chapter", {})
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
                "review_feedback": (
                    f"字数不足：当前 {len(text)} 字，必须扩写至 {MIN_CHAPTER_CHARS} 字以上，"
                    "不得删减既有情节，只做加密加细。"
                ),
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
            rp = gateway.complete(
                run_id=run_id, node_key="repair", project_id=project_id,
                task_type="repair_local", prompt_name="bootstrap.repair_local",
                user_id=user_id,
                variables={"chapter_text": text, "repair_issues": repair_text, "_chapter_outline": ""},
            )
            replacements = rp.get("replacements", []) or []
            new_text, applied = _apply_replacements(text, replacements)
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
            gateway.complete(
                run_id=run_id, node_key="fact_reconcile", project_id=project_id,
                task_type="write_fact_reconcile", prompt_name="bootstrap.write_fact_reconcile",
                user_id=user_id,
                variables={"chapter_text": text, "repair_issues": fact_text},
            )
            report["steps"].append({"step": "fact_reconcile", "candidates": len(fact_issues)})

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
            feedback = "按重新规划的细纲重写本章：" + json.dumps(
                {k: revised.get(k) for k in ("outline", "chapter_goal", "beats", "function_type") if revised.get(k)},
                ensure_ascii=False,
            )
            rw = gateway.complete(
                run_id=run_id, node_key="rewrite", project_id=project_id,
                task_type="gen_next_chapter", prompt_name="narrative.gen_next_chapter",
                user_id=user_id,
                variables={"context": context_text, "current_title": title,
                           "current_body": text, "review_feedback": feedback},
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

    # 4b. chapter summary — the short-term memory layer consumed by later chapters
    smy = gateway.complete(
        run_id=run_id, node_key="summarize", project_id=project_id,
        task_type="summarize_chapter", prompt_name="narrative.summarize_chapter",
        user_id=user_id,
        variables={"body": text, "chapter_seq": chapter_seq},
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
        prompt_version=("gen_chapter1@3.2.0" if chapter_seq == 1 else "gen_next_chapter@3.5.0"),
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

    # Step 7: offline domain_logic gate (no LLM) — protagonist presence + name confusion
    dom_flags = _domain_logic_check(
        text, repo.get_protagonist(project_id, novel_id),
        repo.get_canonical_names(project_id, novel_id),
    )
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

    # 5. accounting: context_package + generation_cost_log (from ai_calls of this run)
    repo.save_context_package(project_id, content_id, chapter_seq, context_hash, included,
                              token_budget=8000, actual_tokens=None, layers=layers)
    cost = _replicate_cost(project_id, run_id, content_id, chapter_seq)
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
        "replan_chapter": ("plan", "replan_chapter"),
        "extract_entities": ("other", "entity_extract"),
        "extract_story_facts": ("other", "fact_extract"),
        "summarize_chapter": ("other", "chapter_summary"),
        "relearn_style": ("other", "style_relearn"),
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
