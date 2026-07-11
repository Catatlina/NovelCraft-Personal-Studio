# NovelCraft Personal Studio —— 架构决策记录（ADR）

> 目的：以标准 ADR 格式固化关键架构决策，作为后续评审/重构/新人对齐的权威留痕。
> 格式：`编号 | 标题 | 状态 | 背景 | 决策 | 理由 | 后果 | 备选方案`
> 状态定义：Proposed（提议）/ Accepted（已采纳）/ Superseded（已被取代，附取代者）/ Rejected（已否决）。
> 配套：《02-架构评审报告》《05-技术实施方案》《16-编码规范》《14-部署与运维手册》。

---

## ADR-001 统一内容模型（Everything is Content）

| 项 | 内容 |
|---|---|
| 编号 | ADR-001 |
| 标题 | 采用统一内容模型：单 `contents` 表 + `type` + JSONB `meta` |
| 状态 | Accepted |
| 关联能力 | C1 |

- **背景**：平台要覆盖小说/短篇/一稿多平台发文/视频脚本等数十种体裁。若每种体裁建独立表，schema 会指数膨胀，且「一稿多平台」的血缘关系难以表达与追溯。
- **决策**：所有内容归一到 `contents` 表：

  ```sql
  contents(
    id, project_id, parent_id,   -- parent_id: 章节属于书、派生稿指向源稿
    type,        -- novel/volume/chapter/short_story/flash_fiction/
                 -- wechat_article/toutiao/xhs_note/zhihu_answer/video_script/...
    title, body, -- body: Tiptap JSON（统一编辑格式，见 ADR-013）
    meta JSONB,  -- 类型专属字段：章节序号/平台标签/SEO标题/封面文案/分镜…
    status, owner_id, created_at, updated_at
  )
  derivations(source_content_id, derived_content_id, workflow_run_id)
  ```

  书籍结构即内容树（novel→volume→chapter 都是 content）；「一稿多平台」= 对同一 source 的 fan-out 派生，血缘存 `derivations` 可追溯。新平台/新体裁 = 新增一个 `type` 枚举 + meta Pydantic Schema + prompt 模板，**零表结构变更**。

- **理由**：极致灵活、血缘统一、扩展零迁移成本；契合「个人+小团队、少运维」定位。内容与版本（ADR-005）、知识（ADR-006 RAG 素材）天然解耦又互通。
- **后果（影响与约束）**：
  - `meta` JSONB 是灵活性来源也是失控来源——每个 type 的 meta 必须有 Pydantic Schema 注册表校验（C1 红线），禁止自由写入（编码规范 §2.3）。
  - 查询需为常用 meta 字段建表达式/函数索引（如 `(parent_id, meta->>'seq')` 唯一索引）。
  - 全文检索用生成列 `tsvector` + GIN 索引，章节按 `(parent_id, meta->>'seq')` 唯一索引。
- **校验方式**：新增 `type` 必须同步注册 `CONTENT_META_REGISTRY`（CI 检查一致性）；meta 写入经 `content_service` 校验（ADR-001 与编码规范三条铁律第三条联动）。
- **备选方案**：① 每体裁独立表（膨胀、血缘割裂，否决）；② EAV 属性表（查询复杂、性能差，否决）。

---

## ADR-002 工作流引擎四节点类型且极简

| 项 | 内容 |
|---|---|
| 编号 | ADR-002 |
| 标题 | 工作流引擎仅四节点类型（agent/human/tool/branch），引擎保持极简 |
| 状态 | Accepted |
| 关联能力 | C2 |

- **背景**：清单要求预设/自定义工作流、节点开关/排序、模型选择、人工确认、暂停/恢复/取消/重试、定时/批量、自动连载、自动发布，能力面很广，但团队规模小、不能养重引擎。
- **决策**：节点类型仅四种——`agent`（调 AI）、`human`（挂起等确认，SSE+通知）、`tool`（抓热点/发布/翻译等确定性操作）、`branch`（按条件分流如质量分<80→返工）。引擎只做 DAG 调度/节点状态机/断点续跑，不内建复杂规则引擎。预设工作流首批八条（长篇章节流水线/黄金三章/短篇爆款/一稿五平台/每日热点晨报/自动连载/出海翻译发布/拆书入库）。

  ```sql
  workflows(id, name, is_preset, definition JSONB)   -- definition: 节点数组(DAG)
  workflow_runs(id, workflow_id, project_id, status, context JSONB, schedule_id)
  run_nodes(id, run_id, node_key, agent, status, input JSONB, output JSONB,
            ai_call_ids, attempt, started_at, finished_at)
  schedules(id, workflow_id, cron, enabled)          -- Celery beat 读取
  ```

- **理由**：极简引擎维护成本恒定，能力由「节点组合 + 预设 YAML」表达，避免自研重引擎。与 ADR-004（多 Agent 显式编排）共同保证可调试。
- **后果（验收红线）**：节点级幂等（重跑不产生脏数据）、run 级断点续跑、human 节点挂起不占用 worker、失败节点单独重试不重跑全链、全部输入输出落 `run_nodes`（与 ADR-003 `ai_calls` 打通）。
- **校验方式**：节点级幂等单测 + 断点续跑集成测试；human 节点挂起时 worker 槽位释放检查。
- **备选方案**：① 引入 Airflow/Temporal 等外部编排（重、需新基础设施，违背单 VPS 红线 ADR-007，否决）；② 仅 agent 一种节点（无法表达人工确认/分支，否决）。

---

## ADR-003 AI Gateway 单一入口 + ai_calls 单表承载全部追踪

| 项 | 内容 |
|---|---|
| 编号 | ADR-003 |
| 标题 | AI Gateway 单一入口；`ai_calls` 单表承载追踪/成本/质量/A-B，Traceable 不是独立系统 |
| 状态 | Accepted |
| 关联能力 | C3 |

- **背景**：需要统一的预算控制、路由降级、Schema 校验、成本统计、模型质量对比、Prompt 实验室回放。若各 agent 自己记日志会数据割裂。
- **决策**：所有 LLM 调用经 `gateway.complete(task_type, prompt_name, variables, output_schema, budget_scope)`：

  1. 预算检查（任务/项目/日三级，Redis 计数）→ 2. 路由（model_routes 表，热更新）→ 3. Prompt 渲染（带 version + model 分支）→ 4. Provider 调用（限流令牌桶、指数退避重试、降级链）→ 5. Schema 校验（失败带错误重试 ≤2）→ 6. 全量落库 `ai_calls`。

  ```sql
  ai_calls(id, run_node_id, agent, task_type, provider, model, prompt_name,
           prompt_version, input JSONB, output JSONB, prompt_tokens,
           completion_tokens, cost, latency_ms, status, error, created_at)
  ```

  这一张表同时支撑 Agent 输入输出记录、成本统计、模型质量对比、A/B 测试数据、Prompt 实验室回放。**Traceable 不是独立系统，是这张表。**

- **理由**：单表即「Traceable」，避免再建独立追踪系统，数据同源、零同步成本。
- **后果**：`ai_calls` 增长最快，按**月分区**；装配结果与丢弃日志随 `input` 落库以支持回放定位「当时模型看到了什么」（呼应 ADR-002 上下文装配 §7 层）。**所有 LLM 调用只准走 gateway（编码规范铁律一，CI grep 守卫）。**
- **校验方式**：`app/` 内 grep 禁止直连 provider；每个 AgentNode ≥1 golden case 写 `ai_calls` 可回放。
- **备选方案**：① 独立追踪/可观测系统（LangSmith 类，需外网/新组件，否决）；② 各 agent 自记日志（数据割裂，否决）。

---

## ADR-004 多 Agent 显式编排、禁自治对话

| 项 | 内容 |
|---|---|
| 编号 | ADR-004 |
| 标题 | 多 Agent 显式编排（AgentNode 契约 + CI 禁互调），禁止自治对话式多 Agent |
| 状态 | Accepted |
| 关联能力 | C3 |

- **背景**：10 个 Agent 若做成自治对话系统会不可调试、不可重放、不可断点（原评审 ⚠️ 项）。
- **决策**：`AgentNode = 角色 SystemPrompt + 任务 Prompt + 工具白名单 + 输出 Schema`，由工作流引擎显式编排（见 ADR-002 DAG）。定案补强：

  1. **Agent 契约固化**：每个 AgentNode 在 `agents/` 下声明 `AgentSpec = {role_prompt, task_prompt_name, tool_whitelist[], input_schema, output_schema, max_retries, budget_scope}`，由 `agent_registry` 统一注册；引擎只能通过 registry 实例化 Agent，禁止 Agent 之间直接互调（CI 静态检查：`agents/**` 不得 import 其它 `agents/**`）。
  2. **Producer 的边界**：Producer 只输出 `WorkflowPlan`（选哪条预设/如何填参/human 节点插入点），产物是**数据**不是控制流；Plan 交给引擎执行，Producer 不参与运行期。Plan 本身进 `ai_calls` 可回放。
  3. **禁自治的机器约束**：工具白名单默认不含「调用其它 Agent」；任何 Agent 想触发另一 Agent，必须由引擎按 DAG 边推进。
  4. **可测试红线**：每个 AgentNode 必须有 ≥1 条 golden case（固定 input → 断言 output schema + 关键字段），进 CI。

- **理由**：可测试、可重放、可断点，从代码层杜绝「自治对话循环」。
- **后果**：新 Agent 必须声明 `AgentSpec` 并注册；引擎只能经 registry 实例化；CI 守卫 `agents/**` 不互 import 必绿方可合入。
- **校验方式**：CI 静态守卫 + golden case 全绿 → 原 ⚠️ 项关闭（见《02》§13.1）。
- **备选方案**：① 自治对话多 Agent（不可调试，否决）；② 单巨型 Agent 包办（失去分工与可重放，否决）。

---

## ADR-005 通用多态版本系统

| 项 | 内容 |
|---|---|
| 编号 | ADR-005 |
| 标题 | 通用多态版本系统：`versions` 表 entity_type + snapshot |
| 状态 | Accepted |
| 关联能力 | C5 |

- **背景**：内容、知识项、prompt、工作流都需版本能力（AI 重写产生分支而非覆盖、可任意节点恢复）。
- **决策**：统一版本表，写路径统一走 `VersionedRepository.save()`：

  ```sql
  versions(id, entity_type,      -- content/knowledge_item/prompt/workflow
           entity_id, version_no, parent_version_id,   -- parent 形成版本树
           snapshot JSONB, reason,                     -- manual/ai_rewrite/auto_save/restore
           author_id, created_at)
  ```

  先快照后更新，任何实体自动获得版本能力；正文类 diff 用文本 diff（diff-match-patch），结构化实体用字段级 diff。「内容版本树」：AI 重写产生分支而非覆盖，编辑器提供树视图 + 任意节点恢复。

- **理由**：一份版本机制服务所有实体，避免每类各建版本表。
- **后果**：auto_save 版本 7 天滚动清理，manual/ai_rewrite 永久；**写操作铁律——只准走 VersionedRepository（编码规范铁律二，CI 守卫）**；与 ADR-008 L2 冲突走版本树三方对比 UI 联动。
- **校验方式**：直 `session.commit` 实体报 warning；版本树恢复集成测试。
- **备选方案**：① 每实体独立版本表（重复实现，否决）；② 仅内容版本化（知识/prompt 失真，否决）。

---

## ADR-006 pgvector 而非独立向量库

| 项 | 内容 |
|---|---|
| 编号 | ADR-006 |
| 标题 | 使用 pgvector，不引入独立向量数据库 |
| 状态 | Accepted |
| 关联能力 | 基础设施 / C4 |

- **背景**：Knowledge Hub 需要向量检索（RAG、风格卡、7 层上下文装配素材层）。
- **决策**：`knowledge_vectors(item_id, chunk_no, embedding vector, chunk_text)` 用 pgvector + HNSW 索引，与业务数据同库；embedding 维度在 config 固化（换模型需迁移，明示）。

- **理由**：单一事实源、少运维、事务一致（知识与向量同生同灭），契合单 VPS 定位（ADR-007）。
- **后果**：换 embedding 模型需迁移并重建向量（同步文档说明）；pg 同时承载向量+事务，资源需规划（4C8G 基线够用，见部署手册 §9 资源分配）。
- **校验方式**：HNSW 索引创建迁移可重复执行；维度变更走显式迁移。
- **备选方案**：① 独立向量库（Milvus/Weaviate/Qdrant，需新基础设施与同步，违背红线，否决）；② 仅全文检索（无语义召回，否决）。

---

## ADR-007 单 VPS + Docker Compose 而非 K8s/微服务

| 项 | 内容 |
|---|---|
| 编号 | ADR-007 |
| 标题 | 单 VPS + Docker Compose 部署，不引入 K8s / 微服务 |
| 状态 | Accepted |
| 关联能力 | 部署 |

- **背景**：用户规模 1~5 人，需低成本、可自托管、可独立部署。
- **决策**：单 VPS（4C8G 起步）跑 nginx/api/5×worker/beat/postgres/redis，全部 Docker Compose 编排；工作流引擎/发布网关/Knowledge Hub 全为 FastAPI 进程内模块 + Celery 任务。compose 服务：nginx/api/worker-plan/worker-generate/worker-review/worker-publish/worker-system/beat/postgres(pgvector)/redis。

- **理由**：运维成本恒定、规模匹配、无新基础设施组件；垂直扩容优先，generate worker 必要时可拆第二 VPS 但仍是同 Redis/Postgres。
- **后果**：不引入 K8s/服务网格；扩容以垂直为主、generate 水平拆分为唯一例外（部署手册 §9）；所有进程同 `nc_net` 网络，仅 nginx 暴露 80/443。
- **校验方式**：compose healthcheck 全绿；资源限制内压测 generate 队列。
- **备选方案**：① K8s（运维过载，否决）；② 微服务拆分（网络/部署复杂度激增，否决）。

---

## ADR-008 Offline First 分三级 L1/L2/L3，不做 CRDT/自动合并

| 项 | 内容 |
|---|---|
| 编号 | ADR-008 |
| 标题 | Offline First 严格限定 L1 只读 / L2 离线编辑 / L3 AI 出站队列，不做 CRDT/自动合并 |
| 状态 | Accepted |
| 关联能力 | C9 / 前端 |

- **背景**：创作者需要断网可浏览、可编辑、可排队 AI 任务（原评审 ⚠️ 分级采纳项）。「全功能离线」会拖入本地库同步冲突深水区。
- **决策**：

  | 级别 | 能力 | 技术实现 | 冲突策略 |
  |---|---|---|---|
  | L1 只读 | 项目树/章节/人物/知识/版本可浏览、可搜索 | SW（stale-while-revalidate）+ IndexedDB | 无写入，无冲突 |
  | L2 离线编辑 | 断网可编辑并本地暂存，恢复网络自动提交 | IndexedDB 草稿 + `base_version_id` 乐观锁 | 服务端版本已变 → 生成分支进版本树，弹**三方对比 UI**由人选择，绝不静默覆盖 |
  | L3 AI 出站队列 | 离线创建的 AI 任务排队，恢复后按序自动执行 | `outbox` 队列（IndexedDB）+ 恢复网络后重放，幂等键防重复 | 依赖服务端 run 级幂等（ADR-002/005）保证不重复扣费 |

- **理由**：覆盖真实离线诉求，同时避免本地库同步冲突深水区。
- **后果**：明确**不做** CRDT/OT 实时协同、不做离线自动三方合并、不承诺全功能离线；冲突必弹三方对比 UI。与 ADR-005 版本树天然配合。
- **校验方式**：断网可浏览+搜索+编辑并排队 AI 任务；恢复后草稿自动提交、出站任务不重复扣费；并发冲突必弹三方对比（红线验收，见《02》§9）。
- **备选方案**：① 全功能离线 + CRDT 自动合并（拖入协同深水区，否决）；② 不做离线（违背创作者诉求，否决）。

---

## ADR-009 自动发布三模式，国内全自动强约束

| 项 | 内容 |
|---|---|
| 编号 | ADR-009 |
| 标题 | 自动发布三模式（手动/半自动/全自动），国内平台全自动强约束 |
| 状态 | Accepted |
| 关联能力 | C7 |

- **背景**：国内平台自动化发布违反 ToS、有封号风险（原评审 ⚠️ 项）。
- **决策**：发布适配器 `PublisherAdapter(format/publish/fetch_metrics)`，每平台一个 adapter。三模式：

  | 模式 | 适用平台 | 触发 | 风险控制 |
  |---|---|---|---|
  | 手动 | 全部 | 排版 + 一键复制，人工去平台粘贴 | 零自动化风险 |
  | 半自动（默认） | 公众号/头条/小红书/知乎/百家/大鱼/网易 | Playwright 填充内容，**人点最终发布按钮** | 不代替人做发布动作 |
  | 全自动 | 仅官方 API：Medium/Substack/X/WordPress | 系统直接调官方 API | 官方授权，合规 |

  国内全自动强约束：① 默认关闭，开启需设置页勾选知悉 + 二次确认弹窗（写 audit_logs）；② 全自动工作流在发布 tool 节点前**强制插入 human 确认节点**（首篇必确认）；③ 每次全自动发布落 publish_records 附风险提示，连续失败自动降级半自动并告警。

- **理由**：在合规与自动化间取平衡，把风险控制在人可干预范围内。
- **后果**：发布前强制过内容安全过滤（敏感词 + 平台规则 + ADR-010 仿写相似度标记）；未开启时路径只能停半自动待点击态（红线验收）。
- **校验方式**：未开启时路径只落半自动待点击态；开启后首篇仍出现 human 确认节点（见《02》§13.2）。
- **备选方案**：① 国内全平台全自动（封号风险不可接受，否决）；② 只做手动（丧失自动化价值，否决）。

---

## ADR-010 风格仿写三道防侵权闸 + 相似度阈值

| 项 | 内容 |
|---|---|
| 编号 | ADR-010 |
| 标题 | 风格仿写三道防侵权闸（入库/生成/产物）+ 相似度阈值 |
| 状态 | Accepted |
| 关联能力 | C4 |

- **背景**：仿写可能过拟合到侵权级模仿（原评审 ⚠️ 项）。
- **决策**：三道闸——
  1. **入库闸**：样本记 `source_type`（原创/授权/公共领域/第三方）与授权声明；第三方受版权保护样本只抽统计特征（句长/词频/节奏），禁整段原文进 style_card 可注入字段。
  2. **生成闸**：`sim = max(向量余弦, 归一化 5-gram 重合率)`；`sim ≥ 0.75` 强制重写（≤2 轮），`0.6 ≤ sim < 0.75` 标高风险 + human 确认，`sim < 0.6` 放行。阈值写 config 可调，检测记录落 `ai_calls.meta`。
  3. **产物闸**：任何进入发布网关的仿写产物必须携带「相似度检测通过」标记，否则发布网关拒绝（与 ADR-009 内容安全过滤同一拦截点）。

- **理由**：从数据、生成、发布三段兜底，满足可验收防侵权红线。
- **后果**：必须构造高相似输入验证拦截与重写至阈值以下方可验收；阈值调整需人工确认（走 PR 清单，编码规范 §5.4）。
- **校验方式**：高相似输入被拦截并重写至阈值以下（红线验收，见《02》§13.4）。
- **备选方案**：① 完全禁止仿写（丧失风格学习价值，否决）；② 无闸自由仿写（侵权风险，否决）。

---

## ADR-011 在 V1 仓库上演进重构（禁另起炉灶）+ V1 收口为迁移前置门禁

| 项 | 内容 |
|---|---|
| 编号 | ADR-011 |
| 标题 | 在 V1 仓库演进重构（禁止另起炉灶）；V1 收口列为 C1 数据迁移硬前置门禁 |
| 状态 | Accepted |
| 关联能力 | 工程基线 |

- **背景**：需先收口 V1 至 80 分再动 C1 迁移，否则在不稳定基座上重构（原评审 ⚠️ 有条件项）。
- **决策**：**禁止另起炉灶**新建仓库；在 V1 仓库上演进。V1 收口任务（TASK-001/002：106 测试全绿 + slowapi 定型 + Celery retry/死信 + 备份告警实收）列为 M1 首两任务，并设为 C1 数据迁移（TASK-004）的**硬前置门禁**——门禁项全绿才允许执行迁移；迁移脚本自带前置备份与可回滚（呼应 ADR-012 里程碑门禁）。

- **理由**：保护既有资产、降低风险、保证迁移基座稳定。
- **后果**：迁移 PR 的 CI 中 V1 收口门禁项必须全绿方允许合入；迁移独立 commit、可降级（编码规范 §4.3）。
- **校验方式**：迁移 PR CI 中 V1 收口门禁全绿 → 原 ⚠️ 项关闭（见《02》§13.5）。
- **备选方案**：① 新建 V2 仓库重写（资产丢失/双线维护，否决）；② 不收口直接迁移（基座不稳，否决）。

---

## ADR-012 里程碑门禁制（M(n) 未验收不开 M(n+1)）

| 项 | 内容 |
|---|---|
| 编号 | ADR-012 |
| 标题 | 里程碑门禁制：M(n) 未验收不得开启 M(n+1) |
| 状态 | Accepted |
| 关联能力 | 工程基线 |

- **背景**：功能清单庞大，需防止半成品堆叠导致集成失控。
- **决策**：里程碑 M1~M5 串行门禁——上一里程碑验收（含测试/UI 五条/文档）通过，方可开启下一里程碑开发；发版加备份恢复演练 + 30 分钟探索测试 + 全功能映射表勾验（M5）+ 报告归档 `docs/reports/`。

- **理由**：保证每个阶段可交付、可验收、可追溯。
- **后果**：任何「提前开工下一里程碑」需显式豁免并记录；验收标准写入 Issue 逐项勾选后关闭（编码规范 §5）。与 ADR-011 的迁移门禁形成双层守卫。
- **校验方式**：M(n) 验收报告归档后方可建 M(n+1) 任务。
- **备选方案**：① 全功能并行开发（集成风险高，否决）；② 无门禁自由排期（半成品堆积，否决）。

---

## ADR-013 Tiptap JSON 统一内容格式

| 项 | 内容 |
|---|---|
| 编号 | ADR-013 |
| 标题 | 正文统一 Tiptap JSON 作为唯一内容格式，派生输出按需序列化 |
| 状态 | Accepted |
| 关联能力 | C1 / C7 |

- **背景**：多平台发布需要 MD/HTML/纯文本等不同格式，若各存各的格式会丢失结构与可编辑性，且版本 diff 困难。
- **决策**：`contents.body` 统一存 Tiptap JSON；派生平台输出（公众号 MD、头条 HTML、X 纯文本等）在 content_service / 发布 adapter 中按平台序列化，源头只有一份结构化正文。

  ```ts
  // 统一格式示例（Tiptap JSON）
  { type: "doc", content: [
    { type: "heading", attrs: { level: 1 }, content: [{ type: "text", text: "第一章" }] },
    { type: "paragraph", content: [{ type: "text", text: "正文…" }] }
  ] }
  ```

- **理由**：单一真相、可编辑、可 diff/版本化（与 ADR-001/005 天然契合）；编辑器扩展（AI 浮条/行内批注/版本树/diff）只消费此格式。
- **后果**：跨平台转换逻辑集中，禁止数据库存 Markdown 原文当正文（编码规范反模式）；发布 adapter 的 `format()` 负责序列化。
- **校验方式**：入库校验 body 为合法 Tiptap doc；序列化单测覆盖各平台。
- **备选方案**：① 存 Markdown 原文（丢失结构/不可精细 diff，否决）；② 每平台各存一份（冗余且易失同步，否决）。

---

## ADR-014 Celery 五队列划分 + model_routes 热更新降级链

| 项 | 内容 |
|---|---|
| 编号 | ADR-014 |
| 标题 | Celery 五队列（plan/generate/review/publish/system）+ model_routes Redis 热更新降级链 |
| 状态 | Accepted |
| 关联能力 | 部署 / AI |

- **背景**：不同任务负载差异巨大（generate 最重、publish IO 密集、system 后台），且 provider 会限流/降级，需在不发版情况下切换路由。
- **决策**：五队列隔离，worker 按队列独立部署与扩缩：

  ```yaml
  worker-plan:     celery -Q plan -c 2
  worker-generate: celery -Q generate -c ${GENERATE_CONCURRENCY}   # = min(provider RPM)
  worker-review:   celery -Q review -c 2
  worker-publish:  celery -Q publish -c 2
  worker-system:   celery -Q system -c 2
  ```

  路由存 `model_routes`（task_type→[primary, fallbacks]），Redis 缓存**热更新**（改 DB 清缓存即生效，无需发版）。降级链：主 429/5xx/超时 → 依序备胎 → 全败则 run_node 置 `PENDING_PROVIDER` 并告警，恢复后自动重试（**不是 FAILED**）。各 provider 独立令牌桶限流（Redis）防 429 雪崩。

- **理由**：队列隔离防互相拖累；热更新降级链让 provider 故障可在不发版情况下切换，保障可用性。
- **后果**：`generate worker` 并发 = `min(各 provider RPM)`（部署手册 §9.1）；`PENDING_PROVIDER` 状态需前端/告警识别（部署手册 §8.3）。与 ADR-003 gateway 降级链、ADR-007 单 VPS 协同。
- **校验方式**：主失败→备→PENDING_PROVIDER 降级链集成测试；清 Redis 缓存后路由即时生效验证。
- **备选方案**：① 单队列混跑（generate 阻塞 review/publish，否决）；② 路由写死在代码（故障需发版，否决）。

---

## ADR-015 V2.2 产品主轴与开源融合边界

| 项 | 内容 |
|---|---|
| 编号 | ADR-015 |
| 标题 | 扫榜成书与热点生产为主轴；全部小说统一入库 |
| 状态 | Accepted |
| 关联能力 | C1/C2/C3/C4/C6 |

- **背景**：旧实现以灵感向导和零散生成能力为可见入口，模块虽多，却没有交付用户真正需要的扫榜成书闭环；进度百分比因此失真。
- **决策**：小说主链固定为“榜单采集→快照→分析→原创选题→8 节点全自动成书→统一书库”；自媒体主链固定为“热点→多平台内容”。灵感生成仅为兼容入口，且与其他来源一样自动进入书库。工作流借鉴 denova 的持久计划/事件/检查点语义，长篇一致性借鉴 show-me-the-story，Prompt 与去 AI 规则借鉴 oh-story-claudecode；其余三项目按《19》许可证策略研究。
- **理由**：以端到端用户结果代替孤立功能数量，并在利用开源经验时保留可追踪来源和许可证边界。
- **后果**：前端第一入口、API、数据模型、任务优先级和验收用例均以两条主链排序；旧“86%”作废。采集失败不可静默；所有生成必须记录 `source_type/source_ref_id/workflow_run_id`。
- **校验方式**：E2E-RANK、E2E-LIB、E2E-AUTO、E2E-HOT、E2E-OSS 与 Prompt 回归门禁全部通过。
- **备选方案**：继续以灵感向导为主入口（不符合最终需求，否决）；仅拼接上游代码（不可维护且有许可证风险，否决）。

---

## 决策索引

| 编号 | 标题 | 关联能力 | 状态 |
|---|---|---|---|
| ADR-001 | 统一内容模型 | C1 | Accepted |
| ADR-002 | 四节点极简引擎 | C2 | Accepted |
| ADR-003 | Gateway + ai_calls 单表 | C3 | Accepted |
| ADR-004 | 多 Agent 显式编排 | C3 | Accepted |
| ADR-005 | 通用多态版本系统 | C5 | Accepted |
| ADR-006 | pgvector 单库 | 基础设施 | Accepted |
| ADR-007 | 单 VPS + Compose | 部署 | Accepted |
| ADR-008 | Offline First 三级 | C9/前端 | Accepted |
| ADR-009 | 自动发布三模式 | C7 | Accepted |
| ADR-010 | 仿写三道防侵权闸 | C4 | Accepted |
| ADR-011 | V1 演进 + 收口门禁 | 工程基线 | Accepted |
| ADR-012 | 里程碑门禁制 | 工程基线 | Accepted |
| ADR-013 | Tiptap JSON 统一格式 | C1/C7 | Accepted |
| ADR-014 | 五队列 + 热更新降级链 | 部署/AI | Accepted |
| ADR-015 | V2.2 产品主轴与开源融合边界 | C1/C2/C3/C4/C6 | Accepted |

## 决策回顾与演进机制

- **提出**：任何「影响架构边界」的改动（新增基础设施、改内容模型、改发布模式、改离线策略等）必须先提 ADR（Proposed），在 PR/评审中讨论。
- **采纳**：评审通过转 Accepted，方可落地代码；落地后同步更新《05-技术实施方案》《02-架构评审报告》相关章节与编码规范（如有守卫变化）。
- **取代**：当新决策推翻旧决策，旧 ADR 标记 Superseded 并注明取代者编号（如 `Superseded by ADR-0xx`）；代码与文档引用统一指向新 ADR。
- **复盘节奏**：每季度结合备份恢复演练与 VPS 切换演练，复查 ADR 是否仍成立（尤其 ADR-006 向量库、ADR-007 单 VPS 是否需升级）。
- **与评审报告对齐**：本册 ADR-001~ADR-012 的「校验方式」列与《02-架构评审报告》§13 五条 ⚠️→✅ 关闭条件一一对应，是验收留痕的权威索引。

## 附录：新 ADR 模板（复制新建）

```markdown
## ADR-0xx 标题

| 项 | 内容 |
|---|---|
| 编号 | ADR-0xx |
| 标题 | 一句话决策标题 |
| 状态 | Proposed / Accepted / Superseded / Rejected |
| 关联能力 | Cx / 基础设施 / 部署 / 工程基线 |

- **背景**：为什么现在要做这个决策？面临什么约束或问题？
- **决策**：具体怎么做（可附表/SQL/配置片段）。
- **理由**：为什么选它，放弃了什么。
- **后果**：带来哪些约束、影响范围、需要哪些守卫/校验。
- **校验方式**：如何验证决策被遵守（CI/测试/红线）。
- **备选方案**：列出被否决的替代方案及否决原因。
```

> 新 ADR 编号接续最大编号递增；状态初提为 Proposed，评审通过转 Accepted 并更新决策索引表。

> 当某 ADR 被取代时，在此表标注 Superseded 并链接取代者。任何架构变更须先提 ADR（Proposed），评审通过转 Accepted，再落地代码。ADR 与《02-架构评审报告》§13 遗留项关闭条件一一对应。
