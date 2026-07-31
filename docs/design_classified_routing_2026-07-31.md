# 小说生产流水线重构：现状架构 vs 重构方案（设计文档 / ADR）

> 状态：方案评审中（未落地代码）
> 日期：2026-07-31
> 范围：DeepSeek-only（Phase 1），不接 Qwen、不建 model_routes 脚手架
> 核心命题：**百万字小说系统最大的成本不是模型能力不足，而是错误地反复整章重写**

---

## 0. 背景与动机

- 当前门禁对七维评分 <80 的章节**一律整段 regenerate**（一次完整章节生成 = 最贵步骤）；日常去 AI 味管线（DeaiPipeline）也走整段 `deai.rewrite`。
- 一次整章生成 ≈ 2000–3200 中文字 token；百万字（约 330 章）下，门禁循环把单章成本放大 ×2~4。
- 用户方向（已 grill-me 共识）：第一阶段 DeepSeek-only，不堆模型；优化工程瓶颈。新增三要素：① 问题分类 A/B/C 路由；② Writer DNA（Style Card）防漂移；③ final_humanize 抽样。

---

## 1. 当前架构（As-Is）

### 1.1 LLM 路由层（`gateway.py`）
- `complete()` **不接收 provider 覆盖参数**；按 `task_type` 查 `model_routes` 表拿 `(provider, model, params)`。
- `model_routes` 当前为空 → fallback 到 `deepseek` + `deepseek-chat`。
- `PROVIDERS = {deepseek, claude, openai, gemini}`（`providers.py:115`）；Qwen 未注册；计费费率仅含 deepseek/openai/anthropic（`gateway.py:1031`）。
- UI（`engine/router.py`）`/models` 与 `/healthz` 仅报告 deepseek。

### 1.2 章节生成 + 硬门禁（`workers/tasks.py` → `_review_and_finalize_chapter`，L2391）
- 常量：`MIN_CHAPTER_CHARS=2000`（env）、`REVIEW_SCORE_THRESHOLD=80`（env `CHAPTER_QUALITY_THRESHOLD`）、`CHAPTER_MAX_REWRITES=3`。
- 流程：
  ```
  生成章节 → review_7dim
    ├─ score>=80 且 chars>=2000 → 通过（status='reviewed'）
    └─ 否则（attempt<3）→ 整段 rewrite
          complete(task_type="gen_next_chapter", rewrite=True,
                   review_feedback=字符串issues)   # 复用 gen_next_chapter
  ```
- 最坏成本：1 生成 + 1 review + 3×(整段重写 + review) = **4 次整章生成 + 4 次 review**。
- 预算耗尽：`status='needs_rewrite'`（仍交付 + 标记，不静默当 done）。

### 1.3 七维审查 `bootstrap.review_7dim`（v3.0.0，`prompt_registry.py:166`）
- 输出：`{score, dimensions{prose/plot/character_ooc/world_conflict/logic_consistency/pace/foreshadowing}, issues:[字符串], reader_experience{5维}}`。
- **`issues` 是纯字符串数组，无 type / severity** → 无法做分类路由（这是当前最大缺口）。

### 1.4 去 AI 味管线 `DeaiPipeline.run()`（`deai_pipeline.py:105-155`）
- 三步：`detect`（套话检测）→ `deai.rewrite`（**整段重写，一次完整章节生成，最贵**）→ `_heuristic_polish` + `_enforce_short_paragraphs`（免费）。
- 应用于：编辑器「去 AI 味」按钮 + V3 humanize。

### 1.5 编辑器实时审阅 `ai_edit`（`main.py:1381-1480`）
- `polish` / `rewrite` / `rewrite_chapter`：重试循环 `MAX_EDITOR_RETRIES=3`
  → `editor.polish/rewrite` 生成 → `review_7dim` → (`>=80` 且 `>=2000`) 通过，否则把 issues 拼进下轮 instruction。
- `deai` → `DeaiPipeline`（整段重写）。
- 前端「按全部建议润色 / 改写」按钮走这条非流式接口。

### 1.6 修复原语 / Repair Engine（**已存在，接线完整**）
| 原语 | prompt | 说明 | 接线 |
|---|---|---|---|
| `repair_local` | `bootstrap.repair_local` v1.0.0 (L889) | 锚点 `{anchor, replacement}` 局部替换 | gateway 契约 L537；worker `tasks.py:457-466`；API `api/v1/repairs.py`（`RepairAction`）；测试 `test_repair_engine.py` |
| `replan_chapter` | `bootstrap.replan_chapter` v1.0.0 (L905) | 重规划章节大纲 | 同上 |
| `write_fact_reconcile` | `bootstrap.write_fact_reconcile` v1.0.0 (L966) | 输出 `{conflicts_found, issues:[{type,detail,severity}], passed}` | **B 类格式已现成** |
| `rewrite_chapter` | `editor.rewrite` v3.2.0 (L218) | 整段重写 | 门禁/编辑器 |

### 1.7 Author Style Card / Writer DNA（**已存在，但仅 V3**）
- `app/services/author_style.py`：表 `author_style_signals`、`get_card()`、`record_signals()`、`run_author_style_learning`（m3_tasks Learning Agent，从用户编辑信号 kept/deleted/edited/liked 学）。
- `assembler._author_style_card()` 注入 → **仅 V3 long-run（`t5_long_run` / `fusion`）**。
- `tasks.py`（V2 章节生成）零引用；`gen_chapter1`(v3.2.0) / `gen_next_chapter`(v3.4.0) prompt **无 `style_card` 变量**。
- 更新靠 `api/v1/author_style.py` 手动 dispatch（非自动）。

### 1.8 `final_humanize`（`bootstrap.final_humanize` v1.0.2，`prompt_registry.py:1024`）
- 完整去味终校 pass（输出 `humanized_text` + `changes` + `ai_patterns_removed`）。
- 门禁循环（`tasks.py:2470`）**完全不调用**——当前每章靠 review+rewrite，不用 final_humanize。

### 1.9 当前成本模型（痛点）
- 单章最坏：4 整章生成 + 4 review（+ deai 时再 +1 整段重写）。
- `repair_local` 局部替换 ≈ 1/5 整章 token；但当前**根本没用上**。

---

## 2. 拟重构方案（To-Be）

### 2.1 七维审查结构化（分类器）— 决策 q0=A
- `review_7dim` 升 **3.0.0 → 3.1.0**：`issues` 改为
  ```json
  [{"type": "style|continuity|plot", "severity": "high|medium|low", "detail": "..."}]
  ```
  - `style` = 文风/AI味/表达（A 类）
  - `continuity` = 事实/前后矛盾/连贯（B 类）
  - `plot` = 剧情/结构/节奏（C 类）
- `gateway._ReviewOutput` 契约、`validate_task_output` 同步；下游读取处（门禁、前端审阅展示、`test_audit_round2`）改写。
- **单源、零额外 LLM 调用**。

### 2.2 门禁循环分类路由（决策 q3 含）
- `_review_and_finalize_chapter` 重写：放弃一律整段 rewrite → 按 `type` 路由：
  ```
  review_7dim（结构化 issues）
    ├─ style(A)      → repair_local 局部替换（≈1/5 整章 token）
    ├─ continuity(B) → write_fact_reconcile + repair_local
    └─ plot(C)       → replan_chapter + rewrite_chapter（仅这类整段重写）
  ```
- 保留最高分候选兜底；`CHAPTER_MAX_REWRITES` 仍限制总轮次。
- **首章（seq==1）仍走 `deai.rewrite` 整段打底**（质量优先，定文风）。

### 2.3 编辑器循环同步（决策 q3 含）
- `ai_edit` 的 `polish/rewrite/rewrite_chapter` 重试循环复用 `review_7dim` 结构化 issues 做同样分类路由；`deai` 仍整段。

### 2.4 Style Card 注入 V2 生成（决策 q1=A）
- `gen_chapter1`(3.2.0→3.3.0)、`gen_next_chapter`(3.4.0→3.5.0) 增加 `style_card` 变量并升版本。
- `tasks.py` 调用处从 `author_style.get_card(project_id)` 取值注入 → **日常 V2 路径也防风格漂移**。

### 2.5 Style Card 每 10 章自动重学（决策隐含）
- 章节定稿（`reviewed`）后若 `chapter_seq % 10 == 0` → `m3_tasks.run_author_style_learning.delay(project_id)`。
- 实现用户「每 10 章更新一次」。

### 2.6 final_humanize 抽样（决策 q2=A）
- 门禁通过后策略调用：
  - `seq==1` → 全量
  - `seq % 10 == 0` → 抽检
  - 其余 → 跳过
- 用户手动（编辑器 `deai` / `rewrite_chapter`）仍全量。

### 2.7 重构后成本模型
- **日常章（A/B 类为主）**：1 生成 + 1 review + 1 `repair_local`（≈1/5 整章）+ 启发式（免费）+ 抽样 humanize。
- 仅 **C 类（剧情/结构，少数）** 才整段 regenerate。
- 单章最坏 token ≈ 现状的 **1/2 ~ 1/3**；百万字下总差距 ×2~3。

### 2.8 To-Be 流水线总图
```
生成章节 (注入 Style Card)
  ↓
review_7dim 3.1.0（结构化 issues: type/severity）
  ↓
分类路由
  ├─ style(A)      → repair_local
  ├─ continuity(B) → write_fact_reconcile + repair_local
  └─ plot(C)       → replan_chapter + rewrite_chapter
  ↓
启发式润色（免费）
  ↓
final_humanize（首章全量 / 每10章抽检 / 手动全量）
  ↓
定稿 reviewed → 若 seq%10==0 触发 Style Card 重学
```

---

## 3. 文件级改动清单

| 文件 | 改动 |
|---|---|
| `gateway.py` | `_ReviewOutput.issues` 结构化；`validate_task_output` 适配 |
| `prompt_registry.py` | `review_7dim` 3.0.0→3.1.0 结构化；`gen_chapter1`/`gen_next_chapter` 加 `style_card` + 升版本；`deai.rewrite` 首章用 |
| `workers/tasks.py` | `_review_and_finalize_chapter` 分类路由；调用处传 `style_card`；每 10 章触发重学；humanize 抽样 |
| `main.py` | `ai_edit` 循环分类路由 |
| `app/services/author_style.py` | 复用 `get_card()`（可选：增量学习接口） |
| `api/v1/author_style.py` | 已存在手动 dispatch；自动触发点接入（可选） |
| 前端（审阅/设置页） | 审阅展示适配 issues 结构化；Style Card 状态 |
| 测试 | 新增 `test_deai_hybrid` / `test_classified_gate` / `test_style_injection`；适配 `test_audit_round2` |

---

## 4. 风险与回滚

- **review_7dim 契约变更（核心风险）**：波及门禁 / 前端 / 测试。回滚 = revert prompt 版本 + 下游读取兼容。
- **repair_local 局部替换可能改坏上下文**（尤其 B 类跨段事实）：先用 `write_fact_reconcile` 核对再替换；全程保留 best 候选兜底。
- **Style Card 注入可能让首章被错误风格带偏**：仅注入不强制；首章仍走 `deai.rewrite` 打底。
- **C 类误判为 A**：阈值规则——`severity=high` 的 `plot` 必走 `replan`；仅 `medium/low` 的 `style/continuity` 走局部替换。

---

## 5. 验证与上线（vibe-coding 门禁）

- 本地：现有 39 项相关测试 + 新增 3 套（hybrid / classified_gate / style_injection）全绿。
- CI：5 job（backend / frontend / frontend-test / e2e / security）全绿。
- 部署：SSH ff-pull + 应用容器重建（postgres/redis 不动）；`healthz` 200；`prod_smoke.py` **14/14**。

---

## 6. 决策记录（grill-me 共识）

| 编号 | 议题 | 结论 |
|---|---|---|
| q0 | 分类器实现 | **升级 review_7dim 输出为结构化**（单源、零额外调用） |
| q1 | Style Card 接入 | **注入 V2 日常章节生成**（gen_chapter1 / gen_next_chapter） |
| q2 | final_humanize 抽样 | **首章全量 + 每 10 章抽检 + 手动全量** |
| q3 | 实施分期 | **三块一次做**（分类路由 + Style Card 注入 + humanize 抽样） |
| — | Provider 策略 | DeepSeek-only（Phase 1）；不接 Qwen；不建 model_routes 脚手架（评估阶段） |
| — | 质量门禁 | 保持严格「七维 <80 自动重写」（成本 ×2~4 接受） |
| — | 用户评分 | 工程合理性 95 / 成本控制 95 / 百万字可持续 90 / 质量上限 80 / 商业化 75 → **综合 88-90** |
