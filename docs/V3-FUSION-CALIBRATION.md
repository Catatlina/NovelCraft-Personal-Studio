# V3 融合需求文档 — 代码对照校准分析

> 校准对象：`docs/NovelCraft-V3-融合需求与开发文档.md`（Draft v1.0）
> 校准方式：直接读取 `backend/app` 实际代码（非 PRD 描述）
> 触发原因：原文档第 5 行自陈「未能直接读取代码…落地前需与实际代码对照校准」
> 结论：**文档基线基本属实，增量融合路径可行**；仅少量表述需澄清（见 §2）

---

## 1. 结论速览

- 文档第 0 节「在现有 8 个子系统上做增量」——与代码实际架构一致，方向正确。
- 文档第 1 节「现状基线」所列能力，**多数可在代码中找到真实实现**（见 §3 对照表）。
- 唯一需澄清的是「10 Agent」的指向（见 §2.1）；「七维 / 七层」的表述与代码一致（见 §2.2–2.3）。
- 文档第 13 章分阶段计划合理；第 0 阶段（先验证现有百万字能力）尤其必要，因为现状仍有大量 🧪 待验收项。

---

## 2. 需澄清的三处表述

### 2.1 「10 Agent」实际是两套并存的概念

- **生成主链路 Agent 角色**：`backend/app/workers/tasks.py` 中以 `agent` 字段定义节点角色（已确认 `Reviewer` 等），这是文档所说的「Producer / Story Architect / Character / Writer / Editor / Reviewer / …」10 个 Agent 的真实落点——它们是 Workflow 节点的角色标签，经 Producer 编排进 WorkflowPlan。
- **平台级 Agent 目录**：`backend/app/platform/agents/manager.py` 的 `AgentManager` 是另一套注册表，内置 3 个（`novel-author` / `content-editor` / `hotspot-analyzer`），用于平台/插件体系。
- 两者**不冲突**：文档的「10 Agent 禁止互调」约束对应主链路节点角色；平台 AgentManager 是独立目录。融合新 Agent 时按文档第 7 章「经 Producer 编排进 WorkflowPlan 节点」即可。

### 2.2 「七维审核」代码侧已存在

- `backend/app/workers/tasks.py:73` 定义节点 `("final_consistency_check", "agent", "Reviewer", "七维一致性检查", ...)`——七维一致性检查是真实流水线节点。
- 另有 `backend/app/services/fusion_deep_book.py` 的 `six_dim_consistency_check`（六维：characters/locations/timeline/items/settings/relationships），属遗留/并行实现。**融合时复用 `七维一致性检查` 节点，不要再新建评分体系**。

### 2.3 「7 层上下文装配」代码侧已存在

- `backend/app/services/deai_pipeline.py:26` 注释 `# 7 层管线定义（名称 + 说明）`——Context Engine 的 7 层装配真实存在。
- `backend/app/core/ai_memory.py` 负责跨章记忆上下文装配（`get_novel_memory` / `inject_memory_context`，含角色/世界/时间线/弧线）。
- 注意：当前代码并存「7 层管线 / 十层分析 (`ten_layer_analysis.py`) / 六维一致性」三套「层/维」概念。叠加 V3 时**必须复用现有装配与评分节点**，避免引入第四套。

---

## 3. 8 子系统 ↔ 代码对照表

| 文档所述子系统 | 代码实证 | 状态 |
|---|---|---|
| Workflow Engine（节点/幂等/断点续跑） | `workers/tasks.py` 定义节点管线（agent/type/名称/函数）+ retry 机制 | ✅ 存在 |
| Agent 系统（10 个，禁止互调） | 主链路 `agent` 角色字段（`Reviewer` 等）+ 平台 `AgentManager`（3 个） | ⚠️ 见 §2.1（两套并存） |
| Context Engine（7 层上下文装配） | `deai_pipeline.py:26` 7 层；`core/ai_memory.py` | ✅ 存在 |
| Story Bible（人物/世界观/大纲/细纲） | `services/entity_tracker.py` 的 `entity_states` 表（character/location/relationship）+ 规划产出存 `contents.meta` | 🟡 部分：实体状态追踪已落地；「大纲/细纲」多为 meta 内 JSON，非独立强 Schema 实体 |
| Quality Engine（七维审核） | `workers/tasks.py:73`「七维一致性检查」节点 | ✅ 存在（见 §2.2） |
| Version System（VersionedRepository/版本树） | `main.py` `list_versions` / `restore_version`；versions 表 + diff | ✅ 存在 |
| Knowledge Hub（pgvector/风格学习/RAG） | `main.py /api/v1/knowledge/style-learn`（M3）；`api/v1/imitation.py`（仿写红线）；`apps/novel/router` 引用 style | ✅ 风格学习+仿写存在（pgvector 需二次确认，但能力线索齐备） |
| 创作入口层（扫榜/灵感/拆书） | `api/v1/ranking.py`（扫榜/市场分析）、`hotspots.py`（热点）、`ten_layer_analysis.py`（拆书十层） | ✅ 存在 |

---

## 4. 各章节落地可行性（摘要）

| 章节 | 挂载点 | 可行性 | 备注 |
|---|---|---|---|
| 3 Novel DNA | `novel.meta`，无新表 | ✅ 低成本 | Schema 扩展 + prompt 扩展，与现有「创作圣经」合并 |
| 4 Story Arc | 新增 `arc` entity_type，`parent_id` 兼容 | ✅ 可行 | 同意文档「先单层」主张，阶段/场景留待二/三阶段 |
| 5 Chapter Function | 细纲 Schema 加 3 字段 | ✅ 最低成本，优先 | 正文生成前轻量 branch 校验 |
| 6 策略库 + Prompt Compiler | `platform/skills` 已有 `SkillManager`（`golden-chapters`/`character-designer`/`de-ai` 等）；`prompt_registry.py` 存在 | ✅ 种子已在 | 先做 3–5 个高频策略 MVP，不做通用 Compiler |
| 7 新增 Agent | 经 Producer 编排进 WorkflowPlan 节点 | ✅ 与现有机制一致 | Planner/Repair 第一阶段做；Scene Director/Learning 后续 |
| 8 Repair Engine | 分级修复，复用现有整章重写兜底 | ✅ 可行 | 8.4「局部修复不分支」的偏离建议合理，需与版本系统对齐 |
| 9 人物认知分层 | `entity_states.known_info` 拆 5 层 | ✅ 字段扩展，低成本 | 复用现有逐章更新机制 |
| 10 时间线锚点 | `timeline_event` 加 `real_world_anchor` | ✅ 低成本 | 仅「现实向」题材启用，避免误判架空/玄幻 |
| 11 读者体验 + Pacing | 复用 Reviewer LLM 扩展维度 + 前端曲线（复用图表组件） | ✅ 可行 | 前端为主 |
| 12 Author Style Card | 扩展 `style_learn` 输入源（编辑器 diff） | ✅ 可行 | 依赖足够编辑 diff 数据积累，放第三阶段合理 |

---

## 5. 需要用户/团队决策的点（对应文档第 15 章开放问题）

1. **场景层是否做**：建议先不做，Chapter Function 已能缓解「信息展示型」水字；待 Arc 验证有效后再定。
2. **局部修复是否产生版本分支**：文档 8.4 提议「不分支，作同节点增量」——合理，避免版本树膨胀，需版本系统负责人确认。
3. **策略库维护方式**：建议第一阶段人工整理网文套路（成本可控），暂不反向抽取。
4. **Learning Agent 用编辑器 diff 做风格学习的隐私/合规口径**：需与现有 RBAC / 离线策略一起过合规。

---

## 6. 风险与建议

- **第零阶段不可跳过**：现状大量 🧪 待验收项（文档第 1 节自承）。先对「7 层上下文装配 + 每 10 章巡检 + 卷级复盘门禁」做一次真实百万字量级验证，再叠加 V3 新能力，否则出问题无法归因是底层引擎还是新策略。
- **避免第四套「层/维」**：现有 `deai_pipeline` 7 层、`workers` 七维、`ten_layer` 十层并存，V3 新增必须挂接现有节点，不再新建并行体系。
- **严格按文档第 14 章提交格式**：每条需求必须回答「挂载点 / 数据模型 / Schema 注册 / 上下文预算 / 影响范围 / 验收标准 / 禁止项」，杜绝「假完成 / 空页面 / 只建字段不接 AI 流程」。

---

## 7. 校准结论

文档是一份**高质量、可执行的增量融合方案**。其基线假设除「10 Agent」需澄清为「主链路 agent 角色 + 平台 AgentManager 目录并存」外，与其余代码实证一致。可进入按第 13 章「第一阶段」5 条需求的逐条填单排期（建议优先顺序：Chapter Function → Novel DNA → Story Arc → 策略库 MVP → Repair Engine 三级版）。
