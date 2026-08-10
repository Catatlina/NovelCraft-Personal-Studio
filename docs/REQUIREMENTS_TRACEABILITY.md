# Starlume AI 小说主线需求追踪矩阵

## 2026-08-10 生成质量旁路收紧（本地待发布）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| Provider/质量失败不得伪装通过 | 可用 | V7 DeAI、编辑器包装和生成前置门禁均 fail-closed；质量专项回归通过 | 生产真实 Provider 失败注入复测 |
| 场景计划不能以空 beat/缺阶段进入正文 | 可用 | `SceneDirector.validate_scene_plan_contract`；4–6 beat、字数预算、五阶段校验；专项回归通过 | 生产真实 Provider 计划样本 |
| 实时审阅必须验证跨章正文连续性 | 可用 | `review_service._continuity_evidence` 加入 transition contract + prose continuity；模型高分不能替代第 2 章起的确定性证据 | 生产登录态章节实测 |
| 正文镜像/平行版本不得进入完成状态 | 可用 | `CHAPTER_MIRROR_HARD_GATE=True`；标题基名+开头锚点检测命中即质量失败 | 生产两本书长跑和人工复核 |
| 品类上下文加载失败不得静默降级 | 可用 | 已配置 `genre_id` 时空品类包直接停止生成；不再使用空上下文冒充成功 | 生产真实品类包生成 |

## 2026-08-10 爽文网感研究链（本地未部署）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 生成目标以爽、快节奏、读者兴奋为主 | 可用 | 新书默认爽感快节奏风格；V7 既有五阶段爽点契约继续作为结构硬门禁；研究卡注入场景规划和正文 Writer | 真实 Provider 章节样本与人工爽感盲评 |
| 生成前联网提炼网感灵感 | 已接线 | `WebResearchService` → Tavily `/search` → 真实 AI 原创灵感卡 → V7 Context/Scene/Writer；无 Key/搜索失败直接失败 | 服务器配置 Tavily Key、真实一章验收 |
| 研究结果缓存、审计和来源可追溯 | 可用 | 复用 `v7_event_logs`；查询哈希、TTL、卡片、来源域名、成功/失败事件；不存完整网页正文 | 生产数据库迁移/事件回放验证 |
| 现有作品可切换研究策略 | 可用 | `GET/PUT /api/v1/novels/{novel_id}/generation-settings`；版本快照和 `audit_logs`；Settings 页面有读取/保存测试 | 生产登录态浏览器点击验证 |
| Docker/环境变量可配置 | 已接线 | compose、`.env.example`、`.env.production.example`、healthz 状态字段已补齐 | 生产注入 Key 后重建并检查容器环境 |
| 真实联网生成质量验收 | 未开始 | 本地仅完成失败/成功协议 mock 的单元契约；远端无 Tavily Key | 一章实跑、两本各 20 章长跑、上下章连续性和人工评审 |

## 2026-08-06 Demo 视觉骨架落地（未部署）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 页面不再沿用旧版骨架 | 本地可用 | Layout 页头、首页 KPI/作品表格、Wizard 步骤轨道、书库/进度/扫榜/设置统一面板已落地 | 发布后生产截图复核 |
| 首页呈现 Demo 式工作台信息密度 | 本地可用 | 四项 KPI 使用真实书库/运行数据；无数据显示“未评分/—”，不伪造数字 | 多作品、多章节真实数据复核 |
| 主导航保持不变 | 已验收（代码级） | `Layout.tsx` 保留原 `NAV_ITEMS` 顺序和入口，仅增加页头品牌/面包屑 | 生产发布后点击回归 |
| 视觉改造不破坏真实功能 | 已验收（本地） | lint、build、49/49 前端测试、页面烟雾 1/1；浏览器核对六个主入口 | push/deploy 后生产走查 |

本批不能标记为生产已部署；发布和线上验收仍是独立步骤。

## 2026-08-06 AI 味词库与编辑会话（已推送部署）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| AI 味词库前台可查看、配置、编辑 | 已验收 | `Settings.tsx`“质量规则”入口；11 类词库可开关、改名、改说明、增删词条；`Settings.quality.test.tsx`；生产登录态页面显示 11 类/171 个启用信号 | — |
| AI 味词库可持久化并回读 | 已验收 | `/api/v1/quality/ai-flavor-lexicon` GET/PUT/RESET；现有 `settings` 表；commit `e3a56b2`；生产管理员 GET/PUT/RESET 3/3 | — |
| 词库参与生成前约束但不变成单词禁令 | 可用 | `render_ai_flavor_guidance` 注入生成、续写、人文化 Prompt；`mode=advisory`、`hard_gate=false`；V7 审阅保留原文证据和题材豁免 | 新 Prompt Provider 长跑与人工误伤评估 |
| 编辑器支持自由输入 AI 修改意见 | 可用 | `EditorAiChat.tsx` 与 `EditorAiChat.test.tsx`；先生成预览，确认后才应用 | 真实编辑器 Provider 正向操作复核 |
| 本批质量/真实性门禁 | 已验收 | 后端 `1035 passed`、前端 `49 passed`、TypeScript/lint/build、`verify_ai_truthfulness.py`、`ai_development_gate.sh` clean | 真实生成质量仍需独立外部验收 |

本批“可用”仅表示代码和离线回归闭环，不表示生产质量或人工盲评已验收；真实 Provider 20 章、两位评审和最终读者体验仍按独立门禁处理。

## 2026-08-05 部署后真实证据补充

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 生产部署与服务健康 | 已验收 | `d1253f2` 已部署；前端/healthz/登录/项目列表通过；容器健康 | 持续运行观察 |
| 测试工作空间不再污染主账号列表 | 已验收 | 书库查询过滤 `is_deleted=FALSE`；主账号仅显示主工作室 | — |
| 主工作室历史章节归属 | 已验收 | `canonical=73`、`unresolved=0`；生产 dry-run `scanned=0` | 新导入项目按流程复核 |
| 新爽点契约在生成前生效 | 可用 | `chapter-payoff-contract-v2`、四档强度、五阶段节拍、可见反馈和去 AI 味保护已部署 | 新 Prompt 20 章真实长跑、两位人工盲评 |

## 2026-08-05 历史章节归属治理

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 历史无归属章节保留且不污染主书库 | 可用 | `nc_legacy_chapter_scope` 为章节补充范围状态；本地测试产物已按外键依赖清理；最终仅保留主账号/主工作空间，主账号正文数据前后均为 0 | 生产迁移后再次核对 |
| 历史章节扫描、证据和决议可追踪 | 可用 | `chapter_scope` 服务和 `/api/v1/chapter-scope/*` 提供 dry-run、候选证据、状态、操作者和审计日志 | 生产环境执行扫描 |
| 高置信历史章节安全自动归属 | 可用 | 只有直接 Novel/Run/Batch provenance 或强标题证据且超过置信度与边际阈值才会自动写入 `legacy_resolved` | 生产样本验证自动绑定准确率 |
| 模糊历史章节人工确认 | 已接线 | `pending` 决议列表和 `POST /chapters/{chapter_id}/bind` 已接入；绑定前不会进入 V7 写入链 | 需在真实生产数据扫描后确认，不对本地测试产物逐条处理 |
| 正常新章节和 V7 编辑/审阅/生成必须有合法 Novel scope | 可用 | API、worker、V7 runtime、修复和场景入口统一执行 fail-closed scope gate | 生产部署后 smoke |

“已接线”表示操作入口和状态闭环已经存在，但尚未完成真实人工处理；不能把未确认历史归属写成已验收。

## 2026-08-04 未完成项目最新证据

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| AI 真实性/开发门禁 | 已验收 | `verify_ai_truthfulness.py` 通过；`bash scripts/ai_development_gate.sh` exit 0；allowlist 仅覆盖不生成正文的确定性扫描与草稿持久化 | 后续新增生成函数仍需保持真实 Gateway 证明 |
| 生产 V7 单链路 20 章长跑 | 可用（真实自动证据） | 20/20 `reviewed`、20/20 `v7_quality_gate_passed`；平均 88.66、最低 87.0；连续性 clean 20/20；重复段落比例 0；第三人称失败 0；transition contract 20/20；证据在 `artifacts/v7-20-chapter-20260804/` | 两位独立人工盲评 |
| V7→V6 书库/编辑器/导出产品链 | 可用（真实生产链） | 20 章写回 V6 `contents`；编辑器、完成度、TXT/Markdown/EPUB 均返回真实证据；`ready_for_release=false` 正确保留人工门禁 | 人工应用/阅读复核与最终发布判定 |
| 人工盲评包 | 已接线 | `blind-review-packet.md` 20 个匿名 case；`blind-scores.template.csv` 评分模板 | 当前 0/20 case 达到两位评审覆盖 |

“可用（真实自动证据）”不等于“生成质量已最终验收”；人工评审仍是故意保留的独立门禁。

## 2026-08-04 页面可用性整改批次（代码级）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 创作历史默认折叠 | 可用 | `Progress.tsx` 使用原生 `details/summary`；目标回归覆盖展开、打开记录、加载更多 | 生产账号视觉复核 |
| 审阅综合评分与审计准确性展示 | 可用 | `Review.tsx` 读取 V7 `overall_score`、`dimension_scores`、`audit_report`、连续性结果；测试覆盖真实分数、折算分、33 维来源标注 | 真实 Provider 审计覆盖与人工相关性 |
| V7 质量与运行监控页面 | 可用 | `V7Dashboard.tsx` 既有真实 API 数据流；`styles.css` 补齐总览/运行/账本/Prompt/错误/权限/移动端样式；Playwright V7 走查 2 passed | 生产视觉截图与真实运行数据持续观察 |
| 创作向导写作风格 | 可用 | `Wizard.tsx` 预设下拉 + 自定义高级入口；生成请求仍提交 `style` 字段；Wizard 测试覆盖选择和自定义 | 真实生成样本验证预设对正文质量的提升 |

上述状态是页面和代码级状态，不等于真实 Provider 长跑、人工盲评或最终生成质量验收。

## 2026-08-02 本轮一次性质量整改（当前发布批次）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 生成前质量控制与跨章交接 | 可用 | V7 GenerationEngine、ContextAssembler、TruthStore、transition contract、场景目标/阻碍/选择/代价约束 | 真实 Provider 20 章长跑 |
| 33 项内部审计与读者体验门 | 可用 | `audit_dimensions.py`、`ReviewEngine`、V7 quality gate；关键维度不能被平均分掩盖 | Provider 完整审计样本与人工相关性 |
| 去 AI 味规则与生成前约束 | 可用 | `DEAI_IRON_RULES`、`deai_metrics.py`；按密度/重复/同构风险，不禁单个标点 | 真人样本误伤率和盲评 |
| 去 AI 味/人文化内容保真 | 可用 | `text_quality.py`、Bootstrap/V7/编辑器统一字符比例与段落保真门 | 真实 Provider 多轮重写 |
| 失败状态、重试和编辑器兜底 | 可用 | App/Progress/WorkspaceDashboard/Editor；节点失败不再显示已完成，应用前预览且保存失败不清理预览 | 生产真实失败注入复测 |
| 本轮自动回归与真实性门禁 | 可用 | 后端 878 passed、138 skipped、1 xpassed；前端 34 passed；build；truthfulness 通过 | 生产部署后 smoke |

运行时代码 `2fba0be` 已部署并通过生产 smoke 与 V7 浏览器走查；真实 Provider 长跑、人工盲评和最终读者体验仍按外部证据单独验收。

## 2026-08-02 融合开发批次（工作树，基线 `94fc731`）

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 全站/按类型扫榜及范围证据 | 可用 | `backend/app/api/v1/ranking.py`、`RankingCenter.tsx`；离线榜单契约回归通过 | 真实平台刷新和平台字段覆盖 |
| 选题候选市场字段与快照来源 | 可用 | `topic_candidates.meta` 复用现有迁移；市场分析回归通过 | 真实榜单样本和人工选题评审 |
| 33 维内部审计 + 7 宏观分数 | 可用 | `backend/app/v7/quality/audit_dimensions.py`、`ReviewEngine`；V7 质量契约回归通过 | Provider 必须真实返回完整 33 项并做长篇质量复核 |
| 跨章状态交接与七域真相投影 | 可用 | `continuity.py`、`truth_store.py`、V7 Director；transition contract 回归通过 | 真实多章运行和人工连贯性评估 |
| 去 AI 味确定性指标与规则学习灰度/回滚 | 已接线 | `deai_metrics.py`、`rule_learning.py`；规则状态机回归通过 | 真实章节样本验证误伤率和读者体验 |

本批工作树尚未提交或部署；“可用/已接线”只代表代码级闭环和离线回归，不代表生产质量验收。

## 2026-08-02 最新单链路决策

质量对比已完成选型：V7 真实 20 章平均 92.0、最低 91.0，V6 平均 79.6、最低 72.0。故正文生成不再维护双轨，V7 为唯一 canonical chain；V6 只承担兼容事实、`contents`、编辑器和导出。

## 2026-08-02 状态真实性修复与生产刷新

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 失败/等待结果不得显示已完成 | 可用 | `7851b7f`；canonical `pending_approval / needs_review / failed` 按真实状态投影到 Bootstrap 节点；历史截图 run 已定向纠正；canonical 回归 10 passed | 更多真实 Provider 运行覆盖 |
| 质量拒绝草稿可见且不可发布 | 可用 | V7 rejected draft 写回 V6 `contents.status=needs_rewrite`，保留质量分、问题和版本快照；代码回归通过 | 生产真实质量长跑与人工盲评 |
| 生产刷新与入口可达 | 可用 | `7851b7f` 已部署；healthz 200；`prod_smoke.py` 15/15 | 真实生产 20 章质量验收 |

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 正文生成唯一链路 | 可用 | `7851b7f` 已部署；`continue`、批量、自动续写、人工重生成和 Bootstrap 首章均委托 V7 Director；生产 smoke 15/15，V7 质量通过后幂等写回 V6 `contents` | 生产 20 章 Provider 长跑 |
| V6 兼容承载 | 可用 | V6 仅作为事实/知识/章节存储、编辑器和导出层；V7 结果保留 `canonical_engine=v7`、run 和 transition provenance | 目标部署环境真实回放 |
| 生成质量目标 | 可用 | V7 真实双轨自动证据优于 V6；本轮代码回归已通过 | 生产 20 章、两位人工盲评；不能标记已验收 |

> 状态只使用：未开始 / 已接线 / 可用 / 已验收。  
> “可用”表示确定性真库链路已通过；“已验收”还要求对应真实 Provider 或生产证据。

| 编号 | 需求 | 前端 | 后端/数据 | 状态 | 当前证据 | 升级门禁 |
|---|---|---|---|---|---|---|
| NOV-G-001 | 用户可注册、登录、退出 | `LoginPage.tsx`、`App.tsx` | `/auth/register`、`/auth/login`、JWT | 已验收 | E2E 主线① + 生产 `novel.xyjin.xyz` 认证 smoke | — |
| NOV-G-002 | 展示八个小说入口（含扫榜选书） | `Layout.tsx`、`App.tsx` | 不改历史数据 | 已验收 | E2E 主线① + visual.spec 截图 + 生产巡检 | — |
| NOV-G-003 | 旧入口迁移、未知入口 404 | `App.tsx`、`NotFoundPage.tsx` | 无 | 已验收 | E2E 主线② + 生产路由 smoke | — |
| NOV-G-004 | 浅深色、主题记忆、响应式 | `ThemeProvider.tsx`、`styles.css` | 浏览器偏好 | 已验收 | 单测 + visual.spec 桌面/手机截图 + 生产巡检 | — |
| NOV-G-005 | 公共页多书切换且作品、run、章节、编辑器、审阅一致 | `Layout.tsx`、`App.tsx` | contents、latest run；账号隔离缓存 | 可用 | E2E 主线⑤：两本真书 + 延迟旧请求，快速切换后编辑器/审阅保持最后选择；选择器仅三个公共页；确定性 E2E 5 passed / 4 skipped | 同提交 CI；生产切书 smoke |
| NOV-H-001 | 首页显示真实书籍和运行状态 | `WorkspaceDashboard.tsx` | `/library/books`、`/runs/latest` | 可用 | 单测、E2E 空状态 | 有书/有运行生产证据 |
| NOV-W-001 | 输入创意、题材、风格、篇幅并启动 | `Wizard.tsx` | Bootstrap API、真实 Gateway | 已验收 | protected E2E 1 passed (2026-07-28, run 8f1fd62b, 19 ai_calls)；修复 step 校验 bug；生产 healthz /wizard smoke | — |
| NOV-W-002 | AI 策划后必须人工确认书名 | `Progress.tsx` | `human_confirm_title` 节点 | 已验收 | protected E2E 1 passed (2026-07-28, run 8f1fd62b, 19 ai_calls)；waiting_human 真实出现并点选定名；生产 smoke | — |
| NOV-P-001 | 展示真实节点、产物、失败和重试 | `Progress.tsx` | Runs、nodes、retry API | 已验收 | 单测(Progress.test.tsx：空态、人工定名、失败原因+重试打到 `/runs/{id}/nodes/{key}/retry`)；protected E2E 小说主线③ 运行中真实节点截图(protected-01)；小说主线⑤ 人工定名(protected-02)/19 节点完成(protected-03, 19 ai_calls)；生产 smoke | — |
| NOV-L-001 | 书库加载、搜索、筛选、排序 | `BookLibrary.tsx` | `/library/books` | 可用 | 真实空态与建书 E2E | 分页/筛选 E2E |
| NOV-L-002 | 详情、章节目录和导入 | `BookLibrary.tsx` | novel/detail/import API | 可用 | E2E 主线③ | 生产 smoke |
| NOV-L-003 | TXT/MD 导出 | `BookLibrary.tsx` | export API | 已验收 | protected E2E 1 passed (2026-07-28, run 8f1fd62b, 19 ai_calls)；导出正文断言通过；生产 smoke | — |
| NOV-E-001 | 编辑章节并真实持久化 | `Editor.tsx`、`RichEditor.tsx` | `PUT /contents/{id}`、versions | 已验收 | E2E 主线③刷新持久化；生产 smoke | — |
| NOV-E-002 | AI 编辑先预览再应用或放弃 | `Editor.tsx`、`editorPreview.ts` | content AI API、版本保存 | 已验收 | 3 条单测；protected E2E 1 passed (2026-07-28, run9, 2 ai_calls)：续写→预览→放弃后原文不变→应用→版本恢复；生产 smoke | — |
| NOV-E-003 | AI 失败不覆盖原文 | `App.tsx`、`Editor.tsx` | Gateway 显式失败 | 已接线 | 代码与单测边界 | 浏览器失败注入 E2E |
| NOV-E-004 | 版本查看与恢复 | 编辑器版本区 | versions API | 已验收 | protected E2E 1 passed (2026-07-28, run9)：按版本 id 恢复后正文 A 回归、AI 建议消失、DB content.body 确为 [A]；生产 smoke | — |
| NOV-R-001 | 无审阅证据时不伪造评分 | `Review.tsx` | run review outputs | 已验收 | E2E 主线④；生产空态 smoke | — |
| NOV-R-002 | 展示七维、一致性、连续性和问题证据 | `Review.tsx` | review/consistency nodes | 已验收 | protected E2E 1 passed (2026-07-28, run 8f1fd62b, 19 ai_calls)；protected-06 截图；生产 smoke | — |
| NOV-R-003 | 审阅建议先预览再由用户应用 | `Review.tsx` | repair preview/apply API、签名与并发门禁 | 已接线 | Repair 定向 15 passed；前端预览/确认 2 tests；后端全量 781 passed；浏览器验证无密钥时显式失败且不改正文；提交 `6f7184c` / Actions `30447533339` 五项全绿 | 真实 Provider 正向预览→应用 |
| NOV-S-001 | BYOK 只保存在当前会话 | `Settings.tsx` | 请求 Header 优先 | 已验收 | E2E 主线④；生产请求验证 | — |
| NOV-S-002 | 创作知识导入、导出和统计 | `Settings.tsx` | knowledge/stats API | 已接线 | 页面/API 接线 | 真库数据操作 E2E |
| NOV-S-003 | 修改密码 | `Settings.tsx` | auth password API | 已接线 | 页面/API 接线 | 正负例 E2E |
| NOV-Q-001 | 单元、构建和确定性主链门禁 | Vitest、Playwright | 真 PostgreSQL/FastAPI | 已验收 | 提交 `07a8c0f`：本地后端 761 passed / 9 skipped / 1 xpassed、前端 12 passed、build、E2E 4 passed / 4 skipped、三项静态校验；Actions `30439322188` 五项全绿 | 后续批次继续维持同提交 CI |
| NOV-Q-002 | 真实 AI 新 UI 全链 | protected Playwright | DeepSeek、run/ai_calls | 可用 | protected “小说主线⑤” 1 passed (5.2m)；run `955d4719-8e21-4043-8a3e-2352c06c0ce2` 20/20 nodes、22 succeeded ai_calls；Writer 含 Prompt Compiler 三层指令，最终一致性含五维读者体验；提交 `5c544ff` / Actions `30445384633` 五项全绿 | Repair Engine 正向 Provider 预览应用；最终生产 smoke 后提升已验收 |
| NOV-D-001 | 当前版本推送和部署 | GitHub Actions、Docker | 生产基础设施 | 可用 | `7851b7f` 已推送并部署到 `novel.xyjin.xyz`；迁移到 `nc_v7_novel_project_mapping`；生产 smoke 15/15 | 生产真实 20 章双轨与人工盲评不属于部署 smoke |

## 更新规则

- 修改需求或实现时，同一批次更新本表。
- 状态提升必须在“当前证据”中写入命令、测试、run、提交或生产验证。
- 只存在代码、路由、按钮或类型定义时，最高为“已接线”。
- 失败或跳过的测试不能写成通过。

## 2026-08-02 V6/V7 质量合并追踪补充

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| V7 章节交接契约与 V6 contents 桥 | 可用 | `backend/app/v7/integration/v6_bridge.py`；新增质量回归通过；仅质量通过章节写入 V6 | 真实数据库写回、书库/编辑器/导出端到端 |
| V7 85 分跨章质量门 | 可用 | `backend/app/v7/integration/quality.py`、StoryDirector 二次复核与最多两次重写 | 真实 Provider 多章长跑、人工盲评 |
| V6 主链最终人文化 | 已接线 | `chapter_loop.py` 在修复/重规划后调用真实 `bootstrap.final_humanize` 并做最终 review | 真实 Provider/数据库环境复测 |
| V6 事实冲突局部修复 | 已接线 | `write_fact_reconcile` 返回精确修复项；主链应用、二次审查、失败转 `needs_review` | 真实冲突样本与回滚/写回证据 |
| V6/V7 成本与 Prompt provenance 统一 | 可用 | `UnifiedAIGateway` 收敛 Provider transport；V6/V7 写 `ai_execution_ledger`；V7 `ensure_runtime_version` + `record_runtime_execution` 写 Prompt provenance；67 项目标回归通过 | Alembic migration、真实播种/回放、V6/V7 账本对账和生产长跑 |

## 2026-08-02 本地收口证据更新

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 统一 Provider transport（V6/V7 sync/async/stream） | 可用 | `unified_gateway.py`；统一 Gateway 回归、流式 SSE 回归通过；E2E 真实后端运行 | 真实 Provider 多章回放 |
| Prompt provenance 与 runtime seed | 可用 | `alembic current` = `nc_v6_v7_runtime_ledger (head)`；seed 8 个 runtime Prompt，重复执行幂等 | 真实 Provider 执行记录与生产审计 |
| 跨版本成本账本 | 已接线 | `ai_execution_ledger` migration、V6/V7 写入、项目范围 `/ledger` 和日期/任务统计回归 | 真实 V6/V7 回放对账、生产成本核对 |
| V7 → V6 章节质量桥 | 可用 | 85 分质量门、`transition_contract`、幂等 contents bridge、V6 二次复核回归 | 真实生成后书库/编辑器/导出链路 |
| 生成质量验收 | 已接线 | 全量后端 843 passed；E2E 18 passed/9 skipped；20 章脚本 dry-run 可执行 | 真实 20 章双轨、跨章指标、去 AI 味差分、两名编辑盲评 |
| 强制 AI development gate | 已接线 | AST 真值、交付声明、空白检查通过；强制脚本 exit 3 的宽泛告警已在 KI-005/015 解释 | 规则清零或完成 CI 级告警收敛 |

## 2026-08-02 继续整改追踪补充

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| ai-workbench 参考落地 | 可用 | `docs/AI_WORKBENCH参考评估_20260802.md`；情绪目标、钩子、分层去 AI、读者体验已接入 V7/V6 提示与契约 | 真实长篇与人工盲评 |
| V7 读者体验证据 | 已接线 | V7 Review 强制五项字段并持久化到 transition contract；目标与全量回归通过 | 真实 Provider 样本的人感相关性 |
| V7 novel→V6 project 映射 | 可用 | `nc_v7_novel_project_mapping`；本地回填 6994 条；跨 project pair 拒绝测试通过 | 生产迁移与真实书库/编辑器/导出回写 |
| Prompt 管理权限 | 可用 | V7 Prompt router 使用 admin read/write guard；权限结构测试通过 | 双用户生产接口回归 |
| 当前质量回归 | 可用 | 后端 843 passed/138 skipped/1 xpassed；前端 32 passed；E2E 最新复跑 17 passed/10 skipped | Provider 20 章双轨、人工盲评 |

## 2026-08-02 真实 Provider 20 章双轨更新

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| V6/V7 真实双轨自动回放 | 可用 | 真实 DeepSeek、本地 PostgreSQL/Redis/Celery；两轨各 20/20；V6 平均 79.6、V7 平均 92.0 | 两位独立人工盲评 |
| 跨版本成本账本 | 可用 | `ai_execution_ledger` 369/369 成功、0 失败、3.190506 元；V6/V7 分项可对账 | 目标部署环境成本核对 |
| Prompt provenance | 可用 | V6 7 个、V7 6 个 Prompt identity，版本、usage、task type 均可追溯 | 生产审计回放 |
| V7→V6 书库/编辑器/导出 | 可用 | 20 章 `contents`、mapping、编辑器、完成度、TXT/Markdown/EPUB 真实接口证据 | 目标部署环境回放 |
| 人工盲评 | 已接线 | 20 个匿名 case 和评分模板已生成 | 0/20 case 达到两位评审 |
| 生成质量目标 | 已接线 | 自动连续性、审稿、去味和重复风险指标已生成 | 人工评分及人感差异报告 |

## 2026-08-02 生产部署证据

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 当前提交生产部署 | 可用 | `7851b7f`；Docker 应用容器重建；迁移 head；公网 healthz 200 | 生产 20 章质量长跑 |
| 生产用户入口 | 可用 | 生产 smoke 15/15；生产 Playwright 走查 4/4 | 真实 Provider 生成质量和人工盲评 |
