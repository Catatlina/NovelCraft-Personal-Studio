# Starlume AI 当前已知问题

## 2026-08-17 KI-044 生成期首场节奏与20章清空副本规则

- 状态：**已部署，真实长跑复跑中**。
- 根因：上一轮真实 DeepSeek 第1章虽然生成质量前置检查通过，但 V7 审阅在后置阶段发现首场日常铺垫过长，pacing=medium、总分87.3；3次后置重写仍未通过。
- 修复：首场压缩目标并把超出预算分配到后续场景；生成 Prompt 强制前两句动作/异常/目标、前220字内具体事件和日常段落上限；Provider 输出超过场景上限时在生成期重试一次；canonical runtime 默认关闭后置整章重写。
- 清空规则：长跑脚本现在拒绝已有正文或 V7 状态的目标；准备脚本只从原作复制设定，创建 `active_chapters=0` 的隔离副本，不删除原作。
- 当前真实证据：旧副本 `04457ea2-e50f-41f5-b72b-c8448f5204e1` 保留为失败证据；新副本 `9070f234-9de0-4131-a301-bf3ddddeb1e9` 已确认空历史并启动20章 DeepSeek 长跑。长跑未结束前不能标记20章验收完成。
- 模型边界：DeepSeek 仍是已配置生产 Provider；GPT-5.6 Luna 仅完成路由接线，生产没有 OpenAI key，尚无真实同 prompt A/B 结论。

## 2026-08-17 KI-042 最新代码复核、生产样本与登录态验收后的未闭合项

- 状态：**已验收（单样本/登录态范围）**。本轮修复已提交为 `188197b`、`bb04e5a`、推送并部署到生产；新增前端发布准备页、Provider AI披露草稿、语义爽点评估、迁移种子和长跑脚本真实性修复，并修复浅色主题卡片文字对比度。
- 验证：后端全量 `1121 passed, 138 skipped, 1 xpassed, 2 warnings`，v0.9.2自测 `60 passed`，前端 `57 passed`、TypeScript、生产构建、真实性门禁、交付声明门禁、强制开发门禁均通过。此前失败基线由本机 PostgreSQL/Redis 未启动造成，补齐服务后已复测。
- 真实 Provider 样本：语义评估返回 `semantic_score=85.0`、`payoff_count=1`、`ending_pressure=true`；披露生成返回 `generated/provider`，模型来源为 `deepseek-chat`，变体保持 `draft`，未人工确认/发布。
- 登录态验收：在 `https://starlume.xyjin.xyz/` 登录后，`#/publish` 可加载真实项目、作品、变体、披露状态和章节选择；浅色/深色主题均复验，浅色主题已恢复可读对比度。
- 20章长跑仍未开始：生产只读数据确认现有《重生后我靠签到系统在侯府杀疯了》`seq=6` 为 `needs_rewrite`；没有在未解决前置质量问题时调用 Provider，也没有创建新书或修改生产正文。
- 长跑脚本已修正为读取真实 `contents.seq`、真实 V7 `v6_content_id`、数据库平台配置与作品元数据，并对生成正文、门禁结果、证据持久化失败 fail-closed；真正执行仍需前置章节通过质量门禁和有效的平台配置。
- 生产边界：Alembic 为 `nc_v11_disclosure_payoff (head)`，API 路由实际返回 `401 authentication required`；单样本真实调用已验收，但不等同于20章长跑、七道门禁全流程或发布完成。

## 2026-08-17 KI-043 浅色主题卡片对比度过低

- 状态：**已验收**。
- 原因：浅色主题下仪表盘卡片沿用了深色渐变背景，但正文文字仍使用浅色主题的深色文本 token，造成标题、指标和说明几乎不可读。
- 修复：`bb04e5a` 为浅色主题隔离卡片、头部、侧栏、表单和进度表面；去除浅色主题深色渐变，恢复白色表面、深色文字和边框阴影 token。深色主题保留原有深色表面。
- 生产证据：新域名登录后首页在浅色主题复验为白色卡片/深色文字；切换深色主题后文字仍保持高对比度，再切回浅色主题完成状态恢复。

## 2026-08-11 KI-041 v0.9.2 出版准备层（已部署，代码级可用，20章长跑未完成）

- 状态：**已部署**（7个新文件+1迁移+main.py修改，58单元测试通过，9个commit已推送，生产Alembic迁移已执行，6表+1字段已创建，容器健康运行）。
- 分支：`agent/publishing-v0.9.2`（从 main@8a0dfc7 新建）。
- 已完成：statistics_v1确定性统计、Alembic迁移(6表+1字段)、七道发布门禁引擎、发布准备服务(状态机)、ChapterContext五类融合、局部修复引擎、18个API端点(已注册)、58单元测试、生产部署、6章真实正文门禁验收。
- 门禁验收结果：6章真实正文 quality_candidate 6/6(100%)，publish_ready 0/6（因payoff_density启发式检测未命中），其余6道门禁100%通过，content_quality均分90。
- 已知限制：
  - 内置平台示例配置 policy_status=stale，默认情况下 platform_compliance 子门禁不通过，publish_ready 会被阻断——符合规范（stale/unknown不能publish_ready），用户必须手动确认平台规则。
  - external_risk 门禁的 is_blocking 是动态的（仅 prohibited 时 True），保存到 quality_gate_results 时反映运行时状态。
  - 局部修复引擎默认只做规则级修复，AI修复函数(ai_repair_fn)需调用方注入，未接入真实Provider。
  - content_quality 门禁在无已有V7审阅分时使用启发式评分（上限95），不是真实AI评分。
  - payoff_density 门禁为关键词启发式检测（结果类词汇+章末悬念词），不是真实爽点密度评估，需接入AI评分或更复杂NLP。
  - 前端发布准备页面未开发，API已就绪。
  - AI披露文案生成放v1.1，当前只做状态记录和发布阻断。
- 20章长跑阻断原因：现有小说"重生后我靠签到系统在侯府杀疯了"第6章 status=needs_rewrite，V7运行时质量门禁禁止继续生成下一章（返回 blocked_quality）；百章一致性小说为每章一句话的测试短文本，不适合真实验收。需创建正确配置的新书或修复现有小说质量后才能完成20章真实Provider长跑。
- 未闭合：20章真实Provider长跑验收、前端页面、payoff_density真实检测、AI披露文案生成(v1.1)。

## 2026-08-10 KI-040 一致性检查输入/输出接口错位（已修复，生产复跑已验收）

- 状态：**已验收**（代码已部署，远端两本设定包各完成 10 章真实 Provider 长跑）。
- 证据：两本真实长跑的章节统一写入“`一致性检查异常，不能放行`”，但生产 `v7_prompt_executions` 中没有 `v7.consistency_check` 记录；复现确认 `plot_brief` 字典被字符串切片触发 `TypeError`，而 V7 网关返回的 `{"text": ...}` 也未被检查器解包。
- 修复：结构化细纲显式 JSON 序列化；检查器兼容 V7 网关使用量信封和旧字符串响应；Provider/坏 JSON/缺字段/非法评分仍 fail-closed。生产证据显示两本书的 `v7.consistency_check` 均全部 `success` 且 `validation_passed=true`。
- 结果：20/20 章落库，质量门如实区分通过和需重写；连续性终审 18/20 为 `continuous`，大唐第 4、6 章被拦截为 `broken`。这证明检查链已执行，但也暴露出设定/细纲的实际跨章问题，不能把批次终态标记成全量通过。

## 2026-08-10 KI-039 Plot 评估节拍标签缺失导致场景规划提前失败（已修复，待生产复跑）

- 状态：**已接线**（本地修复和回归已通过，待部署后重新长跑）。
- 触发：`v7.plot.assess` 返回的故事节拍内容可用，但缺少 `aftershock` 标签；原代码直接把该摘要当作完整场景计划，未进入场景规划的修复路径，两本批次均在第 3 章前失败。
- 修复：不再把不完整 Plot brief 直接放行；先确定性校验，失败时回落到可修复的场景规划 Provider 链，修复结果再次经过五阶段/字数/beat 数门禁。
- 边界：原批次失败原因和已生成临时正文均保留/软删除；部署后需重新完成两本各 10 章。

## 2026-08-10 KI-038 场景计划语义契约一次性失败（已修复，待生产复跑）

- 状态：**已接线**（本地修复和回归已通过，待部署后验证）。
- 触发：真实 Provider 返回语法合法但缺少 `aftershock` 节拍；场景契约按 fail-closed 拒绝，导致大唐批次在正文生成前失败。
- 修复：场景规划增加一次真实 Provider 结构修复机会，要求保留原剧情事实并补齐五阶段；修复结果仍经过同一确定性契约校验，二次失败继续报错，不伪造计划。
- 边界：本次失败批次保留错误证据；部署后两本书需从第 1 章重新跑干净批次。

## 2026-08-10 KI-037 运行时 Prompt 版本注册并发竞态（已修复，待生产复跑）

- 状态：**已接线**（修复已通过本地回归，待推送部署并验证两条并发长跑）。
- 触发：两本作品首次同时使用同一新版 V7 审阅 Prompt 时，两个事务都先读后写，后到事务撞上 `v7_prompt_versions(prompt_name, version)` 唯一约束，导致其中一条批次在真实 Provider 已调用后失败。
- 修复：Prompt 版本注册捕获唯一约束冲突，回滚失败事务后按内容哈希复用已提交的赢家版本；找不到赢家时仍原样报错，不吞掉其他数据库错误；新增并发竞态回归测试。
- 边界：已失败批次保留失败原因；修复发布后需重新启动封神批次，并完成两本各 10 章的真实质量门禁验收。

## 2026-08-10 KI-036 V7 33 维审阅 JSON 输出预算不足（已修复，待长跑验收）

- 状态：**已接线**（修复已推送部署，新的 10 章长跑待验收）。
- 证据：生产真实审阅记录出现 `tokens_output=5000` 且 `output_raw` 在 JSON 中途结束；章节被正确拦截为 `v7_review_validation_failed`，不是正文假通过。
- 修复：审阅 Prompt 版本升至 `1.4.1`，输出预算从 5000 提升到 8000，并限制每项证据/修复建议的长度，降低 33 项证据报告被截断的概率；新增回归测试锁定预算。
- 边界：旧批次的失败章节保留为证据，不回填伪分数；需以新批次完成 2 本各 10 章、连续性和质量门禁结果为最终结论。

## 2026-08-10 KI-035 V7 品类上下文会话工厂 ImportError（已修复）

- 状态：**可用**（`main@dbb242c` 已推送部署，生产 Worker 已强制重建并完成导入检查）。
- 触发：配置真实 `genre_id` 的 V7 章节生成进入品类上下文装配时，运行时错误导入不存在的 `app.v7.db.async_session`；真实 Provider 已调用，但正文未因该错误落库为成功。
- 修复：改用 `app.v7.db.AsyncSessionLocal`，并加入回归契约测试；生产运行时已确认使用 canonical async session factory，品类上下文两本均加载 44 条规则、7 条知识、3 条 Prompt。

## 2026-08-10 KI-034 生成质量旁路整改已部署

- 状态：**可用**（代码门禁和生产链已通过；真实正文质量仍需独立验收）。
- 生产版本：`main@70688f9`；`nc_v7_genre_packs` 迁移成功，旧 V7 引导表的 UUID/启用状态/元数据默认值兼容已补齐。
- 证据：CI backend/frontend/frontend-test/security/E2E 全通过；生产 smoke 15/15；生产浏览器 v2 1 passed、兼容版 3 passed；healthz 的 database/Redis/Worker 正常。
- 未闭合：本次 smoke 未注入 Provider Key，真实 Provider 生成、两本书各 20 章连续性长跑和人工盲评仍未开始。

## 2026-08-10 KI-034 生成质量旁路已收紧（历史记录，生产复测见上）

- 状态：**可用**（本地质量链），生产当前版本待发布复测。
- 已处理：Provider 去 AI 失败、局部修复失败、空/残缺场景计划、空品类上下文、实时审阅模型高分绕过跨章正文校验、正文镜像放行和不完整连续性证据等旁路。
- 本地证据：质量专项 93 passed；前端 54 passed；TypeScript、构建、交付声明和 AI 真实性门禁通过。
- 未闭合：本机 PostgreSQL 未启动，后端全量为 862 passed、138 skipped、150 failed、54 errors；生产 smoke 和浏览器复测已完成，但真实 Provider 样本仍未执行。
- 下一步：使用真实 Provider 执行至少一章失败/成功语义复测，再决定是否进行两本书各 20 章长跑。

## 2026-08-10 KI-032 实时网感研究已接线，生产配置已存在但质量未验收

- 状态：**已接线**。
- 代码范围：作品创建/导入、榜单成书、小说设置、`contents.meta`、worker context、V7 quality profile、`GenerationEngine`、V7 event log、Docker/env 示例均已接入；研究失败 fail-closed，不返回 mock 或静态替代正文。
- 验证：研究服务 6/6、相关 V7/质量 25/25、Redis 依赖回归 30/30、前端 3/3、构建/编译/差异检查通过。
- 最新证据（2026-08-17）：诊断作品真实调用已返回 `live/miss`，2条查询、10个来源、5张原创灵感卡，真实 `deepseek-chat` 整理调用与成本、`web_research.completed` 已写入生产 V7 数据库；联网搜索链路已具备真实样本证据。
- 当前状态：首轮真实正文曾被第2场 `repeated_paragraph_opening` 阻断；段首硬结构修复已部署，最后一次重试成功，单章正文已持久化并通过 V7 审阅/一致性检查。该章仍只有单样本证据，不能替代外部检测或长期可读性验收。
- 下一步：新建并确认 `active_chapters=0` 的清空历史副本后启动真实20章长跑，逐章检查联网研究、上下章连续性、人工爽感与外部检测；不得在已有诊断章节上直接续跑。

## 2026-08-10 KI-033 本机全量后端集成回归受 PostgreSQL 环境阻断

- 状态：**已接线**（测试环境问题，不是本批功能判定）。
- Redis 依赖的目标回归已在临时本地 Redis 上通过 30/30；实时研究与质量相关回归通过。
- 全量 `backend/.venv/bin/pytest -q` 未完成：本机 PostgreSQL `localhost:5432` 未启动，已出现 116 failed、49 errors 后中止；这些失败集中在真实数据库/认证/迁移集成夹具，不能把它们算作本批功能失败或全绿。
- 另外 `verify_ai_truthfulness.py` 和强制 `ai_development_gate.sh` 当前命中仓库既有 `report_distillation.py:426` AST 告警；本批没有修改该告警，也没有用 `GATE_ALLOW_WARNINGS=1` 冒充通过。

## 2026-08-06 Demo 视觉改造批次（工作树，未部署）

- 状态：**本地可用，生产待发布**。
- 本批已把 Demo 的全局页头、工作台 KPI、作品表格、创作向导步骤轨道、书库信息行和统一面板样式落到主应用真实组件；没有复制 Demo 的静态假数据，也没有改变主导航。
- 本地验证：前端 lint、build、49 项组件测试和 Playwright 八页面可达性烟雾通过；浏览器逐页检查了空状态、表单、筛选和入口跳转。
- 未完成：尚未 commit/push/deploy；生产环境视觉截图、不同数据量下的响应式复核和真实作品列表下的最终人工验收仍待发布后执行。

## 2026-08-06 本批新增能力的边界（已部署）

- `e3a56b2` 已推送并部署生产；公网 healthz、15/15 生产 smoke、生产浏览器走查和管理员词库 GET/PUT/RESET 均通过。线上设置页已出现“质量规则 → AI 味词库”入口，登录态实测显示 11 个分类、171 个启用候选信号。
- AI 味词库故意保持 advisory：它可以提示密度、重复和语境候选，不会因为单个词、破折号或题材术语直接改写/阻断。若用户把分类关闭，后端和前端都按配置生效；最终质量门仍由 V7 真实证据负责。
- 配置接口需要登录并遵守现有管理员读取/写入权限；未登录或不在管理员白名单的请求会得到真实权限错误，不会返回内置配置冒充成功。
- 本批不改变外部质量验收边界：新 Prompt 的 Provider 20 章长跑、两位人工盲评和最终生成质量仍未完成。

## 2026-08-05 当前部署与质量边界

- `d1253f2` 已部署生产，书库项目列表已过滤 `is_deleted=TRUE` 的历史测试工作空间；主账号当前只显示主工作室。
- 生产主工作室归属 dry-run 已执行：73 条章节均为 `canonical`，0 条 `legacy_pending`/`legacy_unlinked`，因此没有需要逐条人工确认的生产历史章节。
- 生成前爽点契约 v2 已接入 V7 唯一正文链，但本次部署后尚未重新完成一轮新 Prompt 的 20 章真实 Provider 长跑；两位人工盲评仍为 0/20，最终生成质量不能标记为已验收。

## 2026-08-05 历史章节归属仍需处理

### KI-028 真实生产数据历史章节归属

- 状态：**已验收（当前主工作室范围）**。
- 本地迁移后的 1,451 条无归属记录经只读核对全部属于自动化测试工作空间，不属于 `jxianyang@gmail.com` 主工作室；本机 `novelcraft_dev` 已按外键依赖递归清理全部测试账号、项目和依赖记录，最终只保留主账号 1 个、工作空间 1 个，主账号正文数据前后均为 0。它们不应被当作业务历史章节逐条人工确认。
- 真实生产主工作室已执行 `/api/v1/chapter-scope/scan` dry-run：`scanned=0`，范围摘要为 `canonical=73`、`unresolved=0`，因此没有需要人工绑定的生产孤儿章节。后续新增历史项目仍按同一 dry-run → 高置信自动绑定 → pending 人工确认流程处理。
- 这不是正文丢失，也不是数据库清空；是为了防止错误归属污染 Novel Brain 而主动保留的安全边界。当前验收结论仅覆盖主工作室，不代表任何未来导入项目自动完成归属。

### KI-029 旧 malformed queue 兼容分支仍存在

- 状态：**可用**（隔离兼容路径）。
- 真实 UUID 生产入口已经要求合法 Novel scope；旧测试或历史坏消息使用的非 UUID placeholder 仍走兼容分支，以避免旧队列/导入契约立即崩溃。
- 该分支不接受正常新章节的真实 UUID，也不应被当作生产正文生成链。后续可在所有旧消息迁移完后删除，但当前删除会破坏既有兼容回归，因此暂不强行移除。

## 2026-08-04 未完成项目最新状态

- 真实性门禁已收口：`python3 scripts/verify_ai_truthfulness.py`、`bash scripts/ai_development_gate.sh` 均 exit 0。allowlist 仅解释三个确定性/持久化函数，不放宽正文生成必须经过真实 Gateway 的规则。
- 生产 V7 单链路真实长跑已完成 20/20 章：平均自动审阅分 88.66，最低 87.0；质量门 20/20；连续性 clean 20/20；重复段落比例 0；第三人称策略失败 0；transition contract 20/20。证据目录：`artifacts/v7-20-chapter-20260804/`。
- V7→V6 兼容书库、编辑器、完成度、TXT/Markdown/EPUB 真实链已成功；发布状态仍为 `ready_for_release=false`，因为人工盲评是独立门禁。
- 当前真实阻断只剩人工质量验收：20 个匿名 case 尚无两位独立评审（0/20）。盲评包和 CSV 模板已生成，不能把自动分数宣称为读者/编辑人工验收。

## 2026-08-04 页面整改批次的剩余门禁

### KI-026 页面改动已通过本地回归，生产视觉和真实质量仍需分别验收

- 状态：**可用（代码级）**。
- 已验证：前端全量 41 项测试、生产构建、本地八页面烟雾 1 passed、本地 V7 Cost/Prompt 走查 2 passed；审阅页的评分来源和 33 维审计覆盖有组件测试保护。
- 未验证：生产登录态下的截图级视觉复核、真实 Provider 生成样本中写作风格预设的质量差异；这些不能由静态页面测试代替。

### KI-027 强制 AI development gate 的既有 AST 真实性告警 —— ✅ 已收口（2026-08-04）

- 状态：**已验收（门禁级）**。
- 三个函数已补充最小、可审计的 allowlist 理由，并新增回归测试锁定：它们分别是确定性内容策略扫描、确定性第三人称扫描和已生成草稿的数据库持久化，不产生 AI 正文。
- 复验：`python3 scripts/verify_ai_truthfulness.py` 通过；`bash scripts/ai_development_gate.sh` exit 0；没有使用 `GATE_ALLOW_WARNINGS=1` 绕过失败。

## 2026-08-02 本轮一次性质量整改（最新）

本轮已修复代码侧待修复项，重点是“生成质量先达标，编辑器只做最后兜底”：

- V7 保持唯一正文生成链；生成前使用结构化真相/交接/剧情上下文，生成后执行连续性、读者体验、33 项内部审计和章节级去 AI 味质量门。
- 去 AI 味规则改为分布式风险控制，不禁止单个词或标点；破折号、逗号、省略号等只有在整章高密度、连续重复或同构模板化时才触发整改。
- 最终人文化、润色和改写使用统一无损文本保护：允许自然重排段落，不允许删事件、动作、对话、线索或细节；供应商压缩/空输出会重试或失败。
- 修复运行状态真实投影、Provider 错误可见、AI 操作超时、重试刷新、编辑器预览应用、书名号重复、审阅 JSON 展示、目录文件读取、导出下载和榜单并行分析。
- 本地证据：后端全量 **878 passed、138 skipped、1 xpassed**；前端 **34 passed**；构建通过；AI 真实性检查通过；开发门禁在已解释良性 warning 模式下通过。

仍未完成且不能宣称完成的外部验收：

- 真实 Provider 费用授权下的 20 章长跑、跨章读者体验差分和两位独立人工盲评。
- 真实生产生成正文经过书库、编辑器、导出后的人工终验。

当前只能标记为：**代码整改可用，质量验收待真实长跑和人工评审。**

## 2026-08-02 本轮融合开发的未闭合项

### KI-023 榜单/质量融合代码已提交部署

- 状态：**可用（已部署）**，包含运行时代码提交 `81672d8` 的最终版本已推送并部署到 `https://novel.xyjin.xyz`。
- 证据：后端离线回归 **868 passed、138 skipped、4 deselected、1 xpassed**；前端 lint、34 项测试和构建通过；AI 真实性脚本通过；生产 smoke **14/14**；登录账号浏览器走查无控制台错误。
- 补充修复：V7 trace `list_runs` 补齐 `step_count`，解决历史记录触发 `ResponseValidationError`、导致 V7 生成运行视图暂时不可用的问题。

### KI-025 V7 运行记录响应缺少 step_count —— ✅ 已修复（2026-08-02）

- 根因：`ExecutionTracer.list_runs()` 的历史记录序列化漏掉 `step_count`，但 `RunResponse` 将其定义为必填。
- 修复：补齐字段并新增 `test_v7_trace_contract.py`，用 `RunResponse.model_validate` 锁定接口契约。
- 证据：目标回归通过；生产容器重建后 V7 四个监控视图均能读取，生产日志不再出现该响应校验异常。

### KI-024 真实生成质量仍缺人工证据

- 状态：**可用（真实自动证据）**，不是最终已验收。
- 已闭合：生产 Provider V7 20 章长跑、跨章自动连续性、去 AI 味/重复风险门、V7→V6 书库/编辑器/导出核心链。
- 未闭合：至少两名盲评编辑、人工跨章连贯性和人感去 AI 味评价、盲评后的最终发布判定。
- 说明：33 维审计对旧 Provider 输出会透明标记 `macro_projection`，不会把旧七维结果冒充完整 33 项；去 AI 味规则不禁用单个标点，只在章节级密度、重复和模板风险达到阈值时介入。

## 最新运行时决策：V7 是唯一正文生成链（2026-08-02）

上一轮真实 DeepSeek 20 章双轨已证明 V7 质量优于 V6（V7 平均 92.0/最低 91.0；V6 平均 79.6/最低 72.0）。本轮已将主产品的正文生成、跨章连续性检查、质量审阅和重生成统一收口到 V7 Director。

- V6 仅保留兼容事实、`contents` 存储、编辑器和导出承载；V7 通过质量门后幂等写回 V6，避免双链路重复生成和重复章节。
- 公开 Agent `writer` 入口已同步改为 V7；独立编辑器润色入口仍属于编辑功能，不作为章节生成链路。
- Bootstrap 规划/蓝图仍使用既有结构化准备步骤，但不再执行旧 V6 正文写作/定稿节点。
- 本轮代码已部署为 `7851b7f`；生产 smoke 已通过，但生产链路仍需按 V7 单链路做 20 章质量长跑。
- 这项收口不等于生成质量已验收；当前人工盲评仍是 0/20 两位评审覆盖。

## 最新状态真实性修复（2026-08-02）

- `7851b7f` 已部署生产。旧 Bootstrap 对 V7 `pending_approval`/质量拒绝的“伪完成”投影已修复；节点现在分别显示等待确认、质量待重写或失败，空产物不会标记为成功。
- 质量门拒绝的真实正文会写入 V6 `contents.status=needs_rewrite`，并保留质量分、问题和版本快照，便于编辑器查看和重写；通过质量门才是 `reviewed`。
- 截图对应的历史 workflow `37b01da0-76aa-4383-b2ea-1fd270e4014d` 已定向纠正为 `waiting_human`，不是批量修改其他 run。
- 生产证据：healthz 200，`prod_smoke.py` 15/15；这只证明部署和状态链可用，不证明真实生产长篇质量达标。

> 更新时间：2026-08-02。按阻断程度排序；解决后必须保留验证证据并从本表移除或标注历史。

## 阻断生产验收

### KI-001 新 UI 真实 AI 全链 -- ✅ 已验收(2026-07-28)

- 状态:**已验收**(本地真实 Key 全链通过 + 生产已部署,KI-002 收口完成)。
- 解决过程(2026-07-28,注入真实 `DEEPSEEK_API_KEY` 后连续定位并修复 3 个真实阻断):
  1. **Wizard 表单校验 bug**:`Wizard.tsx` 字数输入 `min={5000} step={10000}` 与全部预设值(100000/300000/...)不满足 HTML5 step 约束 → 浏览器静默拒绝提交,工作流从未启动。修复为 `min={10000}` 且 JS 校验同步 `targetWords < 10000`。
  2. **E2E 编排缺 Celery worker**:`scripts/e2e-backend.sh` 只起 uvicorn,`execute_bootstrap` 入队后无消费者。修复为 worker(concurrency=2)+uvicorn 双进程并带退出清理。
  3. **dev 库迁移落后**:`novelcraft_dev` 停在 `nc_versions_reason_text`,`ai_calls` 缺 `user_id` 列 → 网关预算断言 `UndefinedColumn`,节点重试 4 次后 run failed。执行 `alembic upgrade head`(补 6 个迁移至 `f932f2b0b3bb`)。
- 通过证据(全部真实,无 mock):
  - E2E:`npx playwright test e2e/main-chain.spec.ts --grep "protected"` → **1 passed (13.2m)**。
  - Celery 日志:`execute_bootstrap` 两段任务分别 254.4s(→ `waiting_human`,人工定名断点真实出现)与 527.7s(→ `succeeded`)。
  - run ID:`8f1fd62b-5ad8-4208-8fd8-887f33425631`,status=succeeded。
  - `ai_calls`:本次 run 窗口 **19 条**真实 DeepSeek 调用,合计 ¥0.1889(重节点实测 write_polish 95.6s / write_length_check 94.9s)。
  - 产物:小说《午夜头条》+ 第一章「午夜浮现」(body 2350 chars),由测试在真实候选书名中点选定名。
  - 截图:`frontend/artifacts/screenshots/protected-02..06.png`(人工定名/完成/书库/编辑器/审阅,5 张)。
- 保留约束:`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除;无 Key 环境仍真实跳过,CI 门禁不受影响。

### KI-002 历史新 UI 版本已部署生产 -- 已验收(2026-07-28)

- 状态:**已验收**。
- 部署过程(2026-07-28):
  1. 只读扫描 43.156.17.78:确认拓扑为 nginx 443→docker frontend:8090, Compose 项目在 `/opt/NovelCraft-Personal-Studio/`,运行旧 commit `bf1a377`;无 schema 迁移;`.env` 含全部密钥。
  2. 处理分叉:`origin/main` 已含另一工作副本推送的 E2E 修复;本副本仅把文档提交 rebase 到 `origin/main` 后首次部署至 `f2e2bde`。
  3. 全量重建并启动 api/worker/beat/migrate/frontend,healthz 返回 `ai_key_configured:true`、`worker:ok: 1 online`、DB/redis ok。
- 生产验证:`https://novel.xyjin.xyz/` → 200;`/api/v1/healthz` 全绿;部署 commit 随后续修复推进到 `91bcf9b`。
- 关联收口:KI-001/KI-003 由"可用"提升为**已验收**。
- 边界：该证据只覆盖部署到 `91bcf9b` 的历史版本，不覆盖当前 `main @ f8e343c` 或 2026-07-29 修复批次；当前版本部署见 KI-009。

### KI-003 AI 编辑与版本恢复真实浏览器闭环 -- ✅ 已验收(2026-07-28)

- 状态:**已验收**(真实 `DEEPSEEK_API_KEY` 下 E2E 全链通过 + 生产已部署,KI-002 收口完成)。
- 修复(2026-07-28):E2E 选中错误版本导致恢复后正文变空。根因为测试用脆弱的 `nth(index)` 点击,在版本历史 UI 列表尚未刷新时点到 `body={}` 的 `offline_save` 版本;应用恢复逻辑本身正确(`restore_version` 写回目标快照 body)。修复:恢复按钮加 `data-version-id={v.id}`(`frontend/src/components/Editor.tsx`),测试按真实版本 id 点击并 `waitFor` 按钮可见。
- 通过证据(全部真实,无 mock):
  - E2E:`npx playwright test e2e/main-chain.spec.ts --grep "小说主线6"` → **1 passed (29.2s)**。
  - 真实 AI:run9 两次 `editor.continue` 真实 DeepSeek 调用(deepseek-v4-pro,succeeded,含 prompt/completion tokens 与成本)。
  - 闭环:续写→预览可见且正文不变→放弃后原文不变→再次续写→应用到草稿正文含 AI 建议→按版本 id 恢复后原文 A 回归、AI 建议消失。
  - 截图:`frontend/artifacts/screenshots/protected-07..09.png`(AI 预览 / 应用后 / 版本恢复后)。
  - 取证:`restore->content.body` 恢复后确为 `{content:[{text:"档案室..."}]}`,编辑器 DOM `<p>档案室...</p>`。
- 保留约束:`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除;无 Key 环境仍真实跳过。

## 文档和门禁问题

### KI-004 README 仍描述旧产品入口 —— ✅ 已修复（2026-07-28）

- README 已更新为描述当前八项小说页面入口（含扫榜选书），与代码一致。

### KI-005 真实性门禁存在宽泛告警

- `bash scripts/ai_development_gate.sh` 的 AST 真实性与 whitespace 已通过。
- suspicion scan 会命中测试 mock、输入 placeholder、历史非小说 fallback 字段和自然空集合,默认返回 3。
- 必须逐条阅读输出;只有确认不是生产假实现后,才可按规范用
  `GATE_ALLOW_WARNINGS=1` 复验并记录解释。
- 允许告警不等于修复告警,也不能据此宣称全项目完成。
- 接手逐条解释(2026-07-28,全部非业务伪实现):脚本三类扫描命中均属《23》§10 允许的良性命中--
  1. **mock/fallback/placeholder/deprecated/空返回** 命中约 120 行,均为以下之一:测试代码 `vi.fn().mock*`/`vi.stubGlobal('fetch',...)`(api.test.ts、ThemeProvider.test.tsx、Progress.test.tsx、WorkspaceDashboard.test.tsx)--单元测试对网络/timer 的 monkeypatch,符合《23》§10 规则 1,非产品 mock provider;前端 `placeholder=` HTML 属性(LoginPage/Wizard/Settings/BookLibrary 等输入框)--UI 占位符,非生成结果;反伪实现注释(`never fake success`、`暂无数据 placeholder`、`report real numbers instead of 0/0 placeholder`)--显式拒绝伪造;合法空态 `return []`/`return {}`(db.py、各 service 无数据分支、circuit_breaker、hotspot 采集失败态)--有错误语义/空态文案,非静默成功;`hotspot_collector.py` 的 `fallback_url`--平台官网兜底链接(用户手动访问),非 AI 生成兜底,采集失败仍按源返回状态/502;`gateway.py`/`config.py` 的 `fallback_json`--仅为 model_routes 表列名,`config.py` 已 `max_length=0` 禁止业务 fallback,网关注释明确 "No mock or fallback generation";`ranking_adapter.py:197` `return [("261","都市日常","1")]  # fallback`--历史非小说榜单解析兜底默认分类,不在小说产品路径,保留但不得计入小说主线完成;`core/security.py:25` `JWT_SECRET="dev-secret-change-in-production"`--开发默认密钥,仅当未设环境变量时生效,E2E/生产必须用 ≥32 字节密钥(E2E 已用 32 字节 secret);`platform/modules/manager.py:96` `# TODO: clone repo...`--插件市场未接入口,非完成声明。
  2. **固定模板/伪造输出措辞** 仅 `gateway.py:791`、`config.py:24` 两条注释,说明已移除硬编码预算常量,非生成模板。
  3. **硬编码 active/wired 自报告** 仅 `api/v1/billing.py:82` `UPDATE ... status='active'`--订阅付费成功后的真实状态写库,由真实支付/更新驱动,非能力自报告。
  - 结论:全部命中为非业务伪实现;按《23》§10 用 `GATE_ALLOW_WARNINGS=1` 复验仅表示"已确认良性",不等于修复告警,也不能据此外推全项目完成。

### KI-006 全页面视觉证据 -- 可用(2026-07-29)

- 状态：**可用**（`visual.spec.ts` 已包含八页面，但历史截图证据仍是七页面口径；本批已把用例名改为八页面，待显式开启截图门禁并检查新产物。富状态全链 `write_polish` 修复待真实 Provider 重跑，见 KI-007）。
- 证据:
  - `STARLUME_CAPTURE_VISUAL=1 npx playwright test --grep "七页面"` → **passed (9.1s)**，生成 15 张截图（七页面 1280/390 + 404）。注意：此截图集不含扫榜选书页面，需更新 visual.spec.ts 并重跑。
  - `npx playwright test --grep-invert "小说主线5"` → **6 passed, 1 skipped**;含 3-progress `protected-01-progress-running.png`(真实运行中节点)+ 6 版本恢复闭环 `protected-07/08/09.png`。
  - 小说主线5(人工定名→完成→书库→编辑器→审阅富状态)连续两次因 `write_polish` 节点返回 `invalid_output` 失败,已停止重试;该问题已单独记录为 KI-007。

## 新发现的线上/生产稳定性问题

### KI-007 `write_polish` 节点对 `deepseek-chat` 输出格式与保真不稳定

- 状态：**可用**（真实 Provider 本地全链已通过；生产已部署，但尚未完成真实生产长篇复测）。
- 现象:真实 AI 全链 E2E(小说主线5)连续两次在 `write_polish` 节点返回 `invalid_output`,导致 run failed;切换模型前旧链路上也曾出现相同问题。
- 根因(已校正):失败发生在 `gateway.validate_task_output` 的 Pydantic 契约校验(`_WritePolishOutput` 要求 `polished.body: list[str]` 且 `changes_summary: str`),而非 `_persist_chapter_polish`。`deepseek-chat` 在此节点返回了**结构松散但内容有效**的载荷:裸 `body`(无 `polished` 包裹)、`body` 为字符串而非段落列表、或缺失 `changes_summary`。重试循环只是对同一种漂移重新采样 3 次后放弃。
- 修复(commit 见下方部署记录):在 `gateway.validate_task_output` 前增加 `_normalize_bootstrap_output` 输出修复层(V3 Repair Engine 思路):
  1. 无 `polished` 包裹时,从裸 `body` / `chapter.body` / `text` 自动包装;
  2. `body` 为字符串时按换行 + 分句兜底切分为段落列表;`body` 为 dict 列表时抽取 `text`;
  3. 缺失 `changes_summary` 时由 `changes` 列表派生或填空;
  4. `_split_into_paragraphs` 对单块长文本按句分组,保证段落数门槛不误伤真实长文。
  修复后契约不被削弱--真正空 / 非叙事输出仍会被下游闸门拒绝。
- 证据:
  - `tests/test_write_polish_repair.py` **8 passed**(canonical / 裸 body / 字符串 body / 单块长文 / 缺 changes_summary / changes 列表 / dict 列表 / 空输出仍拒)。
- 追加真实根因与修复：
  1. `generate_story_arc` 的提示输出契约使用 `arc_name/arc_type`，与 Gateway 的 `name/goal/...` schema 冲突，已统一；
  2. `chapter_text` 未列入长上下文字段，真实润色提示只收到约 1500 字符，已提高到 12000；
  3. 润色改为最多 3 次真实质量采样并回传明确段落/字数差距；内容保留不足 75% 时禁止继续；
  4. 仅当文本保留至少 75% 且段落不足 60% 时，允许按句末标点做不改字的确定性重新分段；
  5. Bootstrap 首章装配器此前把字符串当字典并静默吞错，现已真实注入装配文本，缺创意/创作圣经/当前章细纲直接失败。
- 真实证据：protected “小说主线⑤” **1 passed (3.3m)**；run `a416b8a8-2bcb-4ad1-8f3d-d50c0956ba4d` 为 20/20 succeeded、20 条真实 succeeded `ai_calls`，最终正文 35 段/4581 非空白字符；首章初稿请求记录含 1451 字符装配上下文。
- 下一步:
  1. 提交 `391ef3b` / Actions `30443223990` 已全绿。
  2. 最终生产部署后重跑小说主线⑤ smoke，再提升为已验收。

### KI-008 `f8e343c` 的 GitHub Actions 后端失败（历史，已解决）

- 状态：**已验收**。
- 失败 run：`30425548279`，commit `f8e343c`；backend 为 `10 failed, 750 passed, 9 skipped, 1 xpassed`，其余 frontend、frontend-test、e2e、security 通过。
- 根因与修复：
  1. 新增 `generate_story_arc` 后，19 节点断言与完整流程 Provider 夹具未更新；
  2. 同步调度测试未接受新的 `api_key_ref`；
  3. 质量证据无条件声称 pacing/story-arc 来源，现改为只记录实际采样来源；
  4. Costs/预算 UI 已按小说优先退役，但两条静态源码测试仍要求恢复旧入口；
  5. `PROJECT_PROGRESS.md` 的历史措辞触发交付声明校验。
- 本地证据：后端 `761 passed, 9 skipped, 1 xpassed`；前端 `12 passed`；构建通过；E2E `4 passed, 4 skipped`；交付声明、AI 真实性、前后端契约、`git diff --check` 通过。
- CI 证据：修复提交 `07a8c0f` 的 Actions run `30439322188` 五项全绿（backend、e2e、frontend、frontend-test、security）。

### KI-009 当前 V3 代码尚未部署生产（历史条目，已关闭）

- 状态：**已验收（部署门）**，不是生成质量验收。
- 生产当前提交为 `7851b7f`；已完成 healthz、登录、八页面、切书、建书/保存、V3 20 节点结构 smoke。
- 仍需单独完成真实 Provider 20 章长跑和人工盲评，见 KI-018/KI-020。

### KI-021 进度页旧 run 的状态投影修复 -- 已修复（2026-08-02）

- 根因：旧 `_persist_canonical_bootstrap_result` 无条件把 delegated 节点写为 `succeeded`，没有区分 V7 `pending_approval`、`needs_review`、Provider 失败和实际完成。
- 修复：状态机和进度页按 canonical 结果真实投影；SSE 也把等待确认、质量待重写、预算/Provider/派发失败视为终态；质量拒绝草稿保留在 V6 并标 `needs_rewrite`。
- 证据：canonical 状态回归 10 passed；前端 32 passed；生产 smoke 15/15；截图对应 workflow 已定向改为 `waiting_human`。

### KI-010 V3 12 项存在“代码已建但产品闭环不完整”

- 状态：**已接线**。
- 已经通过真实调用复核的项：Chapter Function、Novel DNA、Story Arc、策略库/Prompt Compiler、人物认知分层、时间线锚点、读者体验、Pacing、Author Style Card、Scene Director。详细 run、调用和持久化证据见 `AI_HANDOFF.md` 1.4 与 `V3-FUSION-TRACEABILITY.md`。
- 同提交门禁：`5c544ff` / Actions `30445384633` 五项全绿。
- 本轮修复的伪接线：
  1. Prompt Compiler 已导入却无产品调用者，现进入 Writer 真实请求；
  2. Bootstrap 最终一致性未产出读者体验，现改为必填并持久化；
  3. Author Style 信号和卡片写入均未提交事务，且保存后不触发 Learning Agent，现已修复；
  4. Scene Director 场景写入未提交事务，前端轮询使用旧闭包状态，现已修复；
  5. 人物提取提示未要求 `known_info`，五层认知全空；现增加强契约，并修复 `get_states` 跨书查询。
- 产品入口已补：三档修复统一执行“签名预览 → 用户确认应用”，并具备旧预览冲突与防篡改门禁；本地 781 后端测试、14 前端测试、构建和确定性 E2E 通过。
- Repair 产品接线提交 `6f7184c` / Actions `30447533339` 五项全绿。
- 仍未闭环：当前环境未配置 Provider 密钥，真实 AI 正向预览/应用场景尚未复验。因此 Repair Engine 与 V3 12 项整体仍只能标记为已接线。

### KI-011 多书选择回弹、内容不刷新与跨账号缓存污染

### KI-012 V6/V7 生成质量整改尚未完成真实验收

- 状态：可用（代码与目标回归），不是已验收。
- 已落地：V6 主章节链真实 `final_humanize`、事实 anchor 局部修复+二次复核、连续性失败闭环；V7 交接契约、85 分质量门和 V6 章节桥。
- 证据：目标回归 60 passed、2 warnings；`verify_ai_truthfulness.py` AST 检查通过。
- 当前状态：本地 `.venv` 已补齐项目 requirements 中声明的 `asyncpg`，真实 PostgreSQL/Redis 下全量后端回归已形成证据；注册 503 已通过本地服务依赖与测试 Redis 默认地址修复得到解决。
- 仍然阻断：尚无真实 Provider 的 V6/V7 多章复测和人工盲评。
- 不得宣称：跨章连贯性已达标、去 AI 味已完成人工验收、V6/V7 全应用运行时已统一；当前只能宣称 Provider transport/执行账本边界已接线。

### KI-013 V6/V7 Gateway、成本与 Prompt provenance 统一边界已接线，真实验收未完成

- 状态：可用（代码级），不是已验收。
- 现状：V6/V7 已通过 `backend/app/services/unified_gateway.py` 共用同步、异步和流式 Provider transport；`backend/app/services/ai_runtime.py` + `nc_v6_v7_runtime_ledger` 提供共享执行账本。V7 每次真实调用会幂等播种 `PromptVersionManager` 并写 `v7_prompt_executions`；V6 成功/失败/流式调用写同一账本，Cost API 的项目范围 ledger 可同时汇总两版本，V7 预算门和成功 usage 记账保持 fail-closed。
- 证据：`test_v7_budget_gateway.py`、`test_v7_runtime_provenance.py`、`test_v6v7_quality_harness.py`；目标组合 67 passed、2 warnings；Alembic 已到 `nc_v6_v7_runtime_ledger (head)`，`backend/scripts/seed_v7_prompts.py` 已实际执行并重复执行验证幂等。
- 仍然阻断：尚未完成真实 Provider 回放、V6/V7 跨版本账本对账、V6 书库/编辑器/导出回写和人工盲评。
- 下一步：提供真实 Provider key、同题材双项目/双轨数据库和两名盲评编辑，执行 `scripts/v6v7_20_chapter_quality.py --execute --confirm I_UNDERSTAND_REAL_API_COST_AND_DUAL_WRITE`，再核验共享账本与 V6 facts。

### KI-014 E2E 注册限流与端到端最终结果 -- 已修复（本地验证）

- 现象：多 worker E2E 共享本机 IP 时，注册接口的生产限流 `5/minute` 会造成榜单折叠用例在 UI 断言前等待并超时。
- 修复：注册限流改为读取 `NOVELCRAFT_REGISTER_RATE_LIMIT`，Playwright webServer 仅注入 `120/minute`；生产默认仍为 `5/minute`。这是测试环境隔离配置，不是放宽生产安全策略。
- 证据：`ranking-fold.spec.ts` 单测 **1 passed**；历史完整 `npm run test:e2e` 为 **18 passed、9 skipped、0 failed**，本轮最终复跑为 **17 passed、10 skipped、0 failed**；多出的 skip 是未观测到可操作异步 run 的条件性跳过。

### KI-015 强制 AI development gate 仍有已知宽泛告警 -- 可用（不能视为全绿）

- `bash scripts/ai_development_gate.sh` 当前返回 **exit 3**；`verify_ai_truthfulness.py`、Git whitespace 检查通过。
- 剩余命中包括测试 monkeypatch、HTML input placeholder、合法空集合/服务降级分支、历史非小说榜单 fallback、移除硬编码预算的注释，以及真实订阅写库的 `status='active'`。这些逐条解释见本文件 KI-005，不是生成结果伪造证据。
- `GATE_ALLOW_WARNINGS=1 bash scripts/ai_development_gate.sh` 只能作为已解释告警的复验，不能将其改写成“强制门禁全绿”。

### KI-016 V7 读者体验与情绪钩子证据已接线，真实人感未验收

- 状态：可用（代码与确定性回归），不是已验收。
- 已落地：V7 审稿强制五项 reader experience 字段；场景计划/正文/续写提示加入读者承诺、情绪曲线、开场锚点、局部转折和章末钩子；交接契约持久化读者体验与下一章桥接证据。
- 证据：`test_v7_generation_quality_prompts.py`、`test_v7_merge_quality.py`、全量后端 843 passed；参考差异见 `docs/AI_WORKBENCH参考评估_20260802.md`。
- 仍然阻断：没有真实 Provider 的 20 章双轨样本与人工盲评，不能证明相邻章节人感连贯或去 AI 味优于旧链。

### KI-017 V7 novel→V6 project 映射已落表

- 状态：可用（本地迁移与回填），生产证据未验收。
- 已落地：`nc_v7_novel_project_mapping` migration、`v7/integration/project_mapping.py`；桥接写回前校验 V6 novel 所属 project 并持久化映射。
- 证据：本地 Alembic 头为 `nc_v7_novel_project_mapping`，回填 6994 条；跨 project pair 的拒绝测试通过。
- 仍然阻断：尚无生产数据库迁移/真实 V7 章节写回后在 V6 书库、编辑器和导出可见的完整证据。

- 状态：**可用**。
- 根因：`projects` / `currentNovel` 使用全局离线缓存键；run 恢复异步响应可覆盖人工选择；人工选择后章节加载 effect 被永久禁用；快速切换没有请求代次校验；Layout 的本地选择值未随真实 `currentNovelId` 同步。
- 修复：缓存按登录账号隔离；登录/退出清理工作区；选择 epoch 使旧详情/run/章节响应失效；选书后重新加载章节；Layout 同步受控值。
- 产品范围：选择器只在进度、编辑器、审阅三个公共页出现。
- 本地证据：前端 `14 passed`、构建通过；新增真库 Playwright 竞态用例通过；完整确定性 E2E `5 passed, 4 skipped`。E2E 后端启动前会升级 Alembic，旧库缺 `scenes` 表不再被静默容错。
- 升级门禁：本批同提交 CI 全绿、生产切书 smoke 后提升为已验收。

## 非本轮目标但必须如实保留

- 百章真实 Provider 长跑尚未验收。
- 真实内容平台发布回执尚未验收。
- 外部热点源七天连续稳定性尚未验收。
- 这些模块目前从小说 UI 隐藏,不得因"看不见"就删除历史数据或把它们写成已完成。

### KI-018 真实 Provider 20 章双轨已完成自动回放，人工盲评仍阻断 -- 已接线

- 本地隔离环境已用真实 DeepSeek 完成 V6/V7 各 20 章；自动门通过，V6 平均 79.6、V7 平均 92.0，V7 20 章均有跨章交接契约。
- 盲评包已生成 20 个匿名 case，但两位独立评审覆盖为 0/20；不能把模型自审分数写成用户质量验收。
- 解除条件：两位独立评审分别填写 `blind-scores.template.csv`，随后使用评分文件重新运行 20 章 harness，检查一致性、差异和最低分门禁。

### KI-019 真实长跑期间发现的状态/导出问题已修复 -- 可用

- 批次进度此前缺少事务提交，可能持久化为 `running`；Provider 输出 schema 失败此前可能让子任务退出但批次仍停在 `running`。现已分别补齐进度提交和批次失败收口，并有批次恢复回归。
- EPUB 导出此前因运行环境缺少 `EbookLib` 返回 503；已补运行依赖并在真实产品链中验证 200、`application/epub+zip` 和有效 ZIP 文件头。
- 本地长跑账本留下了 369 条真实执行记录、0 条最终失败记录；仍需目标部署环境重复回归，不能将本地修复写成生产验收。

### KI-020 生产已部署，但真实 20 章质量验收仍未执行 -- 可用

- `7c06fe3` 已部署到 `https://novel.xyjin.xyz`；部署前备份、Alembic 迁移、Prompt seed、容器健康检查均有记录。
- 生产 smoke 15/15 通过，生产浏览器走查 4/4 通过；这证明部署和主要用户入口可用，不证明生产长篇生成质量。
- 仍未闭合：生产真实 20 章双轨、两位人工盲评和最终生成质量目标；不得把 smoke 结果写成质量验收。
