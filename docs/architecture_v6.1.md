# 百万字 AI 小说连载生产系统：完整架构设计文档（v6.1.2 封版·最终工程补丁）

> 状态：**架构封版（v6.1.2，真正冻结，不再新增大型模块，亦不再有 v6.2）** → 进入 Phase 1 开发
> 日期：2026-07-31
> 定位：**个人版 AI 长篇小说生产操作系统**（非产品、非多用户、非自动发布）
> 目标：书名 / 简介 / 大纲 / 分卷树 / 章节树 / 每章详纲 / 正文全部由 AI 生成；达到网文中上游作家水平的连贯性、可读性，且去除 AI 味；支持百万字级持续连载
> 模型策略：Phase 1 **DeepSeek-only**，不提前搭多模型路由、不接 Qwen

---

## 0. 版本演进与封版说明

| 版本 | 内容 | 状态 |
|---|---|---|
| v6 | 作者意图 + 不可破坏规则、Story Bible、大纲体系、章节生产管线、去 AI 味多层防御、Style Card、可追溯性、章节状态枚举、token 预算、分期路线 | ✅ 吸收 |
| v6.1 | 在 v6 上新增 7 项（人物能力树 / 世界状态 / 读者情绪曲线 / 题材逻辑审查 / author-genre Style 分离 / Prompt Registry / 修复保护区） | ✅ 吸收 |
| **v6.1.1（封版）** | 新增 5 个**工程级**小项（book_config / context_package / task_retry_policy / chapter_audit_report / 人工 checkpoint）；情绪曲线由硬规则改为 warning；domain_logic 第一版限定 10-20 条 | ✅ 吸收 |
| **v6.1.1 终版补丁（4 项）** | `entities.entity_type`+`importance_level`；`chapter_summary`+`arc_summary` 双级摘要；`style_change_confidence` 防污染；`LLMProvider` 抽象接口 | ✅ 吸收 |
| **v6.1.2（本版·最终工程补丁，封版）** | 5 个**字段级**补丁（chapter_snapshot 防历史漂移 / fact_confidence 防误回写 / repair_version 失败回滚 / book_status 多书状态机 / generation_cost_log 成本账） | 🆕 封版冻结（不再有 v6.2） |

**封版原则**：用户最终评分 **9.3/10**（百万字连续 9.5 / 长篇一致性 9.5 / 成本控制 9 / 防 AI 味 8.5 / 工程落地 9.3 / 复杂度控制 9）。最大风险是**实现复杂度控制**而非架构缺失。明确**禁止**再增加：AI 导演 / 多 Agent / RAG / 自动评价 / 读者模拟 / 多模型路由 / 自动发布。v6.1.1 的 4 项 + v6.1.2 的 5 项字段补丁全部并入后**真正冻结**，下一步从数据库 Schema 开始工程落地。

---

## 1. 设计哲学

1. **反馈粒度必须匹配修复粒度**——小问题局部修，大问题才整段重写（分类路由已确立）。
2. **长篇小说的核心风险是跨章一致性与漂移**——系统复杂度应花在防漂移上。
3. **不用编造的指标伪装质量保证**——能用规则/统计判断的优先用规则/统计。
4. **🆕 工程落地性优先于功能完整度**——Context 成本可控、失败可恢复、人工介入点明确，比堆模块重要。

---

## 2. 总体分层架构（v6.1.1 最终图）

```
book_config（书级配置：genre/theme/author_intent/immutable_rules/domain_type）🆕
   │
作者意图 + 不可破坏规则
   │
Story Bible（单一事实源）
   ├─ 人物状态 / 成长（弧线）/ 能力（能力树）/ 关系（关系弧线）
   ├─ 世界状态（动态）/ 时间线
   ├─ 剧情线（plot_threads）/ 伏笔账本（到期窗口）
   │
大纲系统（总纲 / 分卷树 / 滚动重规划 / 章节契约）
   │
Context Builder（Context Assembly Engine）🆕
   ├─ 固定层：author rules + immutable_rules
   ├─ 长期层：Story Bible 快照
   ├─ 中期层：卷 / 剧情线
   ├─ 短期层：最近 N 章摘要
   ├─ 当前层：chapter_contract + scene_plan
   └─ 风格层：style_card（author + genre）
   → 产出 context_package（included 清单 + token_budget）🆕
   │
正文生成（注入 context_package + capability_tree + world_state）
   │
多维审核（review_7dim 结构化 + domain_logic 插件）
   │
分类路由 ───┬─────────────┬────────────────┐
   ├ style(A)│ continuity(B)│ plot(C / high) │
   ↓         ↓             ↓                │
repair_local fact_reconcile replan+rewrite   │
（受保护区） +repair_local                    │
   └─────────┴─────────────┴────────────────┘
   │
去 AI 味多层防御 → 定稿（受 protected_elements 保护）
   │
状态回写 Story Bible → 每 10 章 Style Card 重学 + 重规划
   │
人工 checkpoint 🆕：建书确认 / 每卷确认 / 每 100 章 chapter_audit_report
```

---

## 3. 作者意图 + 不可破坏规则 + book_config

`author_intent` / `immutable_rules` 是全局最顶层约束，每次生成 prompt 注入。本版明确它们**挂在 `book_config` 书级配置表**上（而非散落），每本书不同：

```json
// book_config
{
  "id": "bk_001",
  "title": "重生：从工程师到首富",
  "genre": "都市重生",
  "domain_type": "urban_business",          // 决定启用哪个 domain_logic 插件
  "target_words": 1000000,
  "author_intent": {
    "theme": "人生重来一次，不只是赚钱，而是弥补遗憾",
    "core_emotion": "温暖、成长、家庭",
    "reader_expectation": "爽，但不能失去生活真实感",
    "avoid": ["纯装逼", "无脑打脸"]
  },
  "immutable_rules": [
    {"rule": "主角不会为了利益伤害普通人", "priority": "hard"},
    {"rule": "不靠纯外挂解决所有问题", "priority": "hard"}
  ],
  "status": "draft"   // 见 §10.4 book_status 状态机（draft→...→archived）
}
```

> 注：`book_config.status` 是 `book_status` 状态机（§10.4）的子字段，与章节状态枚举（§9）相互独立。

- `immutable_rules` 接入 §6.1 致命维度门禁——违反即强制修复，无论总分。
- 建书后由用户一次性写好；进入 `serializing` 前需人工 Checkpoint 1 确认（§10.2）。

---

## 4. Story Bible 设定库（全系统单一事实源）

### 4.1 核心表结构（含 v6.1.1 新增）

| 表 | 内容 | 谁写 | 谁读 |
|---|---|---|---|
| **`book_config`** 🆕 | 书级配置（genre/domain_type/author_intent/immutable_rules/target_words/status） | 建书时用户 | 所有生成 prompt |
| `entities` | 人物/地点/组织/物品，含状态 + `character_arc` + `capability_tree` + **🆕`entity_type`(character/location/organization/item/concept) + `importance_level`(1-10)** | fact_reconcile | 生成、review、Context Builder（按 importance 决定加载） |
| `timeline` | 事件-时间锚点 + "谁知道" | fact_reconcile | continuity |
| `world_state` | 世界动态快照（公司规模/资产/市场格局） | 定稿回写 | 生成、domain_logic |
| `foreshadowing_ledger` | 伏笔账本（到期窗口 + reader_awareness） | 生成登记 + 回写 | 详纲、review |
| `plot_threads` | 剧情线进度 | 定稿回写 | 详纲 |
| `chapter_emotion_state` | 读者情绪曲线（最近 N 章序列） | 定稿回写 | 详纲（warning） |
| `style_card` | author_style + genre_style 分离 | author_style 学习 | 生成 |
| `outline_versions` | 大纲/细纲版本历史 | 滚动重规划 | 详纲 |
| `chapter_summaries` | 每章轻量结构化摘要 | 定稿回写 | 重规划 |
| `prompt_registry` | Prompt 模板库（name/version/provider/body/variables） | Prompt 管理 | init_db / 渲染 |
| **`context_package`** 🆕 | 每章 Context Builder 装配记录（included + token_budget） | Context Builder | 成本诊断、重放 |
| **`chapter_audit_report`** 🆕 | 每 100 章自动审计报告 | 审计任务 | 人工 Checkpoint 3 |
| **`chapter_snapshot`** 🆕 | 章节锁定不可变快照（content_hash + story_state_hash + entity_state_hash + outline_version）| 锁定动作 | 历史一致性校验、跨章回滚影响分析 |
| **`fact_confidence`** 🆕 | 状态回写每条事实带 confidence（<0.8 仅候选不进硬约束）| 回写任务 | 门禁、fact_reconcile |
| **`repair_versions`** 🆕 | 每次 repair 的 before/after 对照 + 二次 review 结论（after<before 自动回滚）| repair 任务 | 修复污染防护 |
| **`book_status`** 🆕 | 小说整体状态机（draft→worldbuilding→outline_confirmed→serializing→paused→completed→archived）| 用户/编排 | 多书管理 |
| **`generation_cost_log`** 🆕 | 每章 token/cost 明细（generate/review/repair/humanize/total）| 各任务 | 成本优化、预算监控 |

### 4.2 人物弧线 + 关系弧线

`entities` 加 `character_arc`（initial_flaw / growth_goal / current_arc_stage / turning_points）+ 关系弧线。详纲生成时读取约束该章反应符合当前弧线阶段。

### 4.3 🆕 人物能力树（character_capability，防降智）

```json
{
  "capability_tree": [
    {"skill": "软件开发", "level": "高级", "acquired_chapter": 1,
     "evidence": "开发完成 XX 系统", "limitations": "缺管理经验、不懂资本运作"},
    {"skill": "证券投资", "level": "初级", "acquired_chapter": 50,
     "evidence": "跟投朋友公司获利", "limitations": "仅二级市场跟投"}
  ]
}
```

挂在 `entities` 人物子结构，定稿回写（`acquired_chapter` + `evidence` 必须来自已定稿正文）。生成 prompt 注入 → 约束主角只能用"已获得且等级匹配"的能力；越级使用被 `domain_logic` 审查拦截。`limitations` 是防降智核心。

### 4.4 剧情线（plot_threads）

持续进度追踪（区别于伏笔账本）。详纲生成前读取活跃剧情线，决定该章推进哪条，避免支线烂尾。

### 4.5 伏笔账本（到期窗口 + reader_awareness）

`expected_payoff_window` + `status`（open/due_soon/overdue/resolved）+ `reader_awareness`（决定叙事视角策略）+ `importance`。详纲生成前强制查 due_soon/overdue 作硬约束。

### 4.6 🆕 世界动态状态（world_state）

记录"世界变成什么样"而非仅"发生什么事件"：

```json
{"chapter": 100, "time": "2015-Q3",
 "company": {"employees": 500, "cash": 30000000, "products": ["APP"], "valuation": 200000000},
 "market": {"competitors": ["腾讯","阿里"], "industry_trend": "移动互联网爆发"},
 "society_impact": "区域行业标杆"}
```

定稿回写，注入生成 prompt 约束下一章世界规模一致；被 `domain_logic` 校验成长速度。

### 4.7 🆕 双级摘要层（chapter_summary + arc_summary）

每章定稿生成轻量结构化摘要，**分两个级别**：

- **`chapter_summary`**（短摘要，≤500 字）：单章发生了什么、关键人物、关键决策。
- **`arc_summary`**（卷摘要）：一卷的聚合——主线推进、核心转折、人物变化。

```json
{"book_id":"bk_001","arc":"第一卷","arc_summary":"主角重生→建立公司→结识核心团队→完成首次商业突破"}
```

Context Builder 短期层加载策略（第 300 章也不爆）：**最近 10 章 `chapter_summary` + 当前卷 `arc_summary` + 全书阶段摘要**，而非逐章原文。向量记忆仅条件触发（结构化+摘要不够用时再引入）。

### 4.8 🆕 Context Assembly Engine + context_package

**v6.1.1 核心工程项——整个系统最关键的"AI 每章看到什么"由它决定。** 不能"全部塞进去"，必须分层装配并记账，否则百万字后上下文成本失控。

```
章节生成请求
   ↓
Context Builder（分层装配）
   ├─ 固定层：author rules + immutable_rules
   ├─ 长期层：Story Bible 快照（人物/世界/伏笔当前态）
   ├─ 中期层：卷 / 剧情线当前进度
   ├─ 短期层：最近 10 章 chapter_summary + 当前卷 arc_summary + 全书阶段摘要
   ├─ 当前层：chapter_contract + scene_plan
   └─ 风格层：style_card（author + genre）
   ↓
产出 context_package（记录本次实际装配内容 + token 预算）
```

```json
{
  "chapter": 100,
  "included": ["character_main", "world_state", "foreshadowing_5", "recent_summary_10", "arc_summary_current", "chapter_contract"],
  "token_budget": 8000,
  "actual_tokens": 7420
}
```

- 存 `context_package` 表，随 lineage 关联 → 用于成本诊断与失败重放（§6.3 `reduce_context` 策略依赖它）。
- 分层而非全量塞入，是 Context 成本可控的关键工程手段。

---

## 5. 大纲体系

### 5.1 层级 + 章节契约

总纲 → 分卷树 → 分卷细纲 → 章节树 → 每章详纲（scene_plan + chapter_contract）。`chapter_contract` 含 `must_achieve` / `must_not` / `ending_hook`，给生成硬约束 + review 检查依据。

### 5.2 🆕 读者情绪曲线（warning，非硬拦）

**v6.1.1 调整**：原"禁止连续 10 章压抑"硬规则**改为 `emotion_balance_warning`**——只检测提示、不硬拦，避免限制创作（悬疑小说可能 20 章压抑）。

```json
{
  "reader_emotion": {
    "recent_chapters": [{"chapter": 41, "state": "压抑"}, ...],
    "current": "缓冲",
    "recent_peak": "第43章收购成功",
    "next_need": "制造新危机"
  },
  "emotion_balance_warning": {
    "triggered": true,
    "recent_20_chapters": {"压抑": "80%", "爽": "5%", "缓冲": "15%"},
    "hint": "近 20 章压抑占比偏高，建议下一章安排释放或爽点（仅供参考，不强制）"
  }
}
```

- 定性枚举（压抑/冲突/爆发/爽/缓冲/期待），不折算分数、不进门禁。
- warning 仅作生成建议提示，人工/模型可忽略。

### 5.3 滚动重规划（自适应窗口）

详纲只滚动生成未来 10~15 章；窗口长度依上一窗口执行偏差自适应（偏差小放大、偏差大收缩）；卷边界强制归位重生成。与 Style Card 重学共用每 10 章触发点。

### 5.4 大纲版本化

每次重规划产生新版本，旧版本 `superseded`，不删除。

---

## 6. 章节正文生产管线 + 多维审核

```
生成章节（注入 context_package + capability_tree + world_state）
  ↓
review_7dim（结构化 issues: type/severity/repair_scope）
  ↓
domain_logic（按 domain_type 启用插件，第一版 10-20 条核心检查）🆕约束
  ↓
分类路由
  ├─ style(A)      → repair_local（受 protected_elements 保护）
  ├─ continuity(B) → write_fact_reconcile + repair_local
  └─ plot(C, high) → replan_chapter + rewrite_chapter
  ↓
启发式润色 → 去 AI 味多层防御 → 定稿（受 protected_elements 保护）
  ↓
状态回写 Story Bible（每条事实带 fact_confidence，<0.8 仅候选不进硬约束）→ 每 10 章 Style Card 重学 + 重规划
```

首章仍走 `deai.rewrite` 整段打底。

### 6.1 致命维度硬性门禁

总分降级为参考信息；`character_ooc` / `world_conflict` / `logic_consistency` 任一 `severity=high` 或 `immutable_rules` 违反 → 强制修复；`plot=high` 强制 C 类 replan+rewrite；`prose`/`pace` 仅触发 `repair_local`。

### 6.2 🆕 题材逻辑审查（domain_logic，第一版轻量）

按 `book_config.domain_type` 启用插件（urban_business / xuanhuan_power / sci_fi_tech）。**第一版每个题材只做 10~20 个核心检查，不做专家系统、不堆几百条规则**：

```
都市 business_logic 核心检查（示例，约 10-15 条）：
- 财富来源合理性 / 公司规模与章节匹配度 / 时间跨度合理性
- 技术领先性 / 人脉增长斜率 / 融资节奏 / 市场竞争格局一致性
```

- 校验依据 = `capability_tree`（能力越级）+ `world_state`（成长越界）。
- 输出并入 review_7dim `issues`（type=plot/continuity），复用分类路由，不新增门禁分支。
- 初版阈值**从宽**，避免误伤合理高速成长。

### 6.3 🆕 任务失败恢复策略（task_retry_policy）

**v6.1.1 核心工程项。** 百万字生产必遇 API 失败 / 超时 / 输出截断 / JSON 格式错误 / review 失败。不能只靠 Celery 默认无限重试。

```json
{
  "task": "generate_chapter",
  "retry": {
    "max": 3,
    "strategy": ["retry_same", "reduce_context", "fallback_prompt"]
  }
}
```

- `retry_same`：同参数重试（瞬时故障）。
- `reduce_context`：读 `context_package` 缩减 token_budget 再试（应对截断/超长）。
- `fallback_prompt`：切到更稳健的 prompt 版本（应对结构化输出失败）。
- 不同任务不同策略：`review` 失败可降级跳过（记为 warning，不阻断门禁）、`repair_local` 失败回退整段 rewrite、`replan` 失败回退沿用旧详纲。
- 超过 `max` → 章节状态置 `failed`，触发人工 Checkpoint，不静默丢失。

### 6.4 修复保护机制（protected_elements + repair_version 回滚）

`repair_local` 已有 `preserve` / `risk_level`（high 不自动应用），再补"禁止修改区域"：`protected_elements` 命中锚点（关键对白 / 人物第一次事件 / 伏笔线索 importance>=8）不得被替换。

**🆕 repair_version 失败回滚（v6.1.2）**：局部修复比重写更危险，必须存对照并可回退：
- 每次 `repair_local` 前保存 `before_repair`（原正文锚点段），修复后存 `after_repair`；
- 修复后**二次 review**（轻量 7 维），若 `after_score < before_score` 或新引入 high 级问题 → **自动恢复 before_repair**，并记 warning；
- 全程写入 `repair_versions` 表（before/after + 二次 review 结论），事后可解释、可人工复核。

---

## 7. 去 AI 味：多层防御

- 第一层：生成时约束（AI 套话黑名单 + 硬约束禁套话/总结体/AI 连接词；软约束倾向动作化/口语化，**不写固定频率规则**）。
- 第二层：客观文体统计检测（句长方差 / TTR / 对话占比 / 套话命中率，本地脚本零 LLM 成本；指标越界自动升级 humanize 全量）。
- 第三层：final_humanize 终校（首章全量 / 越界触发 / 每 10 章抽检 / 手动全量）。

---

## 8. Style Card / Writer DNA

注入 V2 日常生成，每 10 章基于用户编辑信号重学。

### 8.1 🆕 author_style 与 genre_style 分离

```json
{
  "style_card": {
    "author_style": {"sentence_length":"短句偏多","dialogue_ratio":"35%","narration_distance":"近距离","humor":"低","emotion":"克制"},
    "genre_style": {"pace":"快","tension_density":"高","satisfaction_cadence":"每3-5章一个爽点"}
  }
}
```

`author_style` 跨书稳定慢学；`genre_style` 随题材切换；重学时分别更新不互相污染。

### 8.2 冷启动

新书无编辑信号时从 `author_reference_library` 按品类抽统计特征作初始 Style DNA；第一轮信号回来后正常学习任务接管。与 §7 第二层共用底层计算设施。

### 8.3 🆕 Style 防污染（style_change_confidence）

`author_style` 跨书稳定，不能被 AI 自动无限改写。新增 `style_change_confidence` 门控：

- AI 检测到"连续多章对话比例提升"等风格偏移信号时，**不立即改 `author_style`**；
- 需累计 **≥3 次人工认可**（用户在编辑器接受/采纳该风格建议）才允许写入 `author_style`；
- `genre_style` 随题材可更快调整，但同样走置信度累计，避免单章异常污染整书风格；
- 每次 Style 修改都写 lineage（`style_card_version` + `confidence`），事后可解释。

---

## 9. 可追溯性与版本管理

- 章节 lineage：style_card_version / outline_version / prompt_versions / repair_path（含 repair_version 对照）/ scores / reader_metrics（预留空字段）。
- 🆕 `generation_cost_log`：每章按任务记 token 与成本（generate / review / repair / humanize / total），事后优化 DeepSeek 成本、预算监控用。
- 简单章节状态枚举：`draft → generating → reviewing → repairing → approved → published → locked` + 失败态 `failed` / `retrying`。
- Token 预算：每书 `used_tokens` / 累计成本，达阈值提醒不中断。
- **Prompt Registry**：对应现有 `prompts` 表（`PROMPT_SEEDS` 以 name/version/provider/body/variables 入库，max version wins）；lineage 显式记录每章 prompt_versions，事后可解释"为什么第 101 章画风变了"。
- 范围声明：不做自动发布 / 版权审核引擎 / 通用模板引擎 / 外部知识库 / 质量看板 / 多租户。

### 9.1 🆕 LLM Provider 抽象接口（工程抽象，非路由）

Phase 1 仍 DeepSeek-only，但代码层**不散落 `deepseek.chat()` 调用**。统一抽象：

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, task_type, prompt_name, variables, params) -> dict: ...

class DeepSeekProvider(LLMProvider): ...   # 当前唯一实现
```

- 所有生成/审查/修复调用走 `LLMProvider.complete`，由 `gateway.complete()` 内部 dispatch；
- 未来若接 Qwen/本地模型，仅新增一个 `XxxProvider` 子类 + 在 `PROVIDERS` 注册，**不改动任何调用方**；
- 这与"不建 model_routes / 不搭多模型路由"不冲突——抽象是工程解耦，路由是运行时分流策略，二者独立。

---

## 10. 风险、人工介入点与审计

### 10.1 已知风险

全自动 300+ 章零检查点，漂移已知高风险（Style Card + 重规划缓解不消除）；`repair_local` 局部替换仍可能改坏潜台词（§6.4 保护 + repair_version 回滚是缓解）；`domain_logic` 初版阈值从宽避免误伤；AI 误判回写可能污染 Story Bible（§4.1 `fact_confidence` 门控缓解）；历史章节被改导致世界线漂移（🆕 §10.5 `chapter_snapshot` 缓解）。

### 10.2 🆕 人工 Checkpoint（3 个明确节点）

**v6.1.1 核心工程项——把"人工介入"从含糊的"每卷抽查"明确为三个固定节点：**

- **Checkpoint 1（建书后）**：用户确认世界观 / 主角 / 大方向、`book_config` 置 `confirmed` 才允许大规模生成。否则后续难改。
- **Checkpoint 2（每卷结束）**：确认人物有没有跑偏、主线有没有偏。读卷末即可，不逐章审。
- **Checkpoint 3（每 100 章）**：系统自动生成 `chapter_audit_report`（见下），人看报告不读正文。

### 10.3 🆕 百章审计报告（chapter_audit_report）

**v6.1.1 核心工程项。** 每 100 章自动生成，汇总而非逐章：

```json
{
  "report_at_chapter": 100,
  "character_changes": ["主角：从自卑→主动争取（弧线 stage 推进）"],
  "wealth_changes": ["个人资产 0 → 3000万；公司 0 → 500人"],
  "capability_changes": ["新增：证券投资(初级@50章)"],
  "foreshadowing_status": {"open": 12, "overdue": 2, "resolved": 8},
  "style_drift": {"author_style_v1→v10": "句长分布偏移 +5%"}
}
```

- 存 `chapter_audit_report` 表，供 Checkpoint 3 人工读。
- 不依赖真实读者数据，纯从 Story Bible 状态**规则聚合**；**第一版 100% 规则生成、零 LLM 调用**（直接统计人物状态变化/资产曲线/能力新增/伏笔 open-overdue/风格统计偏移），不调用 AI 生成，避免每 100 章增加成本。

### 10.4 🆕 书级状态机（book_status）

章节有状态枚举（§9），但**小说整体**也需要状态机，否则多本书管理会乱（v6.1.2 字段级补丁）：

```
draft → worldbuilding → outline_confirmed → serializing → paused → completed → archived
```

- `draft`：刚建书，仅 `book_config` + 作者意图；
- `worldbuilding`：搭 Story Bible（人物/世界/能力树）；
- `outline_confirmed`：大纲确认，可进入生成（= Checkpoint 1 通过）；
- `serializing`：日常连载中；
- `paused`：作者主动暂停（不丢状态）；
- `completed`：全文完结；
- `archived`：归档不再改动。
- 状态切换由用户/编排触发，写入 `book_status` 表（带变更时间 + 触发原因），与章节状态枚举相互独立。

### 10.5 🆕 章节锁定快照（chapter_snapshot，防历史漂移）

章节 `locked` 后禁止直接改动，但需防"改了第 30 章一句话、第 500 章状态失效"的历史漂移（v6.1.2 字段级补丁）：

- 锁定动作发生时，保存不可变快照到 `chapter_snapshot`：`content_hash`（正文哈希）、`story_state_hash`（当时 Story Bible 状态哈希）、`entity_state_hash`（实体状态哈希）、`outline_version`（当时大纲版本）；
- 后续若改动历史章节，先比对 `story_state_hash` / `entity_state_hash`，发现下游已定稿章节依赖的旧状态失效 → 触发"跨章回滚影响分析"（P2 条件项），人工决定；
- `locked` 章节正文不可经 editor 直接改，必须经 `replan+rewrite` 全流程重走门禁，保证一致性。

---

## 11. 分期路线（封版）

| 阶段 | 内容 |
|---|---|
| **P0** | review_7dim 结构化 + 门禁分类路由 + repair_local 保护 + Style Card 注入 V2 + humanize 抽样 + 致命维度硬性门禁 |
| **P0.5** | DEAI 硬频率改软约束；文体统计检测脚本 |
| **P1** | 滚动重规划 + 自适应窗口；伏笔到期窗口；lineage；Style DNA 冷启动；章节摘要；scene_plan+contract；人物弧线+关系；**能力树**；**世界状态**；**情绪曲线(warning)**；**题材逻辑插件(10-20条)**；**author/genre Style 分离**；**Prompt Registry**；**修复保护区**；章节状态枚举；token 预算；**🆕 book_config**；**🆕 Context Assembly Engine + context_package**；**🆕 task_retry_policy**；**🆕 人工 checkpoint + 百章审计**；**🆕 entity_type+importance_level**；**🆕 双级摘要 chapter_summary+arc_summary**；**🆕 style_change_confidence**；**🆕 LLMProvider 抽象**；**🆕🆕 v6.1.2 五项字段补丁：chapter_snapshot 防历史漂移 / fact_confidence 防误回写 / repair_version 失败回滚 / book_status 多书状态机 / generation_cost_log 成本账** |
| P1.5 | Reader Simulation 弱化版（定性建议，不进门禁不折算分数） |
| P2（条件/远期） | Reader Simulation 定量版（需真实完读率回填）；跨章回滚影响分析；向量记忆层 |
| P3（远期） | 真实读者反馈闭环，回填 `reader_metrics` |

> **架构已封版（v6.1.2）。P1 内全部 🆕 工程项彼此解耦，可拆独立 PR 分批上线，不阻塞 P0。**

---

## 12. 与已确认决策的一致性

- DeepSeek-only，Phase 1 不接 Qwen，不建 model_routes（扩展点已存在于 `gateway.py`）。
- 三块（分类路由 + Style Card 注入 + humanize 抽样）一次做完。
- 原 ADR「七维<80 自动重写」已更新为「致命维度硬性门禁 + 总分降级参考」。
- **v6.1.1 终版补丁（4 项）**：`entities` 加 `entity_type`+`importance_level`（Context Builder 按重要性加载）；`chapter_summary`+`arc_summary` 双级摘要（第 300 章不爆）；`style_change_confidence`（author_style 需 ≥3 次人工认可才改写，防 AI 自改风格）；`LLMProvider` 抽象接口（DeepSeek-only 但代码不散落 `deepseek.chat()`，未来换模型零改动调用方）。
- **v6.1.2 最终工程补丁（5 项字段级）**：`chapter_snapshot`（锁定快照防历史漂移）/ `fact_confidence`（回写事实 <0.8 仅候选）/ `repair_version`（before/after 对照+二次 review 自动回滚）/ `book_status`（多书状态机）/ `generation_cost_log`（每章 token+cost）。**全部并入后架构真正冻结，不再有 v6.2——后续只做工程实现，不再加模块。**

### 12.1 明确禁止清单（不再讨论）

- ❌ 多 Agent 导演（复杂度提升、收益低）
- ❌ RAG（当前结构化记忆 > 向量，向量仅条件触发）
- ❌ Reader Simulation 定量版（无真实完读率数据，仅保留 P1.5 定性建议）
- ❌ 自动发布（已明确不要）
- ❌ 多模型路由（保持 DeepSeek-only + `LLMProvider` 抽象即可，不建 model_routes）

> 继续设计的边际收益已低于开发验证——真正决定成败的是 Context Builder 稳定性、Story Bible 回写准确性、repair 不破坏正文、DeepSeek 实际生成质量。

---

## 13. Phase 1 开发顺序（单章闭环 MVP 优先，不先写 UI）

用户明确：项目核心是**上下文管理 + 状态回写 + 生成闭环**，不是 UI。开发顺序（微调：单章闭环 MVP 提前，先跑通一章再扩展百万字）：

```
第一步  数据库 Schema（§4.1 全部表 DDL + 迁移，含 🆕book_config/context_package/chapter_audit_report/entity_type/importance/arc_summary/chapter_snapshot/fact_confidence/repair_versions/book_status/generation_cost_log）
  ↓
第二步  Context Builder（Context Assembly Engine：分层装配 + context_package 记账 + 双级摘要加载）
  ↓
第三步  单章完整闭环 MVP（生成→review→repair→保存，先跑通"一章"，不先做百万字）
  ↓
第四步  Story Bible 自动回写（状态/弧线/能力树/世界状态/伏笔 定稿后回写）
  ↓
第五步  滚动规划（自适应窗口重规划 + 伏笔到期窗口）
  ↓
第六步  Style Card（注入 V2 + 每 10 章重学 + author/genre 分离 + style_change_confidence 门控）
  ↓
第七步  复杂审查插件（domain_logic 题材逻辑 10-20 条 + 人工 Checkpoint UI）
```

> 若单章闭环跑不通，后面的都是纸上设计——所以第三步必须最先验证生成→审核→修复→保存的端到端链路。
> 待你确认"开始落地"，我将按此顺序先实现第一步（数据库 Schema），遵循 vibe-coding 小步 + 即时刷新生产约定（提交→推送→CI→SSH 部署→healthz→prod_smoke 14/14）。**架构已封版冻结（v6.1.2），不再新增模块与 v6.2。**
