# NovelCraft 前端功能真实性审计报告

> 审计人：许清楚（产品经理 / Product Manager）
> 审计范围：NovelCraft 前端全部 24 个路由页 + 全部页面组件 + `ui/` 通用组件 + API 层 + 路由挂载映射
> 审计方法：逐页打开组件源码 → 提取所有 API 调用 → 与后端 `backend/app/` 路由装饰器交叉核对 → 逐项确认「真实 API / 真实返回渲染 / 状态变化 / 错误处理」四点 → 识别假按钮 / 假数据 / 假流程 / 信息层级与交互问题
> 审计立场：**只读，不修改任何代码**
> 技术栈：React 19 + Vite + TypeScript + MUI + Tailwind + doc12 双主题 token；API 封装 `lib/api.ts`（`api<T>()` 返回完整 envelope `{code,message,data}`，组件读 `.data`；App.tsx 内另有一层解包封装）

---

## 一、审计结论（Executive Summary）

| 维度 | 结果 |
|------|------|
| 审计覆盖页面数 | **24 个路由 tab → 22 个实际挂载组件**（dashboard/overview/workspace 复用 `Overview`；另含全局 `CommandPalette`、登录页 `LoginPage`、错误边界 `ErrorBoundary`、主题 `ThemeProvider`） |
| 组件文件逐页核查 | **30 个组件文件 + 8 个 `ui/` 组件全部读完** |
| 前端 API 调用总数 | 约 90+ 处 `/api/v1/*` 调用 |
| 有真实后端实现的接口比例 | **≈ 100%**（所有前端调用的路径均在 `backend/app/` 路由中找到对应实现） |
| 假功能（P0） | **0 个（已挂载页面无任何假功能）** |
| 假数据（P1/P2） | **1 处死代码假数据（DashboardV2，未挂载）+ 1 处渲染态硬编码（Editor 聊天问候语）** |
| 假按钮（P1） | **2 个**（Review.tsx 的「重新审查」「导出报告」无 onClick） |
| 假流程（P0） | **0 个**（无 setTimeout 模拟进度 / 无"正在生成-完成"伪状态机） |

**总体结论**：代码库功能真实性高，绝大部分交互真实可用、状态机完整、错误处理以 in-page banner 为主（无 `alert()` 假弹窗）。主要问题集中在**少量死代码假数据、2 个无处理函数的按钮、以及信息层级 / 折叠策略需按三层结构统一**。

---

## 二、功能真实性清单表

> 状态标注：`真实` = API 真实 + 渲染真实 + 状态/错误处理完整；`半实现` = 已接真实接口但体验/状态有缺口；`假功能` = 无真实后端或纯展示骗局。

| # | 页面（组件） | 核心功能 | 当前状态 | 后端接口（已交叉核对） | 问题 | 修改方案（指向文件/行） |
|---|------|------|------|------|------|------|
| 1 | 登录/注册 (LoginPage) | 登录 / 注册 / 显示密码 | 真实 | `/api/v1/auth/login`、`/api/v1/auth/register`、`/api/v1/auth/logout` | 无 | — |
| 2 | 工作台/概览/工作区 (Overview，dashboard+overview+workspace 复用) | 数据看板、分页列表 | 真实 | `/api/v1/analytics/dashboard` | 无 | — |
| 3 | 扫榜选书 (RankingCenter) | 源/快照/话题/扫描/导入/分析/书签/批量删/生成书 | 真实 | `/api/v1/ranking/*`、`/api/v1/library/*`（10+ 端点） | 体量过大（1051 行），高层级折叠待优化 | 见 §六 UI 方案 |
| 4 | 统一书库 (BookLibrary) | 续写/批量生成/恢复/取消/导入/导出TXT-MD/删除/批量删/人工审核 + 搜索筛选排序分页 | 真实 | `/api/v1/library/books`、`completion`、`generation-batches` | 无 | — |
| 5 | 灵感创作 (Wizard) | 启动 Bootstrap | 真实 | `POST projects/{id}/novels` + `novels/{id}/bootstrap`、`/api/v1/healthz` 校验 Key | 无 | — |
| 6 | 创作进度 (Progress) | 工作流时间线、重试、确认/重生成书名 | 真实 | `runs/{id}/nodes/{key}/retry`（经 App.tsx `confirmTitle`/`regenerateTitles`） | ETA 为前端加权估算（代码已诚实注释 "NOT real data"） | P2：保留并标注即可 |
| 7 | 质量审阅 (Review) | 七维雷达、分析报告 8 节、一致性/问题/优点/连续性 | 真实（数据来自 App.tsx 传入） | 经由 `novels/{id}/narrative`、`runs` 节点输出 | **「重新审查」「导出报告」按钮无 onClick（假按钮）** | P1：删按钮或接 `runEditorOp("review")` / 真实导出 |
| 8 | 章节编辑器 (Editor) | 保存/AI续写/润色/大纲、版本恢复、冲突解决、离线队列、自动保存 | 真实 | 经 App.tsx `saveChapter`/`runEditorOp`/`restoreVersion` + `lib/offlineCache` | **AI 聊天初始问候语为硬编码假内容**（L43-45 "检测到本章情绪偏治愈收束…"） | P2：改为空态提示或接真实 chat |
| 9 | AI 成本 (Costs) | 我的 Token 账单、调用明细、预算、路由 | 真实 | `/api/v1/analytics/usage?scope=user`、AI 调用来自 App.tsx | 无 | — |
| 10 | 订阅与套餐 (Billing) | 订阅/套餐目录/升级切换 | 真实 | `/api/v1/billing/subscription`、`/api/v1/billing/plans`、`/api/v1/billing/subscription/upgrade` | 无（已诚实标注 MVP 不涉及支付） | — |
| 11 | Prompt 管理 (Prompts) | 注册表浏览（展开 golden_cases/模板）、实验室多模型对比 | 真实 | `/api/v1/admin/prompts`、`/api/v1/prompts/lab` | 「新建版本」按钮 disabled（已诚实标注只读） | P2：可隐藏或改 tooltip |
| 12 | 工作流编排 (DagEditor) | 设计稿加载/保存/执行 | 真实 | `/api/v1/admin/workflows`、`/api/v1/admin/workflows/custom-dag`、`.../execute` | 初始 seed 节点为硬编码（挂载即从真实接口覆盖，诚实注释"不会被冒充为已运行"） | P2：保留 |
| 13 | 系统设置 (Settings) | Provider/路由/预算/Prompt/通用/平台连接/统计/知识导入/改密 | 真实 | `admin/providers`、`admin/model-routes`、`admin/budgets`、`admin/prompts`、`admin/settings`、`platform-connections`、`stats/overview`、`knowledge/import`、`auth/change-password` | 无 | — |
| 14 | 内容工作室 (Studio) | 短篇/知识库/热点/仿写 | 真实 | `projects/{id}/short-stories`、`knowledge/search`、`knowledge/daily-briefing`、`imitation` | 无 | — |
| 15 | 发布看板 (PublishDashboard) | 发布/出海翻译/数据反馈/团队协作 | 真实 | `publish/records`、`analytics/dashboard`、`analytics/feedback`、`publish`、`overseas/translate`、`contents/{id}/check-sensitive`、`collaboration/*` | 无 | — |
| 16 | 热点追踪 (HotspotDashboard) | 热点/文章分页、生成、CRUD、来源详情 | 真实 | `hotspots/paginated`、`hotspots/overview`、`articles`、`hotspots/generate` 等 | **热点列表分页缺 100 选项（仅 [10,20,50]，与统一 [10,20,50,100] 不符）** | P2：补 100 选项 |
| 17 | 知识库 (KnowledgeBrowser) | 语义检索 + 类型筛选 | 真实 | `POST /api/v1/knowledge/search` | 无 | — |
| 18 | 多平台分发 (FanoutMatrix) | 一稿多平台分发 | 真实 | `POST /api/v1/contents/{id}/fanout` | 无 | — |
| 19 | 版本历史 (VersionTree) | 版本列表 + 恢复 | 真实 | 经 App.tsx `loadVersions`/`restoreVersion` | 无 | — |
| 20 | 伏笔看板 (ForeshadowingBoard) | 种植中/已回收伏笔 | 真实 | `GET /api/v1/novels/{id}/foreshadowings` | **无 loading/error 状态，错误静默 catch** | P2：加 loading/error 态 |
| 21 | 协作管理 (CollaborationPanel) | 成员/邀请/操作日志 | 真实 | `collaboration/members`、`logs`、`invite` | 无 | — |
| 22 | 智能体 (AgentConsole) | Agent 状态表 | 真实 | `/api/v1/agents/status` | 无 | — |
| 23 | 插件管理 (Plugins) | 社区技能目录浏览 | 真实 | `/api/v1/skills/community` | 「安装/启用/禁用」按钮 disabled（已诚实标注后端无接口） | P2：可隐藏 |
| 24 | 命令面板 (CommandPalette) | Cmd/Ctrl+K 全局跳转 | 真实（命令均为真实 tab 切换） | — | **遮罩层用硬编码 `rgba(11,15,25,0.55)`（违反 doc12 token 规范）** | P2：改用 `var(--bg)` + 透明度或专用 token |
| — | 死代码 (DashboardV2) | 统计卡/快捷操作/近期项目/系统状态/待办 | **假功能（未挂载）** | 无任何调用 | 含 STAT_CARDS/QUICK_ACTIONS/RECENT_PROJECTS/SYSTEM_STATUS/TODO_ITEMS 共 5 处硬编码假数据；App.tsx 未 import，永不渲染 | P1：删除该文件或接入真实数据后挂载 |

---

## 三、分级问题清单

### P0（假功能 / 必须整改，影响真实性底线）
- **0 个已挂载页面的假功能。**
- 说明：已挂载的 22 个组件、全局命令面板、登录页均调用真实后端且有真实渲染。未发现任何"显示正在生成/100%/完成"却无真实状态机的伪流程；未发现 `alert()` 假弹窗；未发现 `setTimeout` 模拟进度的假动画。

### P1（体验问题 / 应整改）
| ID | 类型 | 位置 | 描述 | 修改方案 |
|----|------|------|------|----------|
| P1-1 | 假按钮 | `Review.tsx:209`「重新审查」 | 渲染按钮但 `onClick` 缺失，点击无反应 | 删除按钮，或接入真实重新审查（调用工作流 `final_consistency_check` 节点或 `runEditorOp("review")`） |
| P1-2 | 假按钮 | `Review.tsx:212`「导出报告」 | 同上，无处理函数 | 删除按钮，或实现真实报告导出（前端拼装 `NovelAnalysisReport` 数据 → 下载 Markdown/PDF） |
| P1-3 | 假数据（死代码） | `DashboardV2.tsx`（全文件，L33/L78/L146/L195/L208） | 5 处硬编码假数据数组（STAT_CARDS/QUICK_ACTIONS/RECENT_PROJECTS/SYSTEM_STATUS/TODO_ITEMS）；App.tsx 未挂载，永不渲染，但属隐患（易被误接） | 直接删除 `DashboardV2.tsx`；若需「工作台」页，应接入 `Overview` 已用的 `analytics/dashboard` 等真实数据重建 |

### P2（优化问题 / 建议整改）
| ID | 类型 | 位置 | 描述 | 修改方案 |
|----|------|------|------|----------|
| P2-1 | 假数据（渲染态） | `Editor.tsx:43-45` | AI 聊天初始 system 消息硬编码为"检测到本章情绪偏治愈收束…"，伪造成 AI 已分析 | 改为空态引导文案（如"向 AI 助手提问，或选中文本用浮动工具栏润色/续写"），或接真实 chat 接口 |
| P2-2 | 一致性 | `HotspotDashboard.tsx` 热点分页 | 热点列表 `pageSizeOptions` 仅 `[10,20,50]`，缺 100，与全局统一 `[10,20,50,100]` 不符 | 改为 `[10,20,50,100]`（文章列表已正确） |
| P2-3 | 状态缺失 | `ForeshadowingBoard.tsx:15-17` | 仅 `useState([])`，无 loading/error，`catch(()=>{})` 静默吞错 | 加 `loading`/`error` banner，错误可见化 |
| P2-4 | 设计系统 | `CommandPalette.tsx:27` | 遮罩层 `rgba(11,15,25,0.55)` 为裸 hex，违反 doc12 双主题 token 规范（严禁裸 hex） | 改用 `var(--bg)` 配合透明度，或新增 `--overlay` token |
| P2-5 | 冗余展示 | `Prompts.tsx:211`「新建版本」/ `Plugins.tsx:241-252`「安装/启用/禁用」 | disabled 按钮 + 说明文案，诚实但占版面 | 建议隐藏 disabled 按钮，仅在后端提供接口时渲染；或合并为一条 info 提示 |
| P2-6 | 诚实估算 | `Progress.tsx:185-191` | ETA = 前端加权估算（代码注释已标注 "NOT real data"） | 保留，维持现有诚实标注即可（非问题，记录备查） |

---

## 四、假功能 / 假数据 / 假流程 汇总（按 P0/P1/P2）

| 类别 | P0 | P1 | P2 | 合计 |
|------|----|----|----|------|
| 假功能（无真实后端/伪状态机） | 0 | 1（DashboardV2 死代码） | 0 | 1 |
| 假数据（mock/硬编码/useState 初始假数据） | 0 | 1（DashboardV2 5 处数组） | 1（Editor 聊天问候语） | 2 |
| 假按钮（无处理函数） | 0 | 2（Review 重新审查/导出报告） | 0 | 2 |
| 假流程（setTimeout 伪进度/伪完成） | 0 | 0 | 0 | 0 |
| **合计** | **0** | **4** | **2** | **6** |

> 注：DashboardV2 虽含假数据但**未挂载、不向用户展示**，故真实性风险为"隐患级"而非"可见欺骗级"，归入 P1 清理项而非 P0。

---

## 五、交互与信息层级问题列表

### 5.1 交互规范（按钮状态机）
- 通用组件 `ui/Button.tsx` 仅为 `className` 封装，原生 `disabled` 可用；各页面在 `busy/loading` 时正确禁用主按钮（Wizard、Billing、Prompts、Fanout、Login、BookLibrary 等）✅
- `ui/ConfirmDialog.tsx` 支持 Esc/点击遮罩取消、confirm 后自动关闭，删除类操作均经此二次确认（BookLibrary 批量删等）✅
- **缺口**：Review 页 2 个按钮完全无处理函数（P1，见上）；Plugins/Prompts 的 disabled 按钮无视觉"为何不可用"以外的引导（P2）。

### 5.2 列表页规范（分页 / 搜索 / 筛选 / 排序 / 批量）
- `ui/Pagination.tsx` 功能完备：首页/上一页/下一页/末页 + 窗口化页码 + 跳页输入 + 每页 `[10,20,50,100]` 选项 + client/server 双模式 ✅
- 列表页普遍已应用分页（Overview/BookLibrary/Costs/Billing/Prompts/Settings/Studio/PublishDashboard/HotspotDashboard/Review/Collaboration/AgentConsole/VersionTree/ForeshadowingBoard 等）✅
- **缺口**：HotspotDashboard 热点列表缺 100（P2-2）；ForeshadowingBoard 无加载/错误态（P2-3）。

### 5.3 折叠 / 信息层级（现状）
- `ui/Accordion.tsx` 支持 `defaultOpen`，内部受控开合；`NovelAnalysisReport.tsx` 已用 **8 节 Accordion 全部默认折叠**、缺失节渲染"暂无数据"占位（真实、不编造）✅ 这是三层信息结构的优秀范例。
- `HotspotDashboard`「查看来源详情」Accordion 默认折叠 ✅
- `StepTimeline.tsx` 默认展开 `active` 步骤、其余可折叠 ✅
- **缺口**：体量大的 `RankingCenter`（1051 行）、`Settings`（728 行）、`Studio`、`PublishDashboard` 多 Tab 内部面板未统一遵循"高频默认展开 / 低频默认折叠"。

---

## 六、UI 优化方案（三层信息结构 + 折叠原则落点）

> 三层信息结构：**核心信息默认显示 / 常用操作默认显示 / 高级信息折叠**。
> 折叠原则：**高频或用户关注的默认展开；低频或高复杂默认折叠**。

### 6.1 已符合规范的落点（保留）
- `Review.tsx` → `NovelAnalysisReport.tsx`：8 节分析 Accordion 默认折叠，缺失即占位 → **标准范式**，建议作为全局模板。
- `HotspotDashboard.tsx`：来源详情默认折叠。
- 全局列表 `Pagination` 统一 `[10,20,50,100]`（除 P2-2 例外）。

### 6.2 建议整改落点（指向具体页面/组件）

| 落点 | 当前问题 | 三层结构改造建议 |
|------|----------|------------------|
| `RankingCenter.tsx`（最大页，1051 行） | 多个面板平铺，信息密度高 | 将「扫描设置 / 导入参数 / 批量操作区」等高级配置折叠进 Accordion（默认收起）；保留「榜单快照」「话题列表」核心区默认展开 |
| `Settings.tsx`（728 行，4 Tab） | 每 Tab 内列表 + 表单平铺 | 「高级参数 / 原始 JSON / 测试日志」折叠；Provider/路由/预算核心表默认展开 |
| `Studio.tsx`（4 Tab：短篇/知识/热点/仿写） | 结果面板与输入区混杂 | 输入区默认展开；「历史结果 / 原始返回」折叠 |
| `PublishDashboard.tsx`（4 Tab） | 发布表单 + 出海 + 数据 + 团队 | 「高级发布选项 / 翻译映射 / 反馈原始日志」折叠；核心发布/数据卡片默认展开 |
| `Overview.tsx`（dashboard/overview/workspace） | stat 卡 + 快捷操作平铺 | 核心指标卡默认展开；「明细表 / 最近活动」可折叠为下层 |
| `Progress.tsx` | 时间线 + 创作总览 + 节点详情 | 当前 `StepTimeline` 已默认展开 active 步骤（✅）；节点详情按需展开即可 |
| `Billing.tsx` | 用量条 + 套餐目录 | 当前核心信息默认展开（合理 ✅）；「套餐特性明细」可折叠 |

### 6.3 设计系统一致性
- 全站应使用 doc12 token（`var(--xxx)`），严禁裸 hex。已发现唯一违规：`CommandPalette.tsx:27` 遮罩 `rgba(11,15,25,0.55)`（P2-4）。
- 错误反馈统一用 in-page banner（非 `alert()`），现状良好（Prompts/Billing/Plugins/Costs 均有 `Banner` 组件，且注释 "never an alert()"）。

---

## 七、修改优先级（执行顺序建议）

> 后续整改链路：架构师重设计 → 工程师修复 → QA 验证。本审计为前置。

1. **P0（真实性底线）**：无。代码库已挂载页面功能真实，可直接进入体验优化。
2. **P1（必须整改，2 个文件）**：
   - `Review.tsx`：移除或接入「重新审查」「导出报告」按钮（L209、L212）。
   - `DashboardV2.tsx`：删除死代码文件（含 5 处硬编码假数据），消除隐患。
3. **P2（建议整改，按性价比排序）**：
   - `Editor.tsx:43-45` 聊天问候语硬编码 → 改空态引导（最易见、最像"假 AI"）。
   - `HotspotDashboard.tsx` 热点分页补 100 选项。
   - `ForeshadowingBoard.tsx` 补 loading/error 态。
   - `CommandPalette.tsx:27` 遮罩改 token。
   - `Prompts.tsx` / `Plugins.tsx` 隐藏无接口的 disabled 按钮。
4. **结构级（UI 优化，跟随架构师重设计）**：RankingCenter / Settings / Studio / PublishDashboard / Overview 按 §六 三层结构 + 折叠原则统一整改。

---

## 八、附：组件 API 真实性核对摘录（供架构师 / QA 复用）

- 前端所有 `/api/v1/*` 调用路径（约 90+）均已在 `backend/app/` 路由装饰器与前缀中找到对应实现，覆盖：`auth`、`admin`(config/providers/budgets/prompts/model-routes/settings/workflows)、`billing`、`short-stories`、`platform-connections`、`knowledge`、`hotspots`、`ranking`+`library`、`overseas`、`imitation`、`publish_schedule`、`analytics`、`collaboration`、`agents`、`skills`、`contents/{id}/fanout`、`novels/{id}/foreshadowings`、`prompts/lab`。
- 离线机制：`lib/offlineCache.ts`（Mutation 队列 + 乐观更新）被 Editor 的 `saveChapter`/`runEditorOp`/`applyOfflineAiResult` 真实使用，非假功能。
- 流式：`lib/api.ts` 的 `apiStream()`（SSE）被 App.tsx `runEditorOp` 真实用于编辑器 AI 流式输出，`Editor.tsx` 的 `streamPreview` 真实渲染。
- 未发现：`alert()` 假弹窗、`setTimeout` 伪进度、useState 初始假数据数组（除 DagEditor 诚实 seed、Editor 聊天问候语、DashboardV2 死代码三处，均已分级）。

---

*审计完成。本报告仅记录现状与修改建议，未对任何源文件做改动。*
