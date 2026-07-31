# 数据库 Schema 设计稿 v1（对齐 v6.1.1 封版 + 现有代码事实）

> 状态：设计稿（**仅文档，未落地代码**）。下一步经用户确认后转 Alembic 迁移实现。
> 日期：2026-07-31
> 依据：架构文档 `docs/architecture_v6.1.md` §4.1 表清单 + 现有代码事实核对（`docs/NovelCraft-开发文档/09-数据库设计文档.md`、Alembic 迁移、`app/db.py`）

---

## 0. 现有代码事实（决定了"怎么建表"，必须先看）

1. **建表机制 = Alembic 纯 SQL 迁移，无 SQLAlchemy ORM 模型。**
   - `backend/alembic/versions/*.py` 全部用 `CREATE TABLE IF NOT EXISTS ...`（raw SQL），`upgrade()` / `downgrade()` 对称。
   - `app/db.py::init_db()` 只做**种子**（prompts / model_routes / sensitive_words / strategy），并幂等 `CREATE TABLE IF NOT EXISTS strategy` 兜底；**核心表 DDL 在 Alembic 迁移里**。
   - 数据访问层是 `app/db.py` 的 `DB` 封装（`db.execute(sql, params).fetchone()`，返回 dict），**没有 ORM 模型类**——所以本设计稿只给 DDL + 访问约定，不给 model 类。
   - 主键用 `uuid_generate_v7()`（PG 扩展，现有表统一）；JSON 用 `JSONB`；时间用 `TIMESTAMPTZ`。

2. **现有表与 v6.1.1 概念的映射**（核对自 09 文档 + Alembic）：

   | v6.1.1 概念 | 现有真实表 | 现状 | 本稿动作 |
   |---|---|---|---|
   | 书级配置 `book_config` | 无（contents.type='novel' 仅存树） | 缺失 | **新建** |
   | Context 装配 `context_package` | 无（ai_calls.input 含装配日志但非结构化） | 缺失 | **新建** |
   | 双级摘要 `chapter_summary` / `arc_summary` | 无 | 缺失 | **新建** 两张 |
   | 世界状态 `world_state` | 无 | 缺失 | **新建** |
   | 剧情线 `plot_threads` | 无（arcs 是人物弧线，非剧情线） | 缺失 | **新建** |
   | 情绪曲线 `chapter_emotion_state` | 无 | 缺失 | **新建** |
   | 百章审计 `chapter_audit_report` | 无 | 缺失 | **新建** |
   | 实体 `entities` | `entity_states`（已有 `entity_type`） | 有 `entity_type`，**缺 `importance_level`** | **ALTER 加一列** |
   | 伏笔 `foreshadowing_ledger` | `foreshadowings` | 有 planted/pending/paid_off，缺 window/awareness/importance | P1 ALTER（本稿列 DDL，本期可不急） |
   | 时间线 `timeline` | `timeline_events` | 够用 | 复用 |
   | 人物弧线 | `arcs` | 够用 | 复用 |
   | 审核 `review_7dim` | `reviews`（score_7dim + issues JSONB） | issues 现为字符串/对象数组，**无 type/severity** | **ALTER 升级 issues 结构**（P0 必做） |
   | Style Card | `knowledge_items`（kind='style_card'） | 已存在机制 | 复用 + 加 `style_change_confidence` 字段（本稿列） |
   | Prompt Registry | `prompts`（name/version/model/template/golden_cases） | 已存在，匹配架构 | 复用 |
   | 模型路由 | `model_routes`（task_type/provider/model/**params_json**） | 已存在；注意列名是 `params_json` 非 `params` | 复用 |
   |  lineage / 可追溯 | `ai_calls`（input 含 7 层装配日志） | 已存在 | 复用；context_package 与之互补 |

3. **Provider 抽象（v6.1.1 §9.1）是代码层改动（`app/gateway.py` / `app/ai/providers.py`），不涉及新表**——本稿不覆盖，单独在代码实现阶段处理。

---

## 1. 落地分期（与 architecture_v6.1 §13 对齐）

- **Phase A（单章闭环 MVP 必需，最少改动）**：`reviews.issues` 结构化升级 + `entity_states` 加 `importance_level`。这两项是"分类路由 + Context Builder 选择性加载"的前提，且都只动现有表。
- **Phase B（完整管线新表）**：`book_config` / `context_package` / `chapter_summaries` / `arc_summary` / `world_state` / `plot_threads` / `chapter_emotion_state` / `chapter_audit_report` + `foreshadowings` 增强 + `knowledge_items`(style_card) 加置信度。
- 一期迁移文件建议：Phase A、B 各一个 Alembic revision（或合并为一个"v6.1.1 schema" revision），`upgrade` 全 `CREATE TABLE IF NOT EXISTS` + `ALTER ... ADD COLUMN IF NOT EXISTS`，`downgrade` 对称 `DROP`/`ALTER DROP COLUMN`。

---

## 2. Phase A：现有表变更 DDL

### 2.1 `entity_states` 加 `importance_level`（实体分级，Context Builder 选择性加载）

```sql
ALTER TABLE entity_states
  ADD COLUMN IF NOT EXISTS importance_level INTEGER NOT NULL DEFAULT 5
  CHECK (importance_level BETWEEN 1 AND 10);

COMMENT ON COLUMN entity_states.importance_level IS
  '实体重要度 1-10：Context Builder 仅加载 >= 阈值（默认 >=6）的实体，防止第500章加载"村口老王"浪费 token';
```

> 说明：`entity_type` 列已存在（CHECK 含 character/location/organization/item/concept），无需再加。`importance_level` 默认 5，主角是 10，路人 1-3。

### 2.2 `reviews.issues` 结构化升级（支撑分类路由 A/B/C）

现有 `issues JSONB DEFAULT '[]'`。改为结构化对象数组（向后兼容：旧数据是字符串数组，读取时归一化）。

```sql
-- 不换列类型（仍是 JSONB），约定写入结构如下；读取端做兼容：
--   issues = [{"type":"style|continuity|plot","severity":"high|medium|low",
--              "detail":"...","repair_scope":"local|section|chapter","anchor":null}]
-- 旧格式字符串元素在应用层映射为 {"type":"unknown","severity":"medium","detail":<str>}
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS issues_structured BOOLEAN NOT NULL DEFAULT FALSE;
COMMENT ON COLUMN reviews.issues_structured IS
  '标记 issues 是否已按 v6.1.1 结构化（type/severity）；false=旧字符串格式，读取端归一化';
```

> 设计选择：保留 `issues` 列（应用层写入结构化对象），新增布尔标记便于灰度与回放。**分类路由读取 `issues[].type` 决定 A→repair_local / B→fact_reconcile / C→replan+rewrite**（见 architecture_v6.1 §6）。

---

## 3. Phase B：新增表 DDL

### 3.1 `book_config`（书级配置：作者意图 + 不可破坏规则 + 题材）

```sql
CREATE TABLE IF NOT EXISTS book_config (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,  -- 对应 contents(type='novel')
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    genre         VARCHAR(60) NOT NULL DEFAULT '都市重生',
    domain_type   VARCHAR(40) NOT NULL DEFAULT 'urban_business'
                  CHECK (domain_type IN ('urban_business','xuanhuan_power','sci_fi_tech','general')),
    theme         TEXT,
    author_intent JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {theme, core_emotion, reader_expectation, avoid[]}
    immutable_rules JSONB NOT NULL DEFAULT '[]'::jsonb, -- [{rule, priority:'hard'|'soft'}]
    target_words  INTEGER NOT NULL DEFAULT 1000000,
    status        VARCHAR(20) NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','confirmed','serializing','locked')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT book_config_novel_uq UNIQUE (novel_id)
);
COMMENT ON TABLE book_config IS '书级配置：每本书一个规则（非全局）。author_intent/immutable_rules 注入每次生成；status=confirmed 前需人工 Checkpoint1';
```

### 3.2 `context_package`（每章 Context 装配记录，成本诊断 + reduce_context 依赖）

```sql
CREATE TABLE IF NOT EXISTS context_package (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,  -- 章节
    chapter_seq   INTEGER NOT NULL,
    included      JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ["character_main","world_state","recent_summary_10","arc_summary_current","chapter_contract"]
    token_budget  INTEGER NOT NULL,
    actual_tokens INTEGER,
    layers        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {fixed,long,mid,short,current,style} 各层 token 明细
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT context_package_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE context_package IS 'Context Assembly Engine 产出记账：记录 AI 每章实际看到什么 + token 预算，用于成本诊断与失败重放（task_retry_policy.reduce_context 读它缩减）';
```

### 3.3 `chapter_summaries`（短摘要，≤500 字） + 3.4 `arc_summary`（卷摘要）

```sql
CREATE TABLE IF NOT EXISTS chapter_summaries (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,  -- 章节
    chapter_seq   INTEGER NOT NULL,
    summary       TEXT NOT NULL,                       -- <=500 字结构化摘要
    key_chars     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 本章出现的关键人物名
    key_decisions TEXT,                                -- 关键决策/转折一句话
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_summaries_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE chapter_summaries IS '每章轻量结构化摘要；Context Builder 短期层加载"最近10章"而非原文';

CREATE TABLE IF NOT EXISTS arc_summary (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    volume_seq    INTEGER NOT NULL,                    -- 第几卷
    volume_title  TEXT,
    summary       TEXT NOT NULL,                       -- 一卷聚合：主线推进/核心转折/人物变化
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT arc_summary_vol_uq UNIQUE (novel_id, volume_seq)
);
COMMENT ON TABLE arc_summary IS '卷级摘要；第300章时 Context Builder 加载"当前卷摘要 + 全书阶段摘要"，不逐章回溯';
```

### 3.5 `world_state`（世界动态状态快照）

```sql
CREATE TABLE IF NOT EXISTS world_state (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq   INTEGER NOT NULL,
    snapshot      JSONB NOT NULL,                      -- {time, company:{employees,cash,products,valuation}, market:{competitors,industry_trend}, society_impact}
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE world_state IS '世界变成什么样（非仅事件）：定稿回写，注入下一章生成约束；被 domain_logic 校验成长速度';
```

### 3.6 `plot_threads`（剧情线进度）

```sql
CREATE TABLE IF NOT EXISTS plot_threads (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    name          VARCHAR(200) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','paused','resolved','abandoned')),
    progress      TEXT,                                 -- 当前进度一句话
    last_chapter_seq INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE plot_threads IS '剧情线（区别于伏笔/人物弧）：详纲生成前读活跃线决定推进哪条，避免支线烂尾';
```

### 3.7 `chapter_emotion_state`（读者情绪曲线，warning）

```sql
CREATE TABLE IF NOT EXISTS chapter_emotion_state (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq   INTEGER NOT NULL,
    state         VARCHAR(20) NOT NULL
                  CHECK (state IN ('压抑','冲突','爆发','爽','缓冲','期待')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_emotion_state_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE chapter_emotion_state IS '每章情绪标签序列；仅生成建议（emotion_balance_warning），不进门禁、不硬拦';
```

### 3.8 `chapter_audit_report`（每 100 章自动审计报告，100% 规则生成、零 LLM）

```sql
CREATE TABLE IF NOT EXISTS chapter_audit_report (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    at_chapter    INTEGER NOT NULL,                     -- 报告触发章号（如 100/200）
    character_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    wealth_changes    JSONB NOT NULL DEFAULT '[]'::jsonb,
    capability_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    foreshadowing_status JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {open, overdue, resolved}
    style_drift   JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_by  VARCHAR(20) NOT NULL DEFAULT 'rule'   -- 永远 'rule'，零 LLM
                  CHECK (generated_by IN ('rule')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_audit_report_at_uq UNIQUE (novel_id, at_chapter)
);
COMMENT ON TABLE chapter_audit_report IS '百章审计：纯从 Story Bible 状态规则聚合，零 LLM 调用；供人工 Checkpoint3 读报告不读正文';
```

### 3.9 `foreshadowings` 增强（P1，v6.1 已有，本稿列 DDL 备实施）

```sql
ALTER TABLE foreshadowings
  ADD COLUMN IF NOT EXISTS expected_payoff_window INTEGER,   -- 期望回收窗口（章数）
  ADD COLUMN IF NOT EXISTS reader_awareness VARCHAR(20) DEFAULT 'hidden'
    CHECK (reader_awareness IN ('hidden','suspected','known')),
  ADD COLUMN IF NOT EXISTS importance INTEGER NOT NULL DEFAULT 5
    CHECK (importance BETWEEN 1 AND 10);
COMMENT ON COLUMN foreshadowings.importance IS '>=8 的伏笔线索进入 repair_local 的 protected_elements（禁止被局部修改替换）';
```

### 3.10 `knowledge_items`(kind='style_card') 加置信度字段（防污染）

> style_card 已存于 `knowledge_items`，加置信度用独立小表更干净：

```sql
CREATE TABLE IF NOT EXISTS style_change_confidence (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id      UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    style_kind    VARCHAR(20) NOT NULL DEFAULT 'author_style'
                  CHECK (style_kind IN ('author_style','genre_style')),
    pending_signal JSONB NOT NULL DEFAULT '{}'::jsonb,  -- 待确认的风格偏移信号
    approved_count INTEGER NOT NULL DEFAULT 0,          -- 累计人工认可次数
    threshold     INTEGER NOT NULL DEFAULT 3,           -- 达到才允许写入 author_style
    last_applied_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT style_change_confidence_uq UNIQUE (novel_id, style_kind)
);
COMMENT ON TABLE style_change_confidence IS 'author_style 需累计>=3次人工认可才改写，防 AI 自改风格；genre_style 同机制但阈值可更低';
```

---

## 4. Alembic 迁移文件模板（Phase B 示例）

```python
# backend/alembic/versions/<rev>_v611_schema.py
"""v6.1.1 schema: book_config / context_package / summaries / world_state / plot_threads / emotion / audit / style_confidence

Revision ID: v611_schema
Revises: <上一 revision>
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

def upgrade():
    op.create_table(
        'book_config',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v7()')),
        sa.Column('novel_id', UUID(as_uuid=True), sa.ForeignKey('contents.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('project_id', UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('genre', sa.String(60), nullable=False, server_default='都市重生'),
        sa.Column('domain_type', sa.String(40), nullable=False, server_default='urban_business'),
        sa.Column('theme', sa.Text()),
        sa.Column('author_intent', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('immutable_rules', JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('target_words', sa.Integer(), nullable=False, server_default='1000000'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.TIMESTAMPTZ(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMPTZ(), server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # ... 其余表同构 CREATE TABLE（与 §3 DDL 一一对应）
    op.add_column('entity_states', sa.Column('importance_level', sa.Integer(), nullable=False,
               server_default='5', sa.CheckConstraint('importance_level BETWEEN 1 AND 10')))

def downgrade():
    op.drop_table('chapter_audit_report')
    # ... 逆序 DROP
    op.drop_column('entity_states', 'importance_level')
```

> 注：现有项目用 raw SQL 迁移风格（`op.execute("""CREATE TABLE ..."""`)），上例用 SQLAlchemy 声明式仅为可读性；**实现时统一沿用项目现有 raw-SQL 风格**（`CREATE TABLE IF NOT EXISTS` + `ALTER ... ADD COLUMN IF NOT EXISTS`），与 `db.py` / 其他 migration 一致。

---

## 5. 索引与 FK 约定

- 所有新表带 `project_id` + `is_deleted`，复用现有软删约定。
- 高频查询列加索引：`context_package(content_id)`、`chapter_summaries(content_id, chapter_seq)`、`chapter_emotion_state(content_id)`、`world_state(novel_id, chapter_seq)`、`plot_threads(novel_id, status)`、`chapter_audit_report(novel_id, at_chapter)`。
- `book_config.novel_id` 唯一（一书一配置）；`context_package`/`chapter_summaries`/`chapter_emotion_state` 均 `content_id` 唯一（每章一条）。
- 不引入外键到 `versions`/`ai_calls`（避免循环依赖，沿用 09 文档约定）。

---

## 6. 与开发顺序（architecture_v6.1 §13）的衔接

1. **本稿 = §13 第一步（数据库 Schema）** 的交付物：Phase A（最小改动，MVP 必需）+ Phase B（完整管线新表）。
2. **第二步 Context Builder** 依赖 `context_package`（记账）+ `entity_states.importance_level`（选择性加载）+ `chapter_summaries`/`arc_summary`（短期层）。
3. **第三步 单章闭环 MVP** 仅强依赖 Phase A（`reviews.issues` 结构化 + 现有表），Phase B 新表可在 MVP 跑通后补——这也是用户"单章跑不通后面都是纸上设计"的体现：**MVP 不必等全部新表建完**。
4. 迁移落地后需补：`init_db()` 无需改（种子不变）；新增表的读写封装建议放在 `app/db.py` 或新建 `app/repositories/` 薄封装（保持 `DB.execute` 风格，不引入 ORM）。

---

## 7. v6.1.2 追加：5 个字段级补丁的落地表（封版，不再扩展）

> 架构已封版 v6.1.2，以下 5 项均为**字段/小表**，并入 Phase A/Phase B，不新增模块。

| 架构项 | 落地表 / 列 | 形态 | 阶段 |
|---|---|---|---|
| `book_status`（多书状态机） | 新建 `book_status(novel_id, status, changed_at, reason)` | 小表，状态枚举 `draft→worldbuilding→outline_confirmed→serializing→paused→completed→archived` | Phase B |
| `chapter_snapshot`（锁定防历史漂移） | 新建 `chapter_snapshot(content_id, content_hash, story_state_hash, entity_state_hash, outline_version)` | 锁定动作写，唯一 `content_id` | Phase B |
| `fact_confidence`（回写防误污染） | `entity_states` / `world_state` 回写记录加 `confidence` 列（<0.8 仅候选不进硬约束）；或在回写队列加 `candidate_facts(content_id, fact, confidence, promoted)` | ALTER 加列 / 候选事实小表 | Phase A 配套 |
| `repair_version`（失败回滚） | 新建 `repair_versions(repair_id, content_id, before_text, after_text, second_review_score, rolled_back, reason)` | 每次 repair_local 写对照 + 二次 review 结论 | Phase B |
| `generation_cost_log`（成本账） | 新建 `generation_cost_log(content_id, task, prompt_tokens, completion_tokens, cost_usd, created_at)` | 每任务一行，按 `content_id` 聚合 | Phase B |

**设计要点**
- `book_status` 与章节状态枚举（§9）独立，写 `book_status` 表带变更原因，便于多本管理。
- `chapter_snapshot` 在 `locked` 时生成；后续改历史章节比对 `story_state_hash`/`entity_state_hash` 失效则触发"跨章回滚影响分析"（P2 条件项，本期仅存快照+告警）。
- `fact_confidence`：回写 Story Bible 的事实必须带置信度，<0.8 不进硬约束只作候选，避免"张三似乎猜到秘密"被误判为"张三知道秘密"污染全库。
- `repair_versions` 是 repair 污染防护的落地——`after_score < before_score` 或新引入 high 问题自动恢复 `before_text`，全程可解释。
- `generation_cost_log` 为后续 DeepSeek 成本优化与预算监控提供数据，零 LLM 成本记录。
- 全部 5 项与 v6.1.1 的 4 项 + 工程项解耦，可拆独立迁移 PR；**不再有 v6.2**。
