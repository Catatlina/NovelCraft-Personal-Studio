# 数据库 Schema 落地规格 v6.1.2（现状核对版）

> 状态：**迁移依据（冻结 v6.1.2）**。取代 `docs/database_schema_design_v1.md` 中的"假设性"部分——那份设计稿写于未核对真实 DB 之前，误判了多张表"缺失"。本文件基于真实数据库核对结果，是 Alembic 迁移的唯一权威依据。
> 日期：2026-07-31
> 上游：架构文档 `docs/architecture_v6.1.md`（v6.1.2 封版）、用户 v6.1.2 审计意见、用户 Phase 1 step1 表清单。
> 修订 v2（2026-07-31）：采纳用户 6 项修正（删 `book_config.status` / `context_package` 加 `context_hash` / `repair_versions` 加 `base_version_id` / `generation_cost_log` 加任务追踪 / `chapter_summaries` 加来源 / 明确双 `confidence` 边界）+ 三阶段拆分 A/B/C。**仍只出文档，未落迁移代码。**
> 修订 v3（2026-07-31）：用户判定**数据库层冻结、进入开发**。补 4 个工程字段（`reviews.review_hash` / `world_state.state_version` / `plot_threads.importance` / `chapter_snapshot` 生成溯源三列）+ 将 `style_cards` 与 `repair_versions` 调入 **Phase A**，并重排 A/B/C + 迁移 revision 链（a→b→c）。`immutable_rules` 结构化列为后续优化、本期沿用现有 `[{rule,priority}]` 形状。
> 修订 v4（2026-07-31）：用户发开发绿灯，批准 4 项微调并明确"代码不要一次实现 style_cards 全部"。变更：`repair_versions` 加 `repair_status` 状态机（pending→reviewing→approved→applied→rollback/failed，支撑 Celery 异步）；`generation_cost_log` 加 `task_type`（细分一次 generate 的子任务成本）；`reviews.score_7dim` 应用层强制 `{维度:{score,reason}}` 结构；`style_cards` 明确 Phase A 代码仅消费 `author_card`/`genre_card`，其余列只存不实现。**本版起开始落迁移代码（Phase A）。**

---

## 0. 关键结论（先看事实）

真实数据库**已经存在** v6.1.2 大部分所谓"新表"。逐张核对结果：

| 用户 step1 列出的表 | 真实对应 | 现状 | 本规格动作 |
|---|---|---|---|
| `book_config` | 无 | 缺失 | **新建**（无 status 列，书状态移交 book_status 单一事实源） |
| `entities` | `entity_states`（已有 `entity_type`） | 已有，缺 `importance_level` + `confidence` | **ALTER 加 2 列** |
| `timeline` | `timeline_events` | 已存在够用 | **复用** |
| `world_state` | 无 | 缺失 | **新建** |
| `plot_threads` | 无 | 缺失 | **新建** |
| `foreshadowing` | `foreshadowings` | 已存在（planted/pending/paid_off） | **复用**（+ P1 增强 3 列可选） |
| `chapter` | `contents`（type='chapter'） | 已存在 | **复用** |
| `chapter_summary` | 无 | 缺失 | **新建** `chapter_summaries` |
| `context_package` | 无 | 缺失 | **新建** |
| `style_card` | `style_cards` | 已存在（`card` JSONB） | **ALTER 拆分 + 加置信度** |
| `repair_versions` | 无（`versions` 是通用内容版本，非 repair 专用） | 缺失 | **新建** `repair_versions` |
| `chapter_snapshot` | 无 | 缺失 | **新建** |
| `generation_cost_log` | 无 | 缺失 | **新建** |

**v6.1.2 §7 追加字段 + 用户 4 个实现问题**触发的额外动作：

| 架构/问题项 | 真实对应 | 动作 |
|---|---|---|
| `book_status` 多书状态机 | 无 | **新建** `book_status` |
| `arc_summary` 卷摘要 | 无（现有 `arcs` 是人物弧线） | **新建** |
| `chapter_emotion_state` 情绪曲线 | 无 | **新建** |
| `chapter_audit_report` 百章审计 | 无 | **新建** |
| 问题3：`review_7dim` 固定输出格式 | `reviews`（score/维度/issues 非结构化） | **ALTER** `reviews`（+score_7dim / +issues_structured / +review_type / +model） |
| 问题2：Story Bible 事实硬/软分级 + 置信度 | `knowledge_items`（style_card/事实存此） | **ALTER** `knowledge_items`（+confidence / +source_chapter / +approved / +created_by / +fact_type） |

**汇总**：**12 张新建表 + 5 张表 ALTER（加列）+ 5 张直接复用**，按用户三阶段 A/B/C 分批迁移（见 §7）。

---

## 1. 复用现有表（不改结构，仅说明语义归属）

| 表 | v6.1.2 角色 | 备注 |
|---|---|---|
| `contents` | 书/章/卷统一内容树（type 区分 novel/chapter/volume） | 章节正文即 `contents(type='chapter')` |
| `timeline_events` | 时间线 | 已含 `real_world_anchor`/`anachronism_check`，够用 |
| `foreshadowings` | 伏笔系统 | 基础够用；P1 增强见 §3.5 |
| `arcs` | 人物弧线（区别于剧情线 `plot_threads`） | 独立概念，不复用 |
| `versions` | 通用内容版本系统 | 非 repair 专用，不在此接管 |
| `author_style_signals` | 作者编辑信号（用户问题4 的雏形） | **问题4 明确 P2，本期不扩** |
| `model_routes` / `prompts` / `ai_calls` | 路由 / Prompt Registry / 调用溯源 | 已存在，Provider 抽象是代码层改动 |
| `projects` | 项目容器（用户/多书归属） | `book_config` / `book_status` 挂在 `contents(novel)` 与 `projects` 上，不污染 `projects` 自身 |

---

## 2. ALTER 现有表（补 v6.1.2 缺字段）

> 全部用 `ADD COLUMN IF NOT EXISTS`，幂等、可回滚。

### 2.1 `entity_states`（实体分级 + 回写置信度）
```sql
ALTER TABLE entity_states
  ADD COLUMN IF NOT EXISTS importance_level INTEGER NOT NULL DEFAULT 5
    CHECK (importance_level BETWEEN 1 AND 10);
ALTER TABLE entity_states
  ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
    CHECK (confidence BETWEEN 0 AND 1);
COMMENT ON COLUMN entity_states.importance_level IS
  '实体重要度 1-10：Context Builder 仅加载 >= 阈值（默认 >=6）的实体，防止第500章加载"村口老王"浪费 token';
COMMENT ON COLUMN entity_states.confidence IS
  '实体"状态"可信度（仅限实体自身：年龄/能力/关系/位置等），<0.8 视为候选不进硬约束。与 knowledge_items.confidence 分工：本列管"实体状态"，knowledge_items.confidence 管"世界知识/事件/规则"，二者职责不重叠，读取端不互相覆盖';
```

### 2.2 `style_cards`（作者/题材风格拆分 + 风格漂移置信度）
> 比原设计稿更优：把 `style_change_confidence` 单表**折叠进 `style_cards`**，避免多一张表、且与卡片同生命周期。
> 修订 v3：调入 **Phase A**（去 AI 味是 MVP 核心，首章起即需作者风格约束）。
> **Phase A 代码实现范围（v4 明确）**：代码**仅读写 `author_card` / `genre_card` 两列**——生成首章即注入作者/题材风格约束（去 AI 味）。`style_change_confidence` / `relearn_at_chapter` / `pending_signals` / `approved_count` / `apply_threshold` **只建列、Phase A 不实现其逻辑**（每 10 章风格重学、漂移收敛、累计认可改写 author_card 等留待后续阶段，避免一次实现全部复杂度）。
```sql
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS author_card JSONB NOT NULL DEFAULT '{}'::jsonb;   -- 作者个人笔法
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS genre_card JSONB NOT NULL DEFAULT '{}'::jsonb;    -- 题材惯例
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS style_change_confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
    CHECK (style_change_confidence BETWEEN 0 AND 1);
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS relearn_at_chapter INTEGER;                       -- 下次重学章号（每10章）
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS pending_signals JSONB NOT NULL DEFAULT '[]'::jsonb;-- 待确认的风格偏移信号
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS approved_count INTEGER NOT NULL DEFAULT 0;        -- 累计人工认可次数
ALTER TABLE style_cards
  ADD COLUMN IF NOT EXISTS apply_threshold INTEGER NOT NULL DEFAULT 3;       -- 达到才允许改写 author_card
COMMENT ON TABLE style_cards IS '作者/题材风格卡；author_card 需累计>=apply_threshold 次人工认可才改写，防 AI 自改风格';
```

### 2.3 `reviews`（七维结构化 + 固定输出格式）
> 支撑用户问题3（固定 JSON 结构）与分类路由 A/B/C。
```sql
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS score_7dim JSONB;                 -- {style,continuity,plot,logic,character,emotion,pacing}
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS issues_structured BOOLEAN NOT NULL DEFAULT FALSE;  -- 旧 issues 为字符串数组，新为对象数组
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS review_type VARCHAR(40);          -- bootstrap / editor / final_humanize ...
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS model VARCHAR(100);               -- 实际使用的模型（成本溯源）
ALTER TABLE reviews
  ADD COLUMN IF NOT EXISTS review_hash VARCHAR(64);          -- 本次审查结果指纹（score_7dim+issues 聚合 hash），换模型重审可比对是否同一结论
COMMENT ON COLUMN reviews.score_7dim IS '七维评分对象：应用层强制 {维度:{score,reason}} 结构，禁用扁平 {style:85}；七个键固定 style/continuity/plot/logic/character/emotion/pacing，reason 必填供未来 AI 审计解释';
COMMENT ON COLUMN reviews.issues_structured IS 'issues 已按 v6.1.2 结构化（type/severity/location/repair_scope/confidence）；false=旧字符串格式，读取端归一化';
COMMENT ON COLUMN reviews.review_hash IS '审查资产指纹：模型/规则升级后重审同一章，比对 review_hash 可知审查结论是否变化';
```
**`issues` 固定结构（应用层写入，DB 仍 JSONB）**：
```json
{
  "type": "continuity|style|plot|logic|character|emotion|pacing",
  "severity": "high|medium|low",
  "location": "chapter_10_scene_3",
  "description": "李强在第50章与第300章关系冲突",
  "repair_scope": "local|section|chapter",
  "confidence": 0.91
}
```
旧数据（字符串数组）在读取端映射为 `{"type":"unknown","severity":"medium","description":<原串>}`。

**`score_7dim` 应用层强制 schema（v4）**：写入端必须产 `{维度:{score:int,reason:string}}`，**禁止**扁平 `{style:85}`。固定七键：
```json
{
  "style":      {"score": 85, "reason": "对话口语化不足，仍偏书面"},
  "continuity": {"score": 90, "reason": "与前章时间线一致"},
  "plot":       {"score": 88, "reason": "推进主线"},
  "logic":      {"score": 92, "reason": "商业决策合理"},
  "character":  {"score": 87, "reason": "性格稳定"},
  "emotion":    {"score": 80, "reason": "高潮情绪到位"},
  "pacing":     {"score": 84, "reason": "中段略拖"}
}
```
reason 必填，未来 AI 审计需逐维解释；读取端若遇扁平旧格式，归一化为 `{维度:{score:<值>,reason:""}}`。

### 2.4 `knowledge_items`（Story Bible 事实硬/软分级 + 置信度）
> 用户问题2 落地：事实带 `fact_type`（hard/soft）、`confidence`、`approved`、`source_chapter`、`created_by`。
```sql
ALTER TABLE knowledge_items
  ADD COLUMN IF NOT EXISTS confidence NUMERIC(3,2) NOT NULL DEFAULT 1.0
    CHECK (confidence BETWEEN 0 AND 1);
ALTER TABLE knowledge_items
  ADD COLUMN IF NOT EXISTS source_chapter INTEGER;          -- 该事实出自哪一章
ALTER TABLE knowledge_items
  ADD COLUMN IF NOT EXISTS approved BOOLEAN NOT NULL DEFAULT FALSE;  -- 软事实需人工确认才进硬约束
ALTER TABLE knowledge_items
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id);
ALTER TABLE knowledge_items
  ADD COLUMN IF NOT EXISTS fact_type VARCHAR(20) NOT NULL DEFAULT 'hard'
    CHECK (fact_type IN ('hard','soft'));
COMMENT ON COLUMN knowledge_items.fact_type IS
  'hard=可自动进入 Story Bible 硬约束（生日/死亡/公司成立）；soft=心理/感情类，需 approved=true 才进硬约束，避免污染';
COMMENT ON COLUMN knowledge_items.confidence IS
  '世界知识/事件/规则的可信度（公司成立时间/历史事件/题材规则等），<0.8 仅候选。与 entity_states.confidence 分工：本列管"世界知识"，entity_states.confidence 管"实体状态"，不重叠';
```

### 2.5 `foreshadowings`（P1 增强，支撑 protected_elements）
```sql
ALTER TABLE foreshadowings
  ADD COLUMN IF NOT EXISTS expected_payoff_window INTEGER;  -- 期望回收窗口（章数）
ALTER TABLE foreshadowings
  ADD COLUMN IF NOT EXISTS reader_awareness VARCHAR(20) NOT NULL DEFAULT 'hidden'
    CHECK (reader_awareness IN ('hidden','suspected','known'));
ALTER TABLE foreshadowings
  ADD COLUMN IF NOT EXISTS importance INTEGER NOT NULL DEFAULT 5
    CHECK (importance BETWEEN 1 AND 10);
COMMENT ON COLUMN foreshadowings.importance IS '>=8 的伏笔进入 repair_local 的 protected_elements，禁止被局部修改替换';
```

---

## 3. 新建表 DDL

> 约定：`id UUID PRIMARY KEY DEFAULT gen_random_uuid()`（**仅 `gen_random_uuid()` 可用**，无 uuid-ossp）；`JSONB`；`TIMESTAMPTZ`；带 `project_id` + `is_deleted` 软删；FK 用 `ON DELETE CASCADE`；`CREATE TABLE IF NOT EXISTS` 幂等。

### 3.1 `book_config`（书级配置：作者意图 + 不可破坏规则 + 题材）
> 修订 v2：删除 `status` 列（原 draft/confirmed/serializing/locked）。书状态单一事实源移交 `book_status`（见 §3.12），避免两处状态冲突——`book_config` 只回答"书是什么"，`book_status` 回答"书现在处于什么阶段"。
```sql
CREATE TABLE IF NOT EXISTS book_config (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    novel_id       UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,   -- contents(type='novel')
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    genre          VARCHAR(60) NOT NULL DEFAULT '都市重生',
    domain_type    VARCHAR(40) NOT NULL DEFAULT 'urban_business'
                   CHECK (domain_type IN ('urban_business','xuanhuan_power','sci_fi_tech','general')),
    theme          TEXT,
    author_intent  JSONB NOT NULL DEFAULT '{}'::jsonb,    -- {theme, core_emotion, reader_expectation, avoid[]}
    immutable_rules JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{rule, priority:'hard'|'soft'}]
    target_words   INTEGER NOT NULL DEFAULT 1000000,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted     BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT book_config_novel_uq UNIQUE (novel_id)
);
COMMENT ON TABLE book_config IS '书级配置：每本书一个规则（非全局）。author_intent/immutable_rules 注入每次生成；不含状态列——状态由 book_status 单一事实源管理';
```

### 3.2 `world_state`（世界动态状态快照）
```sql
CREATE TABLE IF NOT EXISTS world_state (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq INTEGER NOT NULL,
    state_version INTEGER NOT NULL DEFAULT 1,   -- 世界状态演化版本：第100章公司100人 / 第200章5000人，按章序列出历史演化，不互相覆盖
    snapshot    JSONB NOT NULL,   -- {time, company:{employees,cash,products,valuation}, market:{competitors,industry_trend}, society_impact}
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE world_state IS '世界变成什么样（非仅事件）：定稿回写，注入下一章生成约束；被 domain_logic 校验成长速度；state_version 记录历史演化';
```

### 3.3 `plot_threads`（剧情线进度，区别于伏笔/人物弧）
```sql
CREATE TABLE IF NOT EXISTS plot_threads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','paused','resolved','abandoned')),
    importance      INTEGER NOT NULL DEFAULT 5
                    CHECK (importance BETWEEN 1 AND 10),   -- Context Builder 仅加载 >= 阈值（默认 >=6）的剧情线，防 500 章后全部加载浪费 token
    progress        TEXT,
    last_chapter_seq INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE plot_threads IS '剧情线（区别于伏笔/人物弧）：详纲生成前读活跃线决定推进哪条，避免支线烂尾；importance 控制 Context Builder 加载优先级';
```

### 3.4 `chapter_summaries`（短摘要）+ 3.5 `arc_summary`（卷摘要）
```sql
CREATE TABLE IF NOT EXISTS chapter_summaries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id  UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq INTEGER NOT NULL,
    summary_type VARCHAR(20) NOT NULL DEFAULT 'chapter'
                CHECK (summary_type IN ('chapter','compressed','manual')),
    generated_by VARCHAR(40) NOT NULL DEFAULT 'deepseek',   -- 摘要来源：deepseek / manual / compress
    summary     TEXT NOT NULL,
    key_chars   JSONB NOT NULL DEFAULT '[]'::jsonb,
    key_decisions TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_summaries_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE chapter_summaries IS '每章轻量结构化摘要；summary_type 区分 章节/压缩/人工，generated_by 记录来源（未来无法定位摘要出处时复盘用）；Context Builder 短期层加载"最近10章"而非原文';

CREATE TABLE IF NOT EXISTS arc_summary (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id     UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    volume_seq   INTEGER NOT NULL,
    volume_title TEXT,
    summary      TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT arc_summary_vol_uq UNIQUE (novel_id, volume_seq)
);
COMMENT ON TABLE arc_summary IS '卷级摘要；第300章时 Context Builder 加载"当前卷摘要 + 全书阶段摘要"，不逐章回溯';
```

### 3.6 `context_package`（每章 Context 装配记录）
```sql
CREATE TABLE IF NOT EXISTS context_package (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq   INTEGER NOT NULL,
    context_hash  VARCHAR(64),                         -- 本次装配的上下文指纹（含 included+各层 token+prompt 版本），同章重生成可比对 A/B context 差异
    included      JSONB NOT NULL DEFAULT '[]'::jsonb,   -- ["character_main","world_state","recent_summary_10","arc_summary_current","chapter_contract"]
    token_budget  INTEGER NOT NULL,
    actual_tokens INTEGER,
    layers        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {fixed,long,mid,short,current,style} 各层 token 明细
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted    BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT context_package_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE context_package IS 'Context Assembly Engine 产出记账：记录 AI 每章实际看到什么 + token 预算 + 上下文指纹。是用户问题1（Context 优先级/预算超限裁剪）与"同章重生成 A/B 比对"的落表支撑';
```

### 3.7 `chapter_emotion_state`（读者情绪曲线，warning 级）
```sql
CREATE TABLE IF NOT EXISTS chapter_emotion_state (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id  UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq INTEGER NOT NULL,
    state       VARCHAR(20) NOT NULL
                CHECK (state IN ('压抑','冲突','爆发','爽','缓冲','期待')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_emotion_state_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE chapter_emotion_state IS '每章情绪标签；仅生成建议（emotion_balance_warning），不进门禁、不硬拦';
```

### 3.8 `chapter_audit_report`（每 100 章纯规则审计，零 LLM）
```sql
CREATE TABLE IF NOT EXISTS chapter_audit_report (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id          UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    at_chapter        INTEGER NOT NULL,
    character_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    wealth_changes    JSONB NOT NULL DEFAULT '[]'::jsonb,
    capability_changes JSONB NOT NULL DEFAULT '[]'::jsonb,
    foreshadowing_status JSONB NOT NULL DEFAULT '{}'::jsonb,
    style_drift       JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_by      VARCHAR(20) NOT NULL DEFAULT 'rule' CHECK (generated_by IN ('rule')),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted        BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chapter_audit_report_at_uq UNIQUE (novel_id, at_chapter)
);
COMMENT ON TABLE chapter_audit_report IS '百章审计：纯从 Story Bible 状态规则聚合，零 LLM；供人工 Checkpoint3 读报告不读正文';
```

### 3.9 `chapter_snapshot`（锁定防历史漂移，小说版 Git commit）
```sql
CREATE TABLE IF NOT EXISTS chapter_snapshot (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id        UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq       INTEGER NOT NULL,
    content_hash      VARCHAR(64),   -- 章节正文 hash
    story_state_hash  VARCHAR(64),   -- Story Bible 状态 hash（world_state/plot_threads 聚合）
    entity_state_hash VARCHAR(64),   -- 实体状态 hash
    outline_version   INTEGER,       -- 当时大纲版本
    prompt_version    VARCHAR(64),   -- 生成所用 prompt 版本（如 gen_chapter1=3.2.0），模型/规则升级后复盘用
    model             VARCHAR(100),   -- 生成模型（如 deepseek-chat），DeepSeek 升级后可比对同 context 不同模型结果
    generation_params JSONB,         -- {temperature, top_p, ...} 生成参数，复现实验必需
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chapter_snapshot_content_uq UNIQUE (content_id)
);
COMMENT ON TABLE chapter_snapshot IS '锁定动作写；除状态 hash 外额外存 prompt_version/model/generation_params，使百万字后任一章可完整复现生成条件；改历史章节比对 hash 失效触发"跨章回滚影响分析"（P2 仅存快照+告警）';
```

### 3.10 `repair_versions`（repair 对照 + 二次 review + 失败回滚）
> 修订 v3：调入 **Phase A**（核心流程 生成→review→repair 的 MVP 必需，否则支撑不了 DeepSeek-only 最优方案）。
```sql
CREATE TABLE IF NOT EXISTS repair_versions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id         UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    base_version_id    UUID,                            -- 关联 versions(id) 的修复基准版本；按项目约定不强制 FK 以避免循环依赖，应用层维护版本链（versions.parent_version_id 已支持回溯）
    chapter_seq        INTEGER,
    repair_type        VARCHAR(20) NOT NULL DEFAULT 'local'
                       CHECK (repair_type IN ('local','section','chapter')),
    repair_scope       VARCHAR(20),                    -- continuity/style/plot
    repair_status      VARCHAR(20) NOT NULL DEFAULT 'pending'
                       CHECK (repair_status IN ('pending','reviewing','approved','applied','rollback','failed')),
    before_text        TEXT NOT NULL,
    after_text         TEXT NOT NULL,
    repair_prompt      TEXT,
    second_review_score NUMERIC(4,2),                  -- 二次 review 总分
    second_review_issues JSONB,                        -- 二次 review 结构化 issues
    rolled_back        BOOLEAN NOT NULL DEFAULT FALSE, -- after_score<before_score 或新引入 high 问题→自动恢复
    reason             TEXT,
    model              VARCHAR(100),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE repair_versions IS 'repair 污染防护落地：每次 repair_local 写 before/after 对照 + 二次 review 结论 + 基准版本链，全程可解释、可回滚；base_version_id 串起 chapter_v1→repair_v1→repair_v2→final。repair_status 状态机（pending→reviewing→approved→applied→rollback|failed）支撑 Celery 异步任务——repair 生成中/等待二审/通过/应用/回滚，不用 rolled_back 一个布尔硬判断流程进度';
```

### 3.11 `generation_cost_log`（成本账，DeepSeek-only 成本溯源）
> 用 `cost_cny` 与 `budgets` 表货币单位一致（项目计费为人民币）。
```sql
CREATE TABLE IF NOT EXISTS generation_cost_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content_id       UUID REFERENCES contents(id) ON DELETE CASCADE,
    chapter_seq      INTEGER,
    phase            VARCHAR(20) NOT NULL
                     CHECK (phase IN ('generate','review','repair','humanize','other')),
    task_type        VARCHAR(50),                      -- 细分调用类型：chapter_generate / chapter_review / repair_local / summary_generate / entity_extract ... 一次 generate 可能含 outline/plan/draft/polish 多个子任务，按 task_type 拆分成本
    model            VARCHAR(100),
    task_id          VARCHAR(64),                       -- Celery task id，串起一次生成任务的全部调用
    request_id       VARCHAR(64),                       -- 单次 LLM 请求 id（gateway 调用溯源）
    success          BOOLEAN NOT NULL DEFAULT TRUE,     -- API 失败也记一行，便于分析成本异常来源
    error_message    TEXT,                              -- success=false 时记录错误
    prompt_tokens    INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens     INTEGER NOT NULL DEFAULT 0,
    cost_cny         NUMERIC(10,4) NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE generation_cost_log IS '每任务一行；phase 粗分阶段、task_type 细分子任务（一次 generate 可能含 outline/plan/draft/polish），task_id/request_id 串起调用链，success/error_message 让 API 失败也能入账，按 phase/task_type/成功状态聚合可知钱烧在 generate/review/repair 还是失败重试上，指导 DeepSeek 成本优化';
```

### 3.12 `book_status`（多书状态机，带变更原因）
> 与章节状态枚举独立；追加式日志，当前状态 = 该 novel 最新一行。
```sql
CREATE TABLE IF NOT EXISTS book_status (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    novel_id    UUID NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL
                CHECK (status IN ('draft','worldbuilding','outline_confirmed','serializing','paused','completed','archived')),
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE book_status IS '多书状态机（个人同时写2-3本）：A书 serializing / B书 paused / C书 worldbuilding。追加日志，便于多本管理与回溯';
```

---

## 4. 索引与 FK 约定

- 所有新建表带 `project_id`（FK→`projects`）+ `is_deleted`（软删），复用现有约定。
- 高频查询列索引：
  - `context_package(content_id)`、`chapter_summaries(content_id, chapter_seq)`、`chapter_emotion_state(content_id)`
  - `world_state(novel_id, chapter_seq)`、`plot_threads(novel_id, status)`、`chapter_audit_report(novel_id, at_chapter)`
  - `chapter_snapshot(content_id)`、`repair_versions(content_id)`、`generation_cost_log(project_id, created_at)`、`book_status(novel_id, changed_at)`
- 唯一约束：`book_config(novel_id)`、`context_package(content_id)`、`chapter_summaries(content_id)`、`chapter_emotion_state(content_id)`、`chapter_snapshot(content_id)`、`arc_summary(novel_id, volume_seq)`、`chapter_audit_report(novel_id, at_chapter)`。
- 不向 `versions`/`ai_calls` 加 FK（避免循环依赖，沿用现有约定）。

---

## 5. 用户 4 个实现问题的"落表"映射

| 问题 | 是否本期 | 落表/字段 | 说明 |
|---|---|---|---|
| 问题1：Context Builder 优先级/预算超限裁剪 | 是（表） | `context_package`（token_budget/actual_tokens/layers） | 算法逻辑在代码层；本表提供记账与失败重放依据 |
| 问题2：Story Bible 事实硬/软分级 + 防污染 | 是 | `knowledge_items.fact_type/approved/confidence/source_chapter`、`entity_states.confidence` | 规则：hard 自动进硬约束；soft 或 confidence<0.8 仅候选，需 `approved=true` 才升级 |
| 问题3：`review_7dim` 固定输出格式 | 是 | `reviews.score_7dim` + `issues_structured` + 固定 `issues` JSON 结构 | 见 §2.3 结构定义，驱动分类路由 A/B/C |
| 问题4：人工编辑信号 `author_feedback_log` | **否（P2）** | 已有 `author_style_signals` 雏形 | 用户明确 P2；本期不扩，避免提前加复杂度 |

---

## 6. 迁移落地方式

- **三连 revision（A→B→C）**：`v612_phase_a`（`down_revision='b324f6c7a7f1'`，当前 alembic head）→ `v612_phase_b`（`down_revision=v612_phase_a`）→ `v612_phase_c`（`down_revision=v612_phase_b`）。每阶段独立可回滚；用户命名为 `v612_schema_baseline_a` 首版即本 `v612_phase_a`。
- **风格**：沿用项目现有 raw-SQL 迁移（`op.execute("""...""")` + `CREATE TABLE IF NOT EXISTS` / `ALTER ... ADD COLUMN IF NOT EXISTS`），与 `db.py` 一致，**不引入 ORM 模型**。
- **执行顺序**：先 ALTER（加列，安全）→ 再 CREATE 新表。全部幂等。Phase A 先跑（最小闭环），B/C 依次。
- **downgrade**：对称 `DROP TABLE IF EXISTS` / `ALTER ... DROP COLUMN IF EXISTS`，按 a→b→c 反向。
- **`init_db()` 不改**：种子（prompts/model_routes/...）不变；新表读写后续由 `app/repositories/` 薄封装（保持 `DB.execute` 风格）。
- **应用后校验**：每阶段跑完 `alembic upgrade head` + `\dt` 确认该阶段表/列存在；抽样 `SELECT` 验证 `entity_states.importance_level` 默认 5、各新表可 INSERT/SELECT。

---

## 7. 与开发顺序衔接（架构 v6.1.2 §13 + 用户三阶段拆分 v3）

> 修订 v3：采纳用户最终三阶段（A 单章闭环 / B 上下文成本 / C 长期稳定）。关键调整：`style_cards` 与 `repair_versions` **调入 Phase A**（去 AI 味与 repair 是 MVP 核心，不是后期功能）。每阶段 = 一次 Alembic revision（见 §6 链 a→b→c），可独立回滚。

1. **本规格 = Phase 1 step1（数据库 Schema）** 的交付物：12 新表 + 5 ALTER，按 A/B/C 三阶段分批迁移。
2. **Phase A（单章闭环 MVP，最先建）**：`book_config`（无 status 列）+ `book_status` + `style_cards` 增强（author_card/genre_card 启用，其余列先建不用）+ `entity_states` 增强（importance_level/confidence）+ `knowledge_items` 增强（fact_type/confidence/approved/source_chapter）+ `reviews` 增强（score_7dim/issues_structured/review_hash/model）+ `repair_versions`（含 base_version_id）+ 复用 `contents`。
   - 这足以跑通 **生成→review_7dim（结构化 issues）→分类路由 A/B/C→repair_local→二次 review→回滚→保存 Story Bible（entity_states/knowledge_items 回写）** 的单章闭环，且首章起即有作者风格约束（去 AI 味）。
   - `foreshadowings` 3 列增强（§2.5，protected_elements 支撑）为低风险 ALTER，建议随 Phase A 一并执行。
3. **Phase B（上下文 + 成本）**：`context_package`（含 context_hash）+ `chapter_summaries`（summary_type/generated_by）+ `arc_summary` + `generation_cost_log`（task/request/success 追踪）。MVP 跑通后补，支撑上下文记账 / 摘要检索 / 成本溯源。
4. **Phase C（百万字保障）**：`world_state`（state_version）+ `plot_threads`（importance）+ `chapter_snapshot`（含生成溯源三列）+ `chapter_audit_report` + `chapter_emotion_state`。最后补，承载长期稳定性与污染防护。
5. 明确**不在本期**：multi-Agent、RAG/embedding/vector、Qwen 路由、自动发布、多用户权限、v6.2。架构已封版，**数据库层已冻结**。

---

## 8. 命名说明

新表名沿用 v6.1.2 架构文档命名（多为单数，如 `book_config`/`world_state`/`context_package`），与既有复数表（`entity_states`/`knowledge_items`）略有出入，但**刻意与文档保持一致**以便代码映射。如需统一复数化，作为后续纯重命名迁移处理，不阻塞本期。

---

## 9. 修订记录（v6.1.2_migration_spec 第2版，2026-07-31）

采纳用户审计意见（综合评分 9.3/10），仅改文档、未落迁移代码。变更：

**必改（4 项，结构变更）**
1. `book_config` 删除 `status` 列；书状态单一事实源移交 `book_status`（§3.1）。修正"两处管状态"冲突——`book_config` 只答"书是什么"，`book_status` 答"书现在处于什么阶段"。
2. `context_package` 新增 `context_hash VARCHAR(64)`（§3.6），支持同章重生成 A/B 上下文比对。
3. `repair_versions` 新增 `base_version_id UUID`（逻辑关联 `versions(id)`，不强制 FK，§3.10），串起版本链 chapter_v1→repair_v1→…→final，回滚更稳。
4. `generation_cost_log` 新增 `task_id` / `request_id` / `success` / `error_message`（§3.11），API 失败也入账，成本异常可溯源。

**建议改（2 项）**
5. `chapter_summaries` 新增 `summary_type`（chapter/compressed/manual）+ `generated_by`（§3.4），标注摘要来源。
6. 明确 `entity_states.confidence`（实体状态）与 `knowledge_items.confidence`（世界知识）职责边界，仅增强注释不改动表（§2.1 / §2.4）。

**开发分期修订**
- §7 由 A/B 两阶段改为用户三阶段 A/B/C：A=单章闭环最小依赖（book_config / entity_states 增强 / knowledge_items 增强 / reviews 增强 / contents + book_status）；B=管线新表（context_package / summaries / style_cards 增强 / cost_log）；C=百万字保障（snapshot / audit / world_state / plot_threads / emotion / repair）。

本版冻结，不再设计 v6.1.3 / v6.2。下一步：用户说"开始/落地"后按 §7 分批写 Alembic 迁移。

---

## 10. 修订记录（v6.1.2_migration_spec 第3版，2026-07-31）— 数据库层冻结

用户判定**数据库设计 9.6/10、可冻结并进入开发**。本版仍只出文档、未落迁移代码。变更：

**新增 4 个工程字段（v3）**
1. `reviews.review_hash VARCHAR(64)`（§2.3）：审查结果指纹，模型/规则升级后重审可比对是否同结论。
2. `world_state.state_version INTEGER DEFAULT 1`（§3.2）：世界状态历史演化版本，不互相覆盖。
3. `plot_threads.importance INTEGER DEFAULT 5`（CHECK 1-10，§3.3）：Context Builder 按重要度加载，防 500 章后全量加载浪费 token。
4. `chapter_snapshot` 增加 `prompt_version VARCHAR(64)` / `model VARCHAR(100)` / `generation_params JSONB`（§3.9）：锁定快照额外存生成溯源，百万字后任一章可完整复现。

**阶段重排（v3）**
- `style_cards` 与 `repair_versions` **调入 Phase A**（去 AI 味 + repair 是 MVP 核心，非后期）。§7 重写为：A=单章闭环（book_config/book_status/style_cards/entity_states/knowledge_items/reviews/repair_versions/contents + foreshadowings 可选增强）；B=上下文+成本（context_package/chapter_summaries/arc_summary/generation_cost_log）；C=百万字保障（world_state/plot_threads/chapter_snapshot/chapter_audit_report/chapter_emotion_state）。
- §6 迁移方式由"单 revision"改为 **a→b→c 三连 revision 链**（`v612_phase_a`←`b324f6c7a7f1` → `v612_phase_b` → `v612_phase_c`），每阶段独立可回滚。

**明确延后（非本期）**
- `book_config.immutable_rules` 结构化（问题3）：用户建议"未来固定"，本期沿用现有 `[{rule, priority}]` 形状（repair_local 已能读取 rule/priority），不新增字段，留作后续优化。
- 禁止清单不变：multi-Agent / RAG / embedding / vector / Qwen 路由 / 自动发布 / 多用户权限 / v6.2。

**开发绿灯（用户原话）**："下一步应该让 AI 开始写 Alembic Phase A migration + repository 层 + 单章闭环代码。" 数据库层已冻结，本文件即迁移唯一权威依据；用户 Step 1 = 写 `v612_phase_a` 迁移，Step 2 = 单章闭环，Step 3 = 拿真实小说连测 10 章（非 demo）。

---

## 11. 修订记录（v6.1.2_migration_spec 第4版，2026-07-31）— 开始落代码

用户发开发绿灯，批准 4 项微调并强调"代码不要一次实现 style_cards 全部"。本版起**开始落迁移代码（Phase A）**。变更：

1. **`repair_versions.repair_status VARCHAR(20)`**（§3.10，NEW 列）：状态机 `pending→reviewing→approved→applied→rollback|failed`，替代单一 `rolled_back` 布尔判断流程进度，支撑 Celery 异步任务中 repair 生成中/等待二审/通过/应用/回滚的可见状态。
2. **`generation_cost_log.task_type VARCHAR(50)`**（§3.11，Phase B 表）：细分调用类型（chapter_generate/chapter_review/repair_local/summary_generate/entity_extract…），一次 generate 含 outline/plan/draft/polish 多子任务时按 `task_type` 拆成本。（该表属 Phase B，本版仅补字段定义。）
3. **`reviews.score_7dim` 应用层强制 schema**（§2.3）：固定 `{维度:{score:int,reason:string}}` 七键（style/continuity/plot/logic/character/emotion/pacing），禁止扁平 `{style:85}`，reason 必填供 AI 审计解释。
4. **`style_cards` Phase A 代码范围明确**（§2.2）：Phase A 代码仅消费 `author_card`/`genre_card`；`style_change_confidence`/`relearn_at_chapter`/`pending_signals`/`approved_count`/`apply_threshold` 只建列不实现逻辑，留后续阶段。

**Phase A 迁移内容（本次落地的 `v612_phase_a`）**：`entity_states`(+importance_level+confidence) / `style_cards`(+5 列) / `knowledge_items`(+5 列) / `reviews`(+5 列) / `foreshadowings`(+3 列，protected_elements 支撑) 五个 ALTER + 新建 `book_config` / `book_status` / `repair_versions`（含 `repair_status`）。`down_revision='b324f6c7a7f1'`。

数据库层冻结声明不变；禁止清单不变（multi-Agent / RAG / embedding / vector / Qwen 路由 / 自动发布 / 多用户 / v6.2）。
