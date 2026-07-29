# Starlume AI — 真实进度

<!-- delivery-claims: strict -->

> 更新：2026-07-29（V3 接手复验与 CI 修复）｜ 权威摘要 ｜ 状态遵循《23-AI开发边界与交付真实性规范》

## 2026-07-29 V3 接手复验与 CI 修复

- 基线：同步后 `main = origin/main = f8e343c`，生产文档可确认的最近部署仍为 `91bcf9b`。
- 真实缺陷：章节质量证据会无条件声称 pacing/story-arc 来源；现改为仅记录实际采样来源，并补可选来源回归。
- 测试契约：Bootstrap 已为 20 节点（19 AI + 1 人工门禁），同步更新完整流程夹具、节点断言与 BYOK 引用参数；不恢复已从小说 UI 退役的 Costs/预算入口。
- 本地门禁：后端 `761 passed, 9 skipped, 1 xpassed`；前端 `12 passed`；构建通过；确定性 E2E `4 passed, 4 skipped`；交付声明、AI 真实性、前后端契约与 `git diff --check` 通过。
- 当前状态：**可用**。
- 未完成门禁：新 CI 同版本全绿、真实 Provider 复验与部署。

## 2026-07-28 生产部署与线上热修复

> 部署目标：将 Starlume 新 UI 推上生产 `novel.xyjin.xyz`；处理用户反馈的两个线上阻断问题。

### 部署到 43.156.17.78

- 只读扫描后确认：Compose 在 `/opt/NovelCraft-Personal-Studio/`，旧运行 commit `bf1a377`，nginx 443→frontend:8090，无 schema 迁移风险。
- 处理远程已有 5 个 E2E 提交的分叉，仅把文档提交 rebase 到 `origin/main`，全量重建并启动。
- 结果：`https://novel.xyjin.xyz/` 200；`/api/v1/healthz` 全绿（AI key/DB/redis/worker）；当前生产 commit `91bcf9b`。

### 热修复 1：DeepSeek 模型报错

- 现象：创作向导提示"模型 deepseek-v4-flash 不在 Enterprise 套餐允许范围"。
- 根因：`backend/app/config.py`、`gateway.py`、`api/v1/config.py` 默认模型硬编码为 `deepseek-v4-pro`；`db.py` 启动迁移把 `deepseek-chat/reasoner/v4-flash` 强制覆盖成 `deepseek-v4-pro`，且生产 `.env` 未设 `DEEPSEEK_MODEL`。
- 修复：
  - 所有默认值改为 `deepseek-chat`。
  - `db.py` 迁移改为把不可用模型（v4-pro/v4-flash/reasoner）修复回 `deepseek-chat`，兼治已被污染的 `model_routes`。
  - 生产 `.env` 追加 `DEEPSEEK_MODEL=deepseek-chat`。
- 提交：`a790f83`；部署后 healthz / wizard 模型报错消除。

### 热修复 2：扫榜入口消失

- 现象：用户反馈"扫榜页面没了"。
- 根因：`App.tsx` 的 `LEGACY_TAB_REDIRECTS` 把 `ranking` 重定向到 `wizard`；`RankingCenter` 组件与后端 `/api/v1/ranking/*` 均存在但未挂载到主路由；`Layout.tsx` 导航里也没有扫榜入口。
- 修复：
  - `App.tsx`：移除 `ranking→wizard` 重定向；`ranking` 加入 `PUBLIC_TABS`；渲染 `<RankingCenter />` 并提供 `onBookCreated` 回调（完成后跳 progress/书库）。
  - `Layout.tsx`：`NAV_ITEMS` 加入"扫榜选书"。
- 提交：`91bcf9b`；部署后侧边栏可见"扫榜选书"，可进入 RankingCenter 执行扫榜/AI 分析/生成书。

### 遗留 E2E 收口状态

- 注册限流退避已补并提交（`cb37e15`），稳定了真实 AI E2E 的连续注册。
- 全链 E2E（①②③④⑥⑦）已通过 6 passed, 1 skipped；七页面截图集 15 张已生成；小说主线⑤ 富状态截图因 `write_polish` 节点 AI 输出格式偶发 `invalid_output` 正在 retry 取证。

## 2026-07-28 Starlume AI 小说主线重构（已部署）

> 本轮按已确认的 Vibe Coding 任务契约执行：小说优先、非小说模块从 UI 隐藏但不删除数据/源码、用户可见品牌统一为 Starlume AI、关键 AI 结果必须人工确认、失败不得伪装成功。生产已部署，状态以本表及 `docs/KNOWN_ISSUES.md`、`docs/REQUIREMENTS_TRACEABILITY.md` 为准。

### 2026-07-28 protected 真实 AI 全链 E2E 首次通过（未完成顺序 item ①）

- 注入真实 `DEEPSEEK_API_KEY`（gitignored `.env.local`，不入库）后，`npx playwright test e2e/main-chain.spec.ts --grep "protected"` → **1 passed (13.2m)**。
- 过程中修复 3 个真实阻断：① `Wizard.tsx` HTML5 step 校验拒绝全部预设字数（min=5000/step=10000 不相容，改 min=10000）；② `scripts/e2e-backend.sh` 缺 Celery worker（任务入队无消费者，改双进程）；③ `novelcraft_dev` 迁移落后 6 版（`ai_calls` 缺 `user_id` 致预算断言崩溃，`alembic upgrade head`）。
- 证据：run `8f1fd62b-5ad8-4208-8fd8-887f33425631` succeeded；19 条真实 `ai_calls`（¥0.1889，write_polish 实测 95.6s）；`waiting_human` 人工定名断点真实出现并点选；产物《午夜头条》第一章 2350 chars；截图 protected-02..06。
- 状态提升（据 ACCEPTANCE_CRITERIA）：NOV-W-001/W-002/L-003/R-002 已接线 → **可用**；生产验收仍需部署 smoke（KI-002）。
- 默认无 Key 门禁不变：`test.skip` 保留，仍为 4 passed + skipped。

### 2026-07-28 AI 编辑真实浏览器闭环 E2E 通过（未完成顺序 item ②）

- 注入真实 `DEEPSEEK_API_KEY` 后，`npx playwright test e2e/main-chain.spec.ts --grep "小说主线⑥"` → **1 passed (29.2s)**。
- 闭环覆盖：续写（真实 DeepSeek `editor.continue`）→ 预览出现且正文不变 → 放弃建议后原文保持不变 → 再次续写 → 应用到草稿（正文含 AI 建议）→ 按版本 id 恢复「应用前原文 A」版本 → 原文回归、AI 建议消失。
- 过程中定位并修复真实缺陷：E2E 用脆弱的 `nth(index)` 点击，在版本历史 UI 列表未刷新时点到 `body={}` 的 `offline_save` 版本，恢复后编辑器变空。修复：`Editor.tsx` 恢复按钮加 `data-version-id={v.id}`，测试改为按真实版本 id 点击并 `waitFor` 按钮可见。`restore_version` 应用逻辑本身正确（db.py 解码快照 body 为 `[{text:"A"}]`，写回 content.body）。
- 证据：run9 两次真实 `ai_calls`（deepseek-v4-pro，succeeded）；截图 protected-07/08/09；恢复后 `content.body` 经 API 取证确为 `[{text:"档案室..."}]`，编辑器 DOM `<p>档案室...</p>`。
- 状态提升：NOV-E-002、NOV-E-004 已接线 → **可用**；KI-003 收口为可用；生产验收仍需部署 smoke（KI-002）。NOV-E-003（AI 失败不覆盖原文）仍为已接线，待失败注入 E2E。

### 2026-07-28 创作进度真实节点浏览器证据（未完成顺序 item ③）

- 新增聚焦 E2E `小说主线③：创作进度运行中真实节点浏览器证据（protected）`：启动 run 后轮询到「生成中」节点/「创作中」状态即截图，约 3.4s 命中，生成 `protected-01-progress-running.png`（真实浏览器，运行中节点 + 完成度文案 + 真实节点标题）。该用例与既有 `小说主线③：建书→详情→导入章节→编辑→保存→重载持久化`（非 protected）同批通过。
- `Progress.test.tsx` 补失败/重试单测：失败节点显示失败原因与「重试此步骤」按钮，点击后 `apiRaw` 打到 `/api/v1/runs/{id}/nodes/{key}/retry`（POST）；另保留空态与人工定名单测。单测 11 → **12 passed**。
- 浏览器证据汇总：运行中(protected-01) + 人工定名(protected-02) + 19 节点完成态(protected-03，19 ai_calls) 来自 KI-001 run 8f1fd62b；失败/重试由单测 + 重试端点覆盖（真实浏览器失败注入需强制节点失败，留作后续）。
- 状态提升：NOV-P-001 已接线 → **可用**；生产验收仍需部署 smoke（KI-002）。

### 2026-07-28 AI 交接 checkpoint

- 已新增 `docs/AI_HANDOFF.md`、`REQUIREMENTS_TRACEABILITY.md`、`KNOWN_ISSUES.md`、`ACCEPTANCE_CRITERIA.md`、`AI_CONTINUITY.md`，并把交接读写责任加入 `AGENTS.md`；项目状态不再只依赖聊天记录。
- 最新前端证据：`npm test` 为 **11 passed**；`npm run build` 通过；`npm run test:e2e` 为 **4 passed, 1 skipped**。确定性真库链已覆盖注册/七入口、旧路由/404/手机导航、建书/详情/章节导入/编辑保存/刷新持久化、审阅无伪分和小说设置。
- protected 新 UI 真实 DeepSeek 链因本机没有 `DEEPSEEK_API_KEY` 被明确跳过，不能计入通过；后端既有 19/19 生产 run 不能替代新 UI 浏览器验收。
- 修复同轮浏览器发现的交互缺陷：侧栏悬浮导航后会收起；用户固定展开时正文区让位 260px，不再遮挡书库首卡片。
- 当前 Starlume 新 UI 尚未推送、尚未部署；生产仍不得作为本轮新 UI 证据。

| 范围 | 状态 | 本轮证据 | 未完成门禁 |
|---|---|---|---|
| 品牌、浅深色主题、桌面/平板/手机导航 | 可用 | `ThemeProvider.test.tsx`；1280×720 与 390×844 浏览器视觉检查；系统主题、手动切换与记忆已接线 | 全页面截图集、生产验收 |
| 登录/注册、全局错误、404、旧入口迁移 | 可用 | 本地真实注册进入工作台；`#/missing-page` 显示明确 404；`#/ranking` 迁移到 `#/wizard` | 完整认证 E2E、生产 smoke |
| 小说首页 | 可用 | 真实 `/api/v1/library/books`；加载/空/错误/重试状态；`WorkspaceDashboard.test.tsx` 覆盖真实字段与失败路径 | 有书/有运行数据的生产视觉验收 |
| 创作向导 | 已接线 | AI Key 缺失时明确阻断；输入校验、题材/风格/篇幅与真实 `startBootstrap` 保持接线；桌面/手机视觉检查 | 使用真实 Key 从新 UI 启动并完成 T4 E2E |
| 创作进度与人工书名门禁 | 已接线 | 移除前端虚构 ETA；真实节点状态/错误/重试/产物；`Progress.test.tsx` 覆盖空状态与人工选名 | 运行中、失败、19 节点完成态的浏览器 E2E |
| 非小说模块主线清理 | 可用 | 非小说页面不再由 `App.tsx` 导入或渲染；源码与数据保留；前端主包约 404 KB → 277 KB | 后续确认不再有隐式入口 |
| 书库/详情 | 已接线 | 书库真实加载/搜索/筛选/排序/批次/导入/导出/删除能力保留，空态与页面样式统一 | 有书数据的详情、操作与移动端 E2E |
| 章节编辑器 | 已接线 | 移除重复的外层三栏；AI 结果改为预览后应用/放弃；`editorPreview.test.ts` 覆盖润色、续写、整章重写且原文输入不变；无章节空态浏览器检查 | 真实 AI 生成→预览→应用→版本恢复 E2E |
| 审阅与一致性 | 可用 | 原 `Review` 占位面板已替换为真实评分/七维检查/问题/优势/连续性/时间线/人物弧线；无证据时不填默认分；浏览器空态检查 | 有真实审阅证据的桌面/移动端 E2E |
| 小说设置 | 可用 | 移除热点/发布/预算/Prompt 等非小说入口；保留真实 BYOK、项目知识导入导出、统计和改密；桌面浏览器检查 | 移动端与数据操作 E2E |

本轮门禁：

- `npm test`：11 passed。
- `npm run build`：通过；仅保留 `api.ts` 动静态混合导入与空 react chunk 的既有构建警告。
- `git diff --check`：通过。
- `bash scripts/ai_development_gate.sh`：AST 真实性与 whitespace 通过，但宽泛 suspicion scan 命中测试 mock、输入 placeholder、历史非小说 fallback 字段/空集合等，脚本按设计返回 3。当前不得据此宣称全项目完成；最终交付前需逐项整改或书面说明后以 `GATE_ALLOW_WARNINGS=1` 复验。

## 2026-07-28 主创作链抢救与生产验收

- **状态：已验收（T5，单本隔离验收）**。生产真实 DeepSeek 从创意规划、忠实度审计、人工定名、分卷/章节/场景蓝图、初稿、自审、润色、篇幅检查、事实核对、人文化、七维一致性到连续性审计，19/19 节点全部 `succeeded`。验收 run：`db21a95f-1be5-4232-bb12-84ab98e91dda`，完成时间：2026-07-28 05:10 UTC。
- **生产缺陷与修复**：润色段落合并误判改为比例门禁；人文化增加正文/段落保留门禁和最多三次真实 Provider 反馈修订；修复提示词安全清洗把内部章节正文统一截断到 1500 字的问题，内部 `_chapter_body` 保留注入过滤并放宽到 12000 字。
- **证据**：最终章节 11 段、约 2630 正文字符；32/32 条 `ai_calls` 成功；96 条审计事件保留。隔离验收书与章节、9 条知识项已按精确 ID 软删除，运行与调用账本保留。
- **代码与门禁**：主线提交 `bf1a377`（此前修复链 `44eac3c`、`eb6c72b`、`ac225af`、`220f9a5`）；本地后端 `657 passed, 9 skipped, 1 xpassed`；GitHub Actions run `30330421031` 的 backend/security/frontend/frontend-test/e2e 全绿；生产 `https://novel.xyjin.xyz/api/v1/healthz` 返回数据库、Redis、worker、DeepSeek 配置全部正常。
- **边界（T5 实测）**：本次证明单本完整创作主链可用且已通过真实 Provider 验收；不等同于百章长跑、真实内容平台发布回执或所有外部热点源均已验收。

## 2026-07-17 V2.0 全面升级

### 用户10问题整改

| # | 问题 | 状态 | 证据 |
|---|------|:--:|------|
| 1 | 番茄全榜 | 🧪 | /api/rank/list 7本巅峰榜 + 37分类API 1117本。Playwright已集成但VPS内存不足跳过 |
| 2 | 起点/纵横100+ | 🧪 | 起点7榜合并44本（分页不生效），纵横33本。默认200可配环境变量 |
| 3 | 编辑器排版 | 🧪 | novel-prose.css(440行) + RichEditor.tsx重写(329行)。CSS已打入Docker bundle |
| 4 | 编辑器UI | 🧪 | Editor.tsx增强(263行)：左目录/AI面板/状态栏/全屏/夜间/专注 |
| 5 | 去AI味 | 🧪 | deai_pipeline.py(223行)七层管线 + deai.py API(165行)。未真实DeepSeek验证 |
| 6 | 热点多平台 | 🧪 | 8平台fallback URL。B站API实测通过。头条/小红书/抖音需代理 |
| 7 | 热点文库 | 🧪 | articles CRUD在hotspots.py + HotspotDashboard文库Tab |
| 8 | 书库删除 | ✅ | 7端点(单本/批量/章节删除) + 前端checkbox/确认弹窗；前端测试与 bundle 实测 |
| 9 | 十层分析 | 🧪 | ten_layer_analysis.py(793行) + /ranking/analyze端点。platforms自动去重 |
| 10 | 选题池 | 🧪 | bookmark/delete/batch-delete端点 |

### 新增功能

| 功能 | 文件 | 状态 |
|------|------|:--:|
| DashboardV2 首页 | DashboardV2.tsx(613行) | ✅ |
| 全局玻璃拟态主题 | global-v2.css(413行) + ThemeProvider；前端构建测试通过 | ✅ |
| 仿写HTML提取 | imitation.py _extract_text() | ✅ |
| 一键采集所有平台 | ranking.py /scan-all + 前端按钮 | ✅ |
| 多平台聚合分析 | ranking.py /analyze + 前端UI | 🧪 |
| 新平台: SF轻小说 | ranking_adapter.py fetch_sfacg_ranking() 43本 | ✅ |
| 新平台: 潇湘书院 | ranking_adapter.py fetch_xxsy_ranking() 41本 | ✅ |
| 平台替换: QQ阅读/晋江 | 替换七猫/17K/刺猬猫(JS-SPA不可采)；适配器测试覆盖 | ✅ |

### 验证基线

- 后端: `pytest` → 565 passed, 9 skipped
- 前端: `npm run build` → ✓ built (tsc -b + vite)
- 部署: VPS Docker frontend + systemd API → 200 OK
- 提交: main @ c5b3463
>
> **治理说明**：此前版本宣称"20/20 任务全部完成、6/6 深度融合、8/8 整合、真实 Provider T3/T5 通过、真实源 7 天稳定运行、浏览器 E2E 验收通过"，均无《23》§6 要求的验收证据（commit/命令/日期/输出），且"7 天 T5"与文档同日更新在时间上不可能成立。按《23》§8 全部降级为证据可查的状态；重建证据台账前不得恢复 ✅。外部审计报告（2026-07-11）的 §三/P1-6 亦指认了同一问题。
>
> **开发前强制门禁**：任何后续开发、整改、审计修复、提交前，必须先阅读并遵守 `docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md`。未通过该规范的状态口径、反撒谎扫描、证据等级和交付格式时，不得使用高等级交付口径。

## 当前主线 (main)

### 2026-07-17 WIP 收尾入库 + main 合并 + 整体部署

- **WIP 收尾（@a6ed0da）**：上一会话遗留后端 WIP 逐项审查后入库——章节长度硬门禁（3 次真实重试带反馈）、七维质量证据持久化到章节 meta、移除 analyze_hotspots 模板伪 AI 输出、gateway editor/style 空输出防护、人工选名门禁（"待命名作品"占位）、`/runs/latest` 恢复端点、智能体 stale 状态识别、书库字数修真、知识库嵌入连接泄漏修复、versions.reason TEXT 迁移、nginx /api 直连（线上已提前生效，repo 补记）。
- **合并 main（@27249e4）**：榜单三修复（起点 script tag/番茄 snake_case/番茄全分类）+ CI allowlist 并入分支；overseas_complete.py 冲突取分支侧（审计整改后继版），同步清理 main 侧遗留的 generate_consistency_report 死豁免条目。
- **验证**：合并树全量 `pytest` → **565 passed, 9 skipped**（本地需 `NOVELCRAFT_TEST_REDIS_URL=redis://localhost:6379/15`，否则 fail-closed 503 导致误报）；truthfulness/delivery 门禁通过；前端构建通过。
- **部署**：生产服务器从 main+分支前端的混合状态切换为整体跟随分支 @27249e4，api/worker/beat/frontend 全部重建；基础设施侧确认用户已清理家中 frpc 重复 `nc-proxy` 段（frps 日志 0 次 port already used，代理 200）。

### 2026-07-16 全量回归 + 生产浏览器巡检与修复轮

- **全量回归**：本地 `pytest` → **565 passed, 9 skipped**（CI 等价环境；此前一次失败为本地 `DEEPSEEK_MODEL` 注入所致误报，CI 环境复跑通过）；`npm run build`（tsc+vite）通过；`verify_ai_truthfulness.py`、`verify_delivery_claims.py` 通过；alembic 单头 `nc_versions_reason_text` 全量迁移通过。
- **生产浏览器巡检（真实登录态，Chrome 驱动）**：19 个页面全部渲染并核对控制台/网络请求；扫榜中心真实起点/番茄快照与失败详情展示正常；书库、审阅七维雷达、编辑器 TipTap、成本追踪 13 次真实 DeepSeek 调用、智能体任务计数等均为真实数据。
- **修复 1（生产配置）**：服务器 `.env` 缺 `NOVELCRAFT_ADMIN_EMAILS` → `/admin/settings` 403 且前端产生未捕获异常；已补配并按 `docker-compose.prod.yml`（env_file 全量注入）正确重建 api/worker，登录态实测 200。
- **修复 2（后端 @9c4abc1 main / @535dea6 分支）**：`GET /admin/settings` 由写级 `require_admin` 改为 `require_admin_reads`（QA-003 口径，与 providers/model-routes/prompts 一致）。
- **修复 3（前端 @d72f2cf 分支）**：run 终态（succeeded/failed）停止 2 秒轮询；切换 Tab 滚回顶部；Settings 管理接口失败如实提示而非未捕获异常；同轮把此前已构建部署到生产（bundle `index-D_diNxCO`）的前端 WIP 入库补齐溯源。
- **修复 4（基础设施）**：热点采集全源超时根因定位——`jp.xyjin.xyz:8888`（frps 隧道→国内 tinyproxy）被互联网扫描者当开放代理滥用打满，且 frps 存在僵尸 `nc-proxy` 注册占用端口；已 ufw 白名单收紧 8888 仅允许 43.156.17.78、重启 frps 清除僵尸注册。实测 `/api/v1/hotspots` 恢复 200、60 条真实百度热点，看板正常渲染。遗留：国内 frpc 配置存在重复绑定 8888 的 `nc-proxy` 段，建议清理；知乎/微博 ajax 需有效 Cookie。

- **创意拆解模块化**：所有新书统一执行“原始需求 → 创作圣经 → 市场/故事/玩法/世界/人物/冲突规划”，不再把排行榜建议标题当成已确认标题。规划结果包含 `source_facts`、`design_additions`、`forbidden_changes`、长篇阶段、篇幅和内容配比。
- **规划忠实度硬门禁**：`plan_idea` 每次真实 DeepSeek 输出后，新增独立 `audit_plan_fidelity` 调用逐项对照原始需求；年龄、年份、职业、设备、目标字数、内容主次和前三章事件存在矛盾/遗漏时，自动反馈并重新调用真实 AI，最多三轮；三轮仍不合格则节点 `failed`，不得进入选名或继续写作。用户要求后续生成的分卷总纲、前 N 章细纲、章节正文等记录在结构化 `downstream_deliverables`，由后续模块执行，不在策划节点伪装已产出。每轮策划与审计均写 `ai_calls`，没有 mock/fallback。
- **人工选名**：面向用户的开书入口固定在 `human_confirm_title` 停下，展示 3–10 个候选；支持重新生成候选、填写反馈、自定义书名。用户确认前不进入蓝图和章节生成。
- **当前证据**：相关回归 38 passed；全量后端 `557 passed, 9 skipped`；后续幂等恢复专项 24 passed。生产 run `9a5a00b7-f806-43db-9f8a-452a86211966` 使用 DeepSeek `deepseek-v4-pro` 完成三轮“策划→独立审计”纠偏，最终 `score=100 / contradictions=[] / omissions=[]`；随后市场、故事模式、核心玩法、世界观、人物、冲突图谱均以 attempt 级新幂等键重新真实调用，工作流停在 `waiting_human/human_confirm_title`，未自动选名。内置浏览器与当前 Chrome 均无 NovelCraft 登录态，只能到登录页，因此登录后 T4 视觉验收仍未完成，当前状态保持“已接线 / 生产 T3 已验证”。

### 2026-07-14 待验收推进轮证据（部分完成/骨架 → 待验收）

按《24》顺序推进，每模块独立提交并绑定测试证据；全部状态最高为 🧪 待验收，未标任何 ✅：

- **NC-LIB-002/003（@9d1786f）**：`/library/books` 服务端检索(q)/状态筛选/白名单排序（含 SQL 注入回退负例）；前端「最近编辑」排序；编辑器 3s 防抖自动保存（脏检查、冲突处理期间暂停）。`test_library_contract.py` 2 passed。
- **NC-HM-001/002/003（@9d1786f）**：hm_content 4 个真实 AI 函数首次获得产品入口（platform-match/title-variants/video-script/material-suggestions + Dashboard 选题工具箱）；去重/趋势/时效评分与可恢复工作流回归。`test_hm_media_pipeline.py` 7 passed。
- **长篇一致性（@7481791）**：卷级门禁 + 批量生成 409 enforcement + 百章真库压力 + 摘要失败显式化。`test_long_novel_consistency.py` 7 passed。
- **发布中心（@df778e4）**：指标回流 sweep（beat 6h）+ 状态机/60s 调度行为测试。`test_publish_center.py` 4 passed。
- **融合与骨架项目（@4a27eb9）**：事件账本/事实链负载修复与产品端点、事实事务接入真实 reconcile、分层规划/审计/humanize/insprira/BrowserAct removed 诚信回归。`test_skeleton_fusion_projects.py` 5 passed + `test_fusion_deep.py` 行为对照补强。
- **诚信机器门禁（本轮）**：新增 AST 级 `scripts/verify_ai_truthfulness.py` 并接入 `scripts/ai_development_gate.sh` 与 GitHub Actions；拦截 AI 命名函数绕过 gateway、硬编码 `wired/available/status=active`、固定伪生成模板。新增 `test_truthfulness_gate.py` 负例，确认坏代码会被挡下。
- **融合状态证据驱动（本轮）**：`/fusion/status` 的能力状态由当前用户项目最近 30 天 `ai_calls` / workflow audit evidence 倒推：`verified` / `wired_unverified` / `missing` / `removed`；没有真实成功记录不再计入 verified。新增回归断言 `book_analysis` 成功记录可把 book analyzer 从 `wired_unverified` 升为 `verified`。
- **NC-SEA 出海审计整改（本轮）**：补齐 `translate_segment`/`cultural_localize`/`localize_names` 输出契约与 `overseas.localize_names` prompt；合规检查由裸关键词升级为确定性规则引擎（多语言/别名 pattern，返回 matched_rules）；`publish_overseas` 写入真实 project_id；`/translate` 与 `/overseas/publish` 端点补项目/内容权限和 Provider 失败显式 502；新增 `test_overseas_complete.py`，覆盖合规、术语覆盖、发布项目血缘、API 权限、真实 DeepSeek 翻译 provenance。
- **NC-HM-001 历史热点回填（本轮）**：新增 `/hotspots/history/backfill` 与 `/hotspots/history`，支持在“设置 → 平台连接”或环境变量配置 `history_url`（支持 `{date}`）后按真实授权归档源回填近 7 天热点快照；无历史源时返回 `unsupported`/502，不用当前热点伪造历史。`test_hotspot_history_backfill.py` 覆盖 7 天日期血缘、跨天同标题保留、无源不落库、接口 502。
- **NC-SC-001 扫榜采集闭环（本轮）**：新增 `/ranking/capture-import` 与 `/ranking/snapshots/{id}/confirm-capture`；前端导入 JSON 可自动识别番茄 OCR / 起点用户会话 / 可见浏览器采集工件，保留 screenshot/artifact/置信度证据；低置信 OCR 自动标 `needs_review` 并阻断 AI 分析，owner/editor 确认后放行；起点 challenge / 番茄 OCR required 等非成功状态形成失败快照，不返回空成功。`capture_ranking.py` 已升级为自动优先：DOM 提取 → 番茄私有码本机 Tesseract OCR 尝试 → 缺 OCR/挑战/结构漂移输出显式工件，支持 `--headless --no-pause` 调度；2026-07-14 真实公开源纵横 headless 采集成功 34 条，生成本地证据 `var/ranking-captures/zongheng-live.{json,png,html}`；起点 headless/no-pause 真实复验输出 `user_action_required`（腾讯验证码页），番茄 headless/no-pause 输出 `schema_changed`（App 壳未暴露榜单卡片），均生成 JSON/PNG/HTML 证据且未伪装成功；本地证据目录已 gitignore。
- 验证命令：`cd backend && .venv/bin/pytest -q` → **549 passed, 9 skipped**（2026-07-14）；`python3 scripts/verify_ai_truthfulness.py` → passed；`npm --prefix frontend run build` → passed；`set -a; source .env.local; set +a; npm --prefix frontend run test:e2e` → **5 passed**（含真实 DeepSeek 主链②，上轮证据）；`GATE_ALLOW_WARNINGS=1 bash scripts/ai_development_gate.sh` → AST truthfulness passed，旧宽泛扫描仍需逐项解释。

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
| 榜单采集 adapter | 🧪 待验收 | 纵横官方页真实采集 T3；番茄/起点失败显式化；CSV/JSON/浏览器/OCR 采集工件导入、低置信拦截、人工确认放行、Open Library 六态校验均有真库测试 | 真实番茄截图/OCR样本与起点已登录会话实跑；真实源长周期 T5 |
| 榜单中心 | 🧪 待验收 | 扫榜、快照、分析、选题、成书前后端入口；导入与元数据校验 UI | 真实 AI 分析 T3、完整 E2E |
| 原创市场选题 | 🧪 待验收 | Gateway、严格 Schema、防注入、Provider 失败直接 `failed`/HTTP 错误契约测试 | 真实 Provider T3 输出证据 |
| 扫榜自动建书 | 🧪 待验收 | 幂等键建书、来源血缘、跳过人工选名 | 真实 Provider 批次成功路径 |
| 连续章节流水线 | 🧪 待验收 | 严格 Schema、章节幂等键、连续性风险报告、批次 `failed`/resume 断点续跑；浏览器实测失败→恢复链与导出正文 | 真实 Provider 多章样本与批次成功路径 |
| 统一书库 | 🧪 待验收 | 书库 API/页面、检索/筛选/排序、目录导入（权限+seq+幂等落库）、导出 TXT/MD | 完整 E2E 验收 |
| 灵感 Bootstrap | 🧪 待验收 | 灵感→书名→设定→第一章→审核基础链；真实 Provider V2 全链 `test_real_provider_v2_bootstrap.py` 已跑通（2026-07-14） | 产出质量人工验收 |
| 热点自媒体 | 🧪 待验收 | 采集器去重(24h窗口)/趋势/时效评分 + 趋势报告端点；平台匹配/受众/合规风险、AI 标题变体/短视频脚本/素材建议 4 新端点+Dashboard 选题工具箱；批次失败回滚零残留→重试幂等键复用（`test_hm_media_pipeline.py` 7 tests，@9d1786f）；历史归档 URL 配置后可按真实源回填 7 天快照（无源 502，不伪造） | 真实授权历史源配置与 7 天调度稳定性；成稿质量人工验收；真实平台发布回执 |
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

- 后端测试：**549 passed，9 skipped**（2026-07-14 本轮复跑，本地真实 DeepSeek key；真实 Postgres）。业务运行时不再提供 mock provider。新增覆盖：仿写相似度红线/版权提示、热点生成持久化/回滚、书库正式路径、出海翻译项目归属、平台连接可视化配置、审计报告 P0/P1 整改、诚信门禁、融合证据驱动、NC-SEA 合规/术语/发布血缘/真实 DeepSeek 翻译 provenance、热点 7 天历史归档回填协议与 unsupported 失败语义、扫榜浏览器/OCR采集工件导入与确认门禁。当前 Provider 验收口径：暂以 DeepSeek 为唯一必需真实链；Claude/OpenAI/Gemini 待用户提供对应 key 后再验收。
- 前端：`npm run build` 通过（仅保留 Vite 关于 `api.ts` 动静态混合导入和空 `react` chunk 的既有警告）。
- Alembic：单头 `nc_audit_workflow_scope`；本地库 upgrade→downgrade→upgrade 往返通过。
- 浏览器实测（上一轮）：审阅页时间线/人物弧线渲染真实数据；设置页数据统计为真实计数（AI 调用/内容数/pg_database_size）。当前整改要求 AI provider 失败直接失败/报错，不再把 provider 失败作为可伪恢复的成功态。
- **真实 Provider T3/V2/新增功能（2026-07-14，deepseek-chat）**：本地开发 key 仅保存在 `.env.local`（Git 忽略）。`test_real_provider_t3.py`、`test_real_provider_v2_bootstrap.py`、`test_real_provider_new_features.py` 均已跑通。新增功能真实冒烟覆盖：编辑器整章重写→七维评分→下一章规划、热点生成公众号草稿落库、仿写生成原创样稿并返回相似度报告。
- **浏览器自动化 E2E（2026-07-14 复验）**：Playwright `npm run test:e2e` 实测 **4 passed, 26.2s**。用例①注册→CSV 导入→快照落库→刷新持久→书库空态；用例②书库详情页可进入并展示简介/最新章节/全部章节；用例③平台连接可视化填写、加密保存、不回显密钥；用例④真实 AI 分析→原创选题→建书→书库可见。
- **审计报告整改（2026-07-14，commit 后工作树）**：针对《审计报告_NovelCraft_2026-07-14.md》新增 `tests/test_audit_report_remediation_20260714.py`，9 条专项回归通过；受影响老回归 77 条通过。`knowledge/daily-briefing` 仅消费真实采集/已采集热点，不再由 AI 编造当前热点；`/books/analyze` 改为真实 Gateway `book_analysis` 并写 ai_calls；worker `_track_budget` 由 ai_calls 重算并同步 budgets；发布 worker/一次性发布读取 Fernet 存储凭据；BrowserAct.chrome_publish 标 removed；移动端媒体查询改为真实 `.layout`；`.env.example` 补齐凭据/DB/Redis/Provider/热点/告警配置。
- T5 长周期运行：仍无 7 天连续调度证据，未验收。热点模块已支持授权历史归档 URL 回填 7 天数据；这只能证明“可回填真实历史源”，不能替代“连续 7 天稳定采集”验收。

## 审计对照（外部审计报告 2026-07-11）

- 已修复（`efba333`）：B1 JWT 生产强校验、B2 管理员绕过收口、B4 裸 fetch 清除、P0-1 DB.close 改 rollback、P0-2 SSE 真换行、P1-4 死组件接线。
- 已修复（本轮）：B3 发布凭据 Fernet 加密落库（`platform_accounts` 启用，响应不回显凭据）；P0-3 compose api/worker 依赖 migrate 完成；P1-1 修复 3 条静默失败索引（错误列名，原迁移 `except: pass` 吞错）；Redis appendonly + 持久卷（更正：`7053a07` 提交信息声称 "Redis persistence" 但未实际配置，属《23》§4 虚假上报，本轮补齐）；F5 设置页假统计→真实 `/stats/overview`；F7 审阅页恒空时间线/弧线→真实 `/novels/{id}/narrative`；F8 敏感词前端空函数→真实 `/contents/{id}/check-sensitive` 并接入发布前置检查；F12 DagEditor 空 project_id→真实项目 ID 且缺失时拒绝保存。
- 已修复（第二轮，对照审计全量版 §六）：多轮审核/跨模型审计/Prompt 矩阵此前用字符串长度公式伪造评分并宣称"ready"，现真实经 Gateway 调用、Provider 不可用逐项 `failed`，端点补 `project_id` 成员校验；热点采集 `except: continue` 静默空成功改为逐源状态+全失败 502；AgentConsole 硬编码"模拟"数据改为 `/agents/status` 真实 run_nodes 聚合；Collaboration 页面调用不存在的路径（必 404）改为真实 `/collaboration/*`；`/admin/workflows/{name}/execute` 此前无视工作流名一律跑 bootstrap 且 `project_id=''` 必然崩溃，改为权限校验+仅 bootstrap 可执行+其余显式 501；AI 编辑补 `ai_edit` 版本分支（C5-03）；C5-05 自动保存 7 天保留 beat 任务（保留每实体最近 10 份，语义分支永不清理）；assembler 知识层此前按无人写入的列过滤永远为空，改为按小说前提走 Knowledge Hub 检索。
- 已修复（第三轮，代码/文档/功能契约对账）：工作流保存请求原本必 422 且代码引用不存在的 `workflows.project_id/config`，现新增项目作用域迁移并统一使用 `definition`；系统 Bootstrap 只读，自定义 DAG 明确为设计稿、未接执行器返回 501；清除预算/日报/翻译四组重复路由及其中的跨项目翻译风险；设置页知识导入/导出与预算、知识检索、热点响应、Fanout 响应、多平台发布均对齐真实 API；短篇输入真实落库；Fanout Provider 失败不再复制原文冒充改写成功。
- 已修复（第四轮，按《27-全仓库审计报告》路线图阶段 0）：P1-A 迁移回滚断裂——性能索引 downgrade 移除 CONCURRENTLY，干净库 upgrade→downgrade base→upgrade 三段实测通过，并加全迁移源码契约测试；P1-B schema 快照契约测试（12 张核心表必需列钉死，防列名漂移复发）；P1-G 交付门禁升级为证据绑定校验（✅/已交付行必须含测试/commit/文件/T级标记，含负例测试）；P1-D 不可信外部文本统一清洗 `sanitize_untrusted`（接入 assembler 知识召回与热点晨报入模路径）；P1-E 备份 pg_dump 每日 sidecar + 7 份保留 + 全服务日志轮转（compose，YAML 校验通过）；P2 清理：PublishPage 死组件删除、`store_ranking_snapshot` 吞错死函数及其 T0 存在性断言删除、bundle 分包（主 chunk 702KB→281KB，消除 >500KB 警告）、版本统一（app `2.2.0` 对齐需求基线 V2.2，README 刷新）。**396 tests 全绿**。
- 已修复（第五轮，本轮审查）：纯文本编辑增加 DeepSeek SSE、完成后统一写 ai_calls/版本；流式鉴权支持 token 刷新，预算与 Provider 错误分流，非 DeepSeek 路由安全回退普通网关；Embedding 增加 remote/local/hash 三层适配、来源标记和项目重建，远端部分/非法响应回退 hash，不同后端向量禁止混算；Sentry/Prometheus 可选接线，巡检增加队列积压和成本日报。代码验证 417 passed、前端 build；真实流式 Provider、local semantic 和 Sentry 送达仍未作为验收证据。
- 全面复核（2026-07-12 第二轮，@068a45d）：PR#4 加固复核通过（流式 PENDING_BUDGET 语义/非 deepseek 显式拒绝/embedding 数量与有限性校验/检索按 provenance 过滤）；T5 提交内的一致性组件修复复核通过——entity/summarizer/timeline 此前把 AI 调用记账到 `SELECT id FROM projects LIMIT 1` 的**任意项目**（跨项目成本/预算污染），已改为按 content 归属项目；伏笔抽取 `hint_chapter` 字段对齐 prompt 契约；章节富化失败不再阻断落库与审核门禁。新增实测验收：**流式端到端真实 Provider 通过**（HTTP SSE 经 8100 API，逐字增量帧+done 帧，DeepSeek 真实调用）；**local 语义质量验收通过**（EMBEDDING_SEMANTIC_TEST=1，bge-small-zh 真实模型："地底嗡鸣"≈"深渊低语"≫无关文本，余弦差 >0.1，本机含首次模型下载 34s 完成 8/8）。
- 仍开放：B4 Nginx 无 TLS（需域名/证书决策）；流式浏览器端验收；remote embedding 质量验收（需 embedding API key）与全库重建演练；数据回流/ROI 真实数据；Sentry 与告警实测送达（需 DSN/Telegram env）；发布真实平台回执与 auto_publish 调度。真实平台账号/API/人工输入项已新增“设置 → 平台连接”可视化配置入口，敏感字段加密保存且不回显；海外 RoyalRoad/WebNovel/KDP 等真实发布暂不做自动发布，只保留 manual_required 草稿/人工回执路径，后续真实回执依赖用户填入合法平台凭据或人工上传凭证。`workers/tasks.py` 拆分；Agent 注册表仍为声明式（无独立执行体）；task/日级预算分级；T5 百章长跑进行中（完成后补证据）。

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
