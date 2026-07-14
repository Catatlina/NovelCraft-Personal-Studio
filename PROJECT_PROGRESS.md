# NovelCraft Personal Studio — 真实进度

<!-- delivery-claims: strict -->

> 更新：2026-07-11（审计修复轮）｜ 权威摘要 ｜ 状态遵循《23-AI开发边界与交付真实性规范》
>
> **治理说明**：此前版本宣称"20/20 任务全部完成、6/6 深度融合、8/8 整合、真实 Provider T3/T5 通过、真实源 7 天稳定运行、浏览器 E2E 验收通过"，均无《23》§6 要求的验收证据（commit/命令/日期/输出），且"7 天 T5"与文档同日更新在时间上不可能成立。按《23》§8 全部降级为证据可查的状态；重建证据台账前不得恢复 ✅。外部审计报告（2026-07-11）的 §三/P1-6 亦指认了同一问题。
>
> **开发前强制门禁**：任何后续开发、整改、审计修复、提交前，必须先阅读并遵守 `docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md`。未通过该规范的状态口径、反撒谎扫描、证据等级和交付格式时，不得使用高等级交付口径。

## 当前主线 (main)

### 2026-07-14 待验收推进轮证据（部分完成/骨架 → 待验收）

按《24》顺序推进，每模块独立提交并绑定测试证据；全部状态最高为 🧪 待验收，未标任何 ✅：

- **NC-LIB-002/003（@9d1786f）**：`/library/books` 服务端检索(q)/状态筛选/白名单排序（含 SQL 注入回退负例）；前端「最近编辑」排序；编辑器 3s 防抖自动保存（脏检查、冲突处理期间暂停）。`test_library_contract.py` 2 passed。
- **NC-HM-001/002/003（@9d1786f）**：hm_content 4 个真实 AI 函数首次获得产品入口（platform-match/title-variants/video-script/material-suggestions + Dashboard 选题工具箱）；去重/趋势/时效评分与可恢复工作流回归。`test_hm_media_pipeline.py` 7 passed。
- **长篇一致性（@7481791）**：卷级门禁 + 批量生成 409 enforcement + 百章真库压力 + 摘要失败显式化。`test_long_novel_consistency.py` 7 passed。
- **发布中心（@df778e4）**：指标回流 sweep（beat 6h）+ 状态机/60s 调度行为测试。`test_publish_center.py` 4 passed。
- **融合与骨架项目（@4a27eb9）**：事件账本/事实链负载修复与产品端点、事实事务接入真实 reconcile、分层规划/审计/humanize/insprira/BrowserAct removed 诚信回归。`test_skeleton_fusion_projects.py` 5 passed + `test_fusion_deep.py` 行为对照补强。
- **诚信机器门禁（本轮）**：新增 AST 级 `scripts/verify_ai_truthfulness.py` 并接入 `scripts/ai_development_gate.sh` 与 GitHub Actions；拦截 AI 命名函数绕过 gateway、硬编码 `wired/available/status=active`、固定伪生成模板。新增 `test_truthfulness_gate.py` 负例，确认坏代码会被挡下。
- **融合状态证据驱动（本轮）**：`/fusion/status` 的能力状态由当前用户项目最近 30 天 `ai_calls` / workflow audit evidence 倒推：`verified` / `wired_unverified` / `missing` / `removed`；没有真实成功记录不再计入 verified。新增回归断言 `book_analysis` 成功记录可把 book analyzer 从 `wired_unverified` 升为 `verified`。
- 验证命令：`cd backend && .venv/bin/pytest -q` → **523 passed, 8 skipped**（2026-07-14）；`python3 scripts/verify_ai_truthfulness.py` → passed；`GATE_ALLOW_WARNINGS=1 bash scripts/ai_development_gate.sh` → AST truthfulness passed，旧宽泛扫描仍需逐项解释。

### 2026-07-14 本轮整改证据

- P0 成本追踪白屏：已改为读取 `/api/v1/admin/budgets` 与 `/api/v1/admin/model-routes` 的 `response.data`，组件侧增加数组保护；证据：`npm --prefix frontend run test:e2e` 通过，含 `主链①d：成本追踪页无白屏并展示预算与模型路由`。
- P1 自媒体生成真实 AI 化：`hm_content` 的文章、标题、短视频脚本、素材建议均走 `app.gateway.complete()`；新增/补齐 `gen_daily_brief`、`hm_daily_brief`、`hm_title_variants`、`gen_video_script`、`hm_material_suggestions` 输出契约；失败按网关错误暴露，不返回模板成品。
- P1 融合状态诚信：`fusion_governance` 不再硬编码 active；`BrowserAct.chrome_publish` 明确为 removed；`fusion.py` 中 Deep Workflow / Deep Book 状态按真实导入与替代模块可调用性计算。
- P2 embedding：remote/local 失败不再静默切 hash；hash 仅允许测试/显式离线开发模式，产品路径缺少语义后端会直接报错。
- 验证命令：
  - `cd backend && .venv/bin/pytest -q` → `493 passed, 8 skipped`
  - `npm --prefix frontend run build` → passed
  - `set -a; source .env.local; set +a; npm --prefix frontend run test:e2e` → `5 passed`（含真实 DeepSeek 主链②）
  - `bash scripts/ai_development_gate.sh` → 关键项通过；剩余宽泛警告为 UI placeholder、`fallback_json` 历史字段名、空集合自然返回等，不能作为完成声明证据，交付时需继续说明。

| 能力 | 状态 | 已有证据 | 尚未覆盖 |
|---|---|---|---|
| 榜单采集 adapter | 🧪 待验收 | 纵横官方页真实采集 T3；番茄/起点失败显式化；导入/校验/置信度门禁有真库测试 | 番茄 OCR 与起点用户会话复验；真实源长周期 T5 |
| 榜单中心 | 🧪 待验收 | 扫榜、快照、分析、选题、成书前后端入口；导入与元数据校验 UI | 真实 AI 分析 T3、完整 E2E |
| 原创市场选题 | 🧪 待验收 | Gateway、严格 Schema、防注入、Provider 失败直接 `failed`/HTTP 错误契约测试 | 真实 Provider T3 输出证据 |
| 扫榜自动建书 | 🧪 待验收 | 幂等键建书、来源血缘、跳过人工选名 | 真实 Provider 批次成功路径 |
| 连续章节流水线 | 🧪 待验收 | 严格 Schema、章节幂等键、连续性风险报告、批次 `failed`/resume 断点续跑；浏览器实测失败→恢复链与导出正文 | 真实 Provider 多章样本与批次成功路径 |
| 统一书库 | 🧪 待验收 | 书库 API/页面、检索/筛选/排序、目录导入（权限+seq+幂等落库）、导出 TXT/MD | 完整 E2E 验收 |
| 灵感 Bootstrap | 🧪 待验收 | 灵感→书名→设定→第一章→审核基础链；真实 Provider V2 全链 `test_real_provider_v2_bootstrap.py` 已跑通（2026-07-14） | 产出质量人工验收 |
| 热点自媒体 | 🧪 待验收 | 采集器去重(24h窗口)/趋势/时效评分 + 趋势报告端点；平台匹配/受众/合规风险、AI 标题变体/短视频脚本/素材建议 4 新端点+Dashboard 选题工具箱；批次失败回滚零残留→重试幂等键复用（`test_hm_media_pipeline.py` 7 tests，@9d1786f） | 真实源长周期稳定性；真实 Provider 成稿质量验收 |
| 长篇一致性 | 🧪 待验收 | 真库百章写前检索窗口(<5s)、写后 reconcile 接线+新实体标记、卷级门禁（缺章/未过审/到期伏笔/实体矛盾4类阻断，批量生成 409 enforcement，通过时生成卷摘要落库）；摘要 AI 失败显式化不再落伪摘要（`test_long_novel_consistency.py` 7 tests，@7481791） | 真实 Provider 百章 T5 长跑 |
| 发布中心 | 🧪 待验收 | Fernet 凭据、状态机全生命周期+非法迁移拒绝、beat 60s 到期派发+6h 指标回流 sweep（只聚合真实采集数据）（`test_publish_center.py` 4 tests，@df778e4） | 真实平台发布回执与真实回流数据（需有效平台凭据） |

## 八上游项目融合

| 项目 | 状态 | 真实边界 |
|---|---|---|
| oh-story-claudecode | 🧪 待验收 | 7 上游 Skill+许可证在库；PromptSpec/golden cases 播种并有汇总校验（`test_fusion_deep.py` golden case 断言、`/batch` golden-case 检查端点）；write_chapter_draft/final_humanize 绑定方法论提示词（`test_fusion_wired.py`） |
| denova | 🧪 待验收 | 事件账本行为对照测试（负载 roundtrip、非法事件类型拒绝、detail/details 键名错位回归修复）；run 账本查询端点 `/runs/{id}/ledger`；workflow plan 由 config+dag_exec 产品链承担，无调用的 WorkflowPlan 助手类已删（@4a27eb9） |
| show-me-the-story | 🧪 待验收 | 章节事实事务链接入真实 reconcile 落库路径（每次 reconcile 写可回溯事务），查询端点 `/contents/{id}/fact-chain`，roundtrip 测试钉住 previous/new 负载（@4a27eb9） |
| AI_NovelGenerator | 🧪 待验收 | 目录解析/四阶段20节点全链 T2；真库百章检索窗口与一致性组件回归（`test_long_novel_consistency.py`）；真实 Provider 百章 T5 未做 |
| AI-auto-generates | 🧪 待验收 | 批量生成批次幂等恢复、书本分析真实 Gateway（`/books/analyze` 写 ai_calls）、章节目录导入落库均有回归 |
| harnessNovel | 🧪 待验收 | 分层规划 `/novels/layered-plan` 走真实网关（空响应显式失败）；合理性审计/humanize 由 bootstrap 末段节点承担且次序钉死（`test_skeleton_fusion_projects.py`，@4a27eb9） |
| BrowserAct (MIT) | 🧪 待验收（合规缩减版） | 按《25》仅保留用户已登录会话半自动发布包装；anti-bot 已删除，fusion 状态如实上报 removed（有回归测试钉死） |
| insprira (AGPL 洁净室) | 🧪 待验收 | 账号追踪幂等 + 真库诊断计算（发帖数/互动均值/redfox 指数/评级）、违禁词三类命中与洁净放行回归；check-compliance 改 JSON body；真实平台数据验收仍需真实账号 |

## 验证基线（2026-07-14 本轮工作树实测）

- 后端测试：**519 passed，8 skipped**（2026-07-14 待验收推进轮后，本地真实 DeepSeek key；真实 Postgres；业务运行时不再提供 mock provider）。新增覆盖：仿写相似度红线、热点生成持久化/回滚、书库正式路径、出海翻译项目归属、平台连接可视化配置、审计报告 P0/P1 整改（伪热点下线、书本分析真实网关、预算真实同步、发布读取存储凭据、融合 removed 状态、Provider 诊断失败语义、移动端响应式/env 示例）、真实编辑器/热点/仿写 Provider 冒烟。
- 前端：`npm run build` 通过（仅保留 Vite 关于 `api.ts` 动静态混合导入和空 `react` chunk 的既有警告）。
- Alembic：单头 `nc_audit_workflow_scope`；本地库 upgrade→downgrade→upgrade 往返通过。
- 浏览器实测（上一轮）：审阅页时间线/人物弧线渲染真实数据；设置页数据统计为真实计数（AI 调用/内容数/pg_database_size）。当前整改要求 AI provider 失败直接失败/报错，不再把 provider 失败作为可伪恢复的成功态。
- **真实 Provider T3/V2/新增功能（2026-07-14，deepseek-chat）**：本地开发 key 仅保存在 `.env.local`（Git 忽略）。`test_real_provider_t3.py`、`test_real_provider_v2_bootstrap.py`、`test_real_provider_new_features.py` 均已跑通。新增功能真实冒烟覆盖：编辑器整章重写→七维评分→下一章规划、热点生成公众号草稿落库、仿写生成原创样稿并返回相似度报告。
- **浏览器自动化 E2E（2026-07-14 复验）**：Playwright `npm run test:e2e` 实测 **4 passed, 26.2s**。用例①注册→CSV 导入→快照落库→刷新持久→书库空态；用例②书库详情页可进入并展示简介/最新章节/全部章节；用例③平台连接可视化填写、加密保存、不回显密钥；用例④真实 AI 分析→原创选题→建书→书库可见。
- **审计报告整改（2026-07-14，commit 后工作树）**：针对《审计报告_NovelCraft_2026-07-14.md》新增 `tests/test_audit_report_remediation_20260714.py`，9 条专项回归通过；受影响老回归 77 条通过。`knowledge/daily-briefing` 仅消费真实采集/已采集热点，不再由 AI 编造当前热点；`/books/analyze` 改为真实 Gateway `book_analysis` 并写 ai_calls；worker `_track_budget` 由 ai_calls 重算并同步 budgets；发布 worker/一次性发布读取 Fernet 存储凭据；BrowserAct.chrome_publish 标 removed；移动端媒体查询改为真实 `.layout`；`.env.example` 补齐凭据/DB/Redis/Provider/热点/告警配置。
- T5 长周期运行：仍无证据，未验收。

## 审计对照（外部审计报告 2026-07-11）

- 已修复（`efba333`）：B1 JWT 生产强校验、B2 管理员绕过收口、B4 裸 fetch 清除、P0-1 DB.close 改 rollback、P0-2 SSE 真换行、P1-4 死组件接线。
- 已修复（本轮）：B3 发布凭据 Fernet 加密落库（`platform_accounts` 启用，响应不回显凭据）；P0-3 compose api/worker 依赖 migrate 完成；P1-1 修复 3 条静默失败索引（错误列名，原迁移 `except: pass` 吞错）；Redis appendonly + 持久卷（更正：`7053a07` 提交信息声称 "Redis persistence" 但未实际配置，属《23》§4 虚假上报，本轮补齐）；F5 设置页假统计→真实 `/stats/overview`；F7 审阅页恒空时间线/弧线→真实 `/novels/{id}/narrative`；F8 敏感词前端空函数→真实 `/contents/{id}/check-sensitive` 并接入发布前置检查；F12 DagEditor 空 project_id→真实项目 ID 且缺失时拒绝保存。
- 已修复（第二轮，对照审计全量版 §六）：多轮审核/跨模型审计/Prompt 矩阵此前用字符串长度公式伪造评分并宣称"ready"，现真实经 Gateway 调用、Provider 不可用逐项 `failed`，端点补 `project_id` 成员校验；热点采集 `except: continue` 静默空成功改为逐源状态+全失败 502；AgentConsole 硬编码"模拟"数据改为 `/agents/status` 真实 run_nodes 聚合；Collaboration 页面调用不存在的路径（必 404）改为真实 `/collaboration/*`；`/admin/workflows/{name}/execute` 此前无视工作流名一律跑 bootstrap 且 `project_id=''` 必然崩溃，改为权限校验+仅 bootstrap 可执行+其余显式 501；AI 编辑补 `ai_edit` 版本分支（C5-03）；C5-05 自动保存 7 天保留 beat 任务（保留每实体最近 10 份，语义分支永不清理）；assembler 知识层此前按无人写入的列过滤永远为空，改为按小说前提走 Knowledge Hub 检索。
- 已修复（第三轮，代码/文档/功能契约对账）：工作流保存请求原本必 422 且代码引用不存在的 `workflows.project_id/config`，现新增项目作用域迁移并统一使用 `definition`；系统 Bootstrap 只读，自定义 DAG 明确为设计稿、未接执行器返回 501；清除预算/日报/翻译四组重复路由及其中的跨项目翻译风险；设置页知识导入/导出与预算、知识检索、热点响应、Fanout 响应、多平台发布均对齐真实 API；短篇输入真实落库；Fanout Provider 失败不再复制原文冒充改写成功。
- 已修复（第四轮，按《27-全仓库审计报告》路线图阶段 0）：P1-A 迁移回滚断裂——性能索引 downgrade 移除 CONCURRENTLY，干净库 upgrade→downgrade base→upgrade 三段实测通过，并加全迁移源码契约测试；P1-B schema 快照契约测试（12 张核心表必需列钉死，防列名漂移复发）；P1-G 交付门禁升级为证据绑定校验（✅/已交付行必须含测试/commit/文件/T级标记，含负例测试）；P1-D 不可信外部文本统一清洗 `sanitize_untrusted`（接入 assembler 知识召回与热点晨报入模路径）；P1-E 备份 pg_dump 每日 sidecar + 7 份保留 + 全服务日志轮转（compose，YAML 校验通过）；P2 清理：PublishPage 死组件删除、`store_ranking_snapshot` 吞错死函数及其 T0 存在性断言删除、bundle 分包（主 chunk 702KB→281KB，消除 >500KB 警告）、版本统一（app `2.2.0` 对齐需求基线 V2.2，README 刷新）。**396 tests 全绿**。
- 已修复（第五轮，本轮审查）：纯文本编辑增加 DeepSeek SSE、完成后统一写 ai_calls/版本；流式鉴权支持 token 刷新，预算与 Provider 错误分流，非 DeepSeek 路由安全回退普通网关；Embedding 增加 remote/local/hash 三层适配、来源标记和项目重建，远端部分/非法响应回退 hash，不同后端向量禁止混算；Sentry/Prometheus 可选接线，巡检增加队列积压和成本日报。代码验证 417 passed、前端 build；真实流式 Provider、local semantic 和 Sentry 送达仍未作为验收证据。
- 全面复核（2026-07-12 第二轮，@068a45d）：PR#4 加固复核通过（流式 PENDING_BUDGET 语义/非 deepseek 显式拒绝/embedding 数量与有限性校验/检索按 provenance 过滤）；T5 提交内的一致性组件修复复核通过——entity/summarizer/timeline 此前把 AI 调用记账到 `SELECT id FROM projects LIMIT 1` 的**任意项目**（跨项目成本/预算污染），已改为按 content 归属项目；伏笔抽取 `hint_chapter` 字段对齐 prompt 契约；章节富化失败不再阻断落库与审核门禁。新增实测验收：**流式端到端真实 Provider 通过**（HTTP SSE 经 8100 API，逐字增量帧+done 帧，DeepSeek 真实调用）；**local 语义质量验收通过**（EMBEDDING_SEMANTIC_TEST=1，bge-small-zh 真实模型："地底嗡鸣"≈"深渊低语"≫无关文本，余弦差 >0.1，本机含首次模型下载 34s 完成 8/8）。
- 仍开放：B4 Nginx 无 TLS（需域名/证书决策）；流式浏览器端验收；remote embedding 质量验收（需 embedding API key）与全库重建演练；数据回流/ROI 真实数据；Sentry 与告警实测送达（需 DSN/Telegram env）；发布真实平台回执与 auto_publish 调度。真实平台账号/API/人工输入项已新增“设置 → 平台连接”可视化配置入口，敏感字段加密保存且不回显；后续真实回执仍依赖用户填入合法平台凭据。`workers/tasks.py` 拆分；Agent 注册表仍为声明式（无独立执行体）；task/日级预算分级；T5 百章长跑进行中（完成后补证据）。

## 下一顺序

以《24-AI开发任务列表》为准：优先补真实 Provider T3 证据（解锁全部"待验收"），再做 E2E 脚手架与 T4 用例，随后按序推进 HM/PUB/SEA。任何状态回升必须绑定同一提交中的验收证据。

## 2026-07-13 深度融合轮（经产品级验收审计修正）

> **治理更正**：本节此前把六项目融合标为"完成"并宣称"19/19 节点端到端通过、445 passed"，但《NovelCraft验收审计报告》（@53a3857，真实库实测）证明当时 18 个新 task_type 在 model_routes 与 prompts 中命中均为 0/18、默认模型为虚构的 deepseek-v4-pro——主打工作流属未接线门面，"19/19"依赖手填模型且提示词为 15 字兜底，"445 passed"跑在另一分支。按《23》§8 原声明作废，以下为整改后带证据的状态。

### 审计问题整改（2026-07-13 第四轮，同一提交链）

| 审计编号 | 问题 | 整改与证据 |
|------|------|------|
| BUG-01 🔴 | 18 新节点 0/18 路由、0/18 提示词 | db.py 播种 18 条 model_routes + prompt_registry 补 18 套方法论提示词（200-700字，绑定上下文变量）；真实库实测 gateway 解析 **18/18 有效**（deepseek-chat + 非兜底提示词）；回归锁定 `tests/test_v2_bootstrap_wiring.py`（10 tests） |
| BUG-02 🔴 | 虚构模型 deepseek-v4-pro/flash | gateway.MODEL 与 config.deepseek_model 改 `deepseek-chat`；init_db 自愈存量 v4 路由行；仓库全文 0 处 v4 残留（wiring 测试钉死） |
| BUG-03 🔴 | nc_commerce_plans 外键类型不匹配，全新库迁移崩溃 | subscriptions.user_id VARCHAR(36)→UUID；干净 pgvector/pg16 实测 `upgrade head→downgrade base→upgrade head` 三段通过 |
| BUG-04 🟠 | Alembic 双 head | 新增 `nc_merge_commerce_head` 合并；`alembic heads` 单头 |
| BUG-05 🟠 | 新节点无输出契约（垃圾输出算成功） | 18 个 pydantic 输出模型（宽容 extra、必填字段严格）+ 18 条 OUTPUT_CONTRACTS；负例测试拒绝畸形输出 |
| BUG-07 🟡 | 无 Key 静默走错误默认 | healthz 暴露 `ai_key_configured`（仅布尔），创作向导无 Key 时显示引导警示 |
| 门面追加 | fusion.py 路由从未挂载（/fusion/status 恒 404） | 已挂载 `/api/v1/fusion/status`，`tests/test_fusion_wired.py` 实测 200 |

### 六项目融合状态（整改后）

| 项目 | 状态 | 证据（真实编排/落库/校验链；AI 需真实 provider 验收） |
|------|------|------|
| oh-story-claudecode | 🧪 已接线待真实验收 | 7 SKILL 文件+LICENSE 在库；write_chapter_draft/final_humanize 提示词绑定 story-long-write/deslop 方法论；`test_fusion_wired.py` 钉死 |
| AI_NovelGenerator | 🧪 已接线待真实验收 | 四阶段 19 节点全链 T2 通过（`test_v2_bootstrap_full_flow.py`：建书→规划→人工确认书名→蓝图→写作→六维一致性→落章+知识库+账本） |
| harnessNovel | 🧪 已接线待真实验收 | 分层规划（plan_*→blueprint_*）在全链测试中逐节点 succeeded |
| show-me-the-story | 🧪 已接线待真实验收 | write_fact_reconcile 节点 + `_write_after_reconcile` 在全链测试中执行 |
| denova | 🧪 已接线待真实验收 | Event ledger（audit_logs）记录 run.started/checkpoint/run.completed 有断言；provider 失败按当前规则进入 failed/报错，待真实 provider 长链验收 |
| AI-auto-generates | 🧪 已接线待真实验收 | 批量生成批次幂等恢复、书本分析真实 Gateway、目录导入落库均有回归（2026-07-14 待验收推进轮） |

### 验证基线（2026-07-13 本轮实测）

- 干净库：Docker pgvector/pg16 → `alembic upgrade head` 一次通过（修复前必崩）→ init_db 播种 52 routes/53 prompts/0 虚构模型。
- 决定性复验（审计同款检查）：18/18 新节点路由命中、18/18 提示词命中、gateway 实解析 18/18 真实模型+方法论提示词。
- 全链 T2（历史）：曾使用 mock provider 验证真实 Postgres 编排/落库/校验链。当前规则已移除业务 mock provider，该证据仅保留为历史参考，不再作为完成证据。
- QA 遗留：QA-002 微博嵌套解析（回归测试）/QA-003 admin 读接口按 NOVELCRAFT_ADMIN_EMAILS 收紧（配置即生效，个人实例不锁死）/QA-004 DELETE novels/contents 软删级联/QA-008 注册防枚举/healthz 增加 worker 存活+队列深度检查，均有 `tests/test_qa_remediation_20260713.py` 回归。
- **真实 Provider V2 全链**：`tests/test_real_provider_v2_bootstrap.py` 已用 2026-07-14 本地开发 key 跑通；该 key 不得提交，项目截止后回收。
