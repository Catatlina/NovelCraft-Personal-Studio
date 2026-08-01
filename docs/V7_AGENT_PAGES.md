# V7 智能体页面功能梳理文档

> 目标：回答"V7 页面里那些东西都实现了什么功能、想怎么呈现、为什么看起来乱"。
> 调研日期：2026-08-02。所有路径均基于仓库根目录 `NovelCraft-Personal-Studio/`。

---

## 一、总体结论（先看这里）

V7 页面 = 一个**独立 Tab 内的自包含侧边栏应用**（`V7Dashboard`），共 **12 个导航模块**，分为 Brain / Generation / Engineering 三组。

| 状态 | 数量 | 模块 |
|---|---|---|
| ✅ 真实可用（前端直接调真实后端 API） | 7 | Overview、States、Goals、Constraints、Versions、Event Log、Decisions |
| ⚠️ 部分实现（真实 API + mock 回退 / 前端模拟） | 2 | Generation Console、Trace Viewer |
| 🧪 Mock 壳（完全不调 API，纯前端假数据） | 2 | Cost Monitor、Prompt Manager |
| 🚧 占位（仅提示文案） | 1 | Config |

**核心问题**：后端能力（尤其 Sprint 3 的 Cost / Prompt 工程化 API）已实现但**前端没接**；已接的页面又**混入 mock 回退**，且页面上**没有任何视觉区分**真实与演示数据，导致用户无法分辨哪些数字是真的。

---

## 二、入口与整体结构

- **前端入口**：`frontend/src/App.tsx:8` 引入 `V7Dashboard`；`frontend/src/App.tsx:844` 渲染 `<V7Dashboard novelId={novel.id} />`。**注意：只有在用户选中了一本小说（`novel` 非空）时 V7 Tab 才可见。**
- **前端路由**：`frontend/src/v7/pages/V7Dashboard.tsx` 是**自包含页面**，用 `useState<PageKey>` 切换 12 个页面，**不走 React Router**——浏览器 URL 不变化、无深链接、刷新即回到 Overview。
- **导航分组逻辑**：`V7Dashboard.tsx:109-120` 按 `section` 字段分组。实际效果：Brain 组 6 项（overview/states/goals/constraints/versions/events）、Generation 组 3 项（generation/trace/decisions）、Engineering 组 3 项（cost/prompts/config）。
- **API 客户端**：`frontend/src/v7/api/client.ts`（`brainApi`），全部走 `/api` 前缀，即真实后端路径 `/api/v7/...`。
- **后端入口**：`backend/app/main.py:66,119` 挂载 `v7_router`；`backend/app/v7/api/router.py` 统一前缀 `/api/v7`，下面挂 `brain`、`trace`、`director`、`cost`、`prompt` 五个子路由。
- **相邻但不属于 V7Dashboard 的"智能体"入口**：`frontend/src/components/AgentConsole.tsx`（Tab「智能体」，走 V6 的 `/api/v1/agents`），以及主界面中的 Skills / Plugins / Modules 等 Tab。多个入口都在讲"智能体"，但互不打通，是"看起来乱"的重要原因之一（见第四节）。

---

## 三、12 个模块逐个梳理

> 后端路径均为 `backend/app/v7/api/<file>.py` 中定义的、经由 router.py 最终暴露的完整 URL。

### Brain 分区（真实实现区）

#### 1. Overview（概览）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/BrainOverview.tsx`
- **后端 API（真实）**：`GET /api/v7/brain/{novel_id}/overview`（`brain.py:79` → `NovelBrain.get_overview()`）
- **功能**：统计卡片（States/Goals/Constraints/Versions/Decisions/Events 数量）、状态分布、近期事件列表。
- **说明**：前端无 mock 回退，纯真实调用；错误时显示 Retry。

#### 2. States（故事状态管理）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/StateManager.tsx`
- **后端 API（真实）**：
  - `GET/POST /api/v7/brain/{id}/states`（`brain.py:87,102`）
  - `PUT /states/{state_id}`（`brain.py:138`）
  - `POST /states/{state_id}/approve|reject`（`brain.py:188,230`）
  - `GET /states/pending-review`（`brain.py:269`）、`GET /states/{state_id}/changes`（`brain.py:279`）
- **功能**：按 type（global/character/world/plot/reader）增删改故事状态、人工审批/驳回待审状态、查看变更历史。这是 V7「全局状态驱动」的核心载体。
- **说明**：无 mock 回退，真实可用。

#### 3. Goals（目标管理）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/GoalManager.tsx`
- **后端 API（真实）**：`GET/POST /goals`、`GET /goals/tree`、`PUT/DELETE /goals/{goal_id}`（`brain.py:297-371`）
- **功能**：目标列表 + 目标树（树形展示父子目标关系），创建/编辑/删除。
- **说明**：无 mock 回退。

#### 4. Constraints（约束管理）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/ConstraintManager.tsx`
- **后端 API（真实）**：`GET/POST /constraints`、`PUT/DELETE /constraints/{id}`（`brain.py:374-435`）
- **功能**：按类型/严重度（info/warning/error/blocking）维护创作约束（如"不许开金手指"）。
- **说明**：无 mock 回退。

#### 5. Versions（版本管理 / 快照回滚）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/VersionManager.tsx`
- **后端 API（真实）**：`GET/POST /versions`、`GET/POST /snapshots`、`POST /rollback`（`brain.py:438-557`；核心实现 `backend/app/v7/brain/version_control.py`）
- **功能**：版本列表、创建快照、一键回滚到某快照（Sprint 3 工程化的「回滚」能力）。
- **说明**：无 mock 回退。

#### 6. Event Log（事件日志）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/EventLog.tsx`
- **后端 API（真实）**：`GET /api/v7/brain/{id}/events`（`brain.py:576`）
- **功能**：按严重度/类别筛选系统事件，支持 5 秒自动刷新。
- **说明**：无 mock 回退。

### Generation 分区（含部分实现）

#### 7. Generation Console（章节生成控制台）— ⚠️ 部分实现
- **前端**：`frontend/src/v7/pages/GenerationConsole.tsx`
- **后端 API（真实）**：`POST /api/v7/director/{id}/generate-chapter`（`director.py:50` → `StoryDirector.generate_chapter()`，`story_director.py:159`）
- **后端真实程度**：后端是**真实实现**——`generate_chapter` 走 7 步智能体循环（perceive→plan→assemble→generate→deai→review→memory），通过 `generation_engine.py` 的 `AIGateway`（`generation_engine.py:558`）真实调用 LLM。
- **前端问题（关键）**：
  1. 页面上的 **7 步管线动画是纯前端模拟**（`GenerationConsole.tsx:56-75`，用 `setTimeout` + 随机时长逐一亮灯），与后端真实执行**无关联**；
  2. 真实 API 调用放在动画之后，**catch 后直接 fallback 伪造结果**（`GenerationConsole.tsx:84-93`，`review_score:75 / word_count:3200 / run_id:'mock-run-id'`）；
  3. 因此用户在页面上看到的进度条、步骤耗时、最终分数**大部分是假的**，即使后端生成真的发生了。
- **结论**：功能方向真实（后端真实），但**前端呈现是演示壳**。该模块最误导人。

#### 8. Trace Viewer（执行轨迹查看器）— ⚠️ 部分实现
- **前端**：`frontend/src/v7/pages/TraceViewer.tsx`
- **后端 API（真实）**：`GET /api/v7/trace/{id}/runs`、`GET /runs/{run_id}/steps`（`trace.py:31,63,113`；实现 `backend/app/v7/trace/tracer.py`）
- **功能**：运行列表（run_type/状态/tokens/成本）→ 点击后查看分步时间线（步骤名/耗时/token/置信度/输入输出摘要）。
- **前端问题**：真实调用成功后正常展示；但**失败时会 fallback 一条硬编码 `demo-run-1` 和 5 条假步骤**（`TraceViewer.tsx:38-52,64-71`）。由于 v7 表由 `create_all` 自动建表（非 alembic 迁移），新库无数据时容易走到 mock 分支。

#### 9. Decisions（决策日志 / 人工审批）— ✅ 真实可用
- **前端**：`frontend/src/v7/pages/DecisionLog.tsx`
- **后端 API（真实）**：
  - `GET /api/v7/brain/{id}/decisions`（`brain.py:560`）
  - `POST /api/v7/director/{id}/decisions/{decision_id}/approve|reject`（`director.py:81,99` → `HumanInterventionService.review_decision`，`backend/app/v7/human/intervention_service.py`）
- **功能**：待审批决策队列 + 决策历史，支持人工批准/驳回并记录理由（Sprint 3 的「人工控制/决策审批」落地）。
- **说明**：无 mock 回退，真实可用。`GET /api/v7/director/{id}/decisions/pending`（`director.py:71`）也存在但前端 DecisionLog 未调用（用 brain 接口的 status 过滤）。

### Engineering 分区（Mock 与占位）

#### 10. Cost Monitor（成本监控）— 🧪 Mock 壳
- **前端**：`frontend/src/v7/pages/CostMonitor.tsx`
- **前端问题（关键）**：虽然 `import brainApi`（`CostMonitor.tsx:11`），但 **`loadBudgets()` 完全没有调用任何 API**，直接 `setSummary({...})` + `setBudgets([...])` 塞入硬编码假数据（`CostMonitor.tsx:59-125`，注释还写着 `// Mock data for demo`）。预算列表、百分比、告警状态全是假的。
- **后端（真实 API 已就绪但前端未接）**：`backend/app/v7/api/cost.py` 提供了完整接口：
  - `GET/POST /api/v7/cost/{id}/budgets`（`cost.py:46,65`）、`GET/PUT/DELETE /budgets/{budget_id}`、`POST /budgets/{budget_id}/reset`
  - `GET /{id}/remaining`（`cost.py:144`）、`GET /{id}/check`（`cost.py:152`）、`POST /{id}/record`（`cost.py:167`）
  - `GET /{id}/summary`、`GET /{id}/stats/daily`、`GET /{id}/stats/task-type`（`cost.py:195,205,215`）
  - 核心实现：`backend/app/v7/cost/cost_manager.py`（Sprint 3「成本」能力）。
- **结论**：后端真实、前端假数据，**该接没接**的典型。

#### 11. Prompts（Prompt 版本管理）— 🧪 Mock 壳
- **前端**：`frontend/src/v7/pages/PromptManager.tsx`
- **前端问题（关键）**：文件顶部硬编码 `MOCK_PROMPTS`（`PromptManager.tsx:30-96`），`useState(PromptVersion[]>(MOCK_PROMPTS))`（`:99`）直接作为数据源，**整个页面零 API 调用**；"Set as default"、"New Version" 都只改本地 state，刷新即还原；展开模板时甚至显示占位文案 "Prompt template content would be displayed here in full version"（`:317`）。
- **后端（真实 API 已就绪但前端未接）**：`backend/app/v7/api/prompt.py` 提供完整接口：
  - `GET /api/v7/prompt/names`（`prompt.py:51`）、`GET/POST /versions`（`:62,83`）、`GET /versions/active/{prompt_name}`（`:135`）、`POST /versions/{id}/default|deactivate`（`:161,173`）、`POST /versions/detect-change|hash`（`:106,121`）
  - `POST /executions`、`GET /executions`、`GET /executions/stats/{prompt_name}`（`:187,221,252`）
  - 核心实现：`backend/app/v7/prompt/prompt_manager.py`（Sprint 3「Prompt 版本」能力）。
- **结论**：与 Cost Monitor 同病，**后端真实、前端 mock**。

#### 12. Config（系统配置）— 🚧 占位
- **前端**：`frontend/src/v7/pages/V7Dashboard.tsx:89-102`（switch 分支内的内联 JSX），侧边栏标 `Soon`。
- **功能**：仅提示 "System configuration page coming soon / Decision permissions, model routing, and more"，无任何 API。

---

## 四、为什么看起来乱？（判断）

1. **Mock 与真实混用，且无视觉区分**（最核心）
   同一侧边栏里 7 个真实 + 2 个含 mock 回退 + 2 个纯 mock + 1 个占位，但 UI 上只有 `New/Soon` 小徽标，**没有任何「演示数据」标记**。用户看到的 Cost 预算数字、Generation 的进度条和分数、Trace 的时间线都可能是假的，但看起来和真的一样。
2. **后端已就绪的能力，前端偏偏没接**
   Sprint 3 工程化了 Cost（`cost_manager.py`）和 Prompt（`prompt_manager.py`）两套完整后端，但对应前端页面是 mock 壳。这在功能完成度上形成"最该乱"的落差：工程上最扎实的模块，界面反而最假。
3. **入口分散、概念重复**
   - V7Dashboard 是自包含 `useState` 页面，无路由、无 URL、刷新即回 Overview，天然让人觉得"迷路"；
   - 同一 App 里还有独立的「智能体」Tab（`AgentConsole.tsx`，V6 `/api/v1/agents`）、Skills/Plugins/Modules 等 Tab，多个"智能体"入口互不打通；
   - V7 的 Prompts 与 V6 已有的 Prompt 管理（`backend/app/main.py:1738` `/api/v1/prompts`）功能重叠；V7 Versions 与主界面「版本历史」Tab 也重叠。
4. **页面层级与分组语义模糊**
   12 个条目平铺在一个 64/256px 侧边栏，分组（Brain/Generation/Engineering）与真实语义有错位：Trace 被归入 Generation 但它本质是观测工具；Cost/Prompts 被归入 Engineering，但用户更可能按"写作流程"找它们；Config 占位还占用一个导航位。
5. **依赖选中小说才能访问**
   `App.tsx:844` 要求 `novel` 非空才渲染 V7，没有小说时 Tab 点了没反应（PUBLIC_TABS 里有 v7 但渲染被条件拦掉），进一步增加"找不到"的困惑。

---

## 五、建议的呈现方式

### 合并
- **Cost Monitor → 接真实 API**（`/api/v7/cost/*`），与 Generation Console 的生成动作联动展示真实花费；若数据为空显示空态而非假预算。
- **Prompts → 接真实 API**（`/api/v7/prompt/*`），并与 V6 的 `/api/v1/prompts`（`main.py:1738`）统一为一个 Prompt 入口，避免两套并存。
- **Trace Viewer 与 Decisions 可合并**为「执行与决策」单一页面（左侧运行列表，右侧轨迹 + 待审批决策），二者数据天然关联（决策来自运行）。
- **Versions 与主界面「版本历史」Tab 统一**，避免同一能力两个入口。

### 隐藏 / 降级
- **Config**：从导航中移除（占位无意义），待真实实现后再放回。
- **Generation Console**：在未接入真实流式步骤进度（由 trace/事件推送驱动）前，明确标注「演示模式」或直接隐藏，杜绝假进度条误导。
- **Trace Viewer**：去掉 mock 回退，改为空态 + "暂无运行记录"，与真实状态一致。

### 补真实 API（优先级从高到低）
1. Cost Monitor → `backend/app/v7/api/cost.py`（后端已 100% 就绪）
2. Prompt Manager → `backend/app/v7/api/prompt.py`（后端已 100% 就绪）
3. Generation Console → 消费 `POST /director/{id}/generate-chapter` 的真实返回 + 用 `trace`/`events` 驱动步骤进度（后端已有 `tracer` 与 `event_bus`，可做 SSE 推送）

### 结构性建议
- 给 V7Dashboard 换成真正的路由（每模块一个 URL），或至少把当前页 key 同步到 query string，解决"刷新回 Overview、无深链接"问题。
- 所有模块 UI 上打状态角标：真实（绿）/ 演示数据（橙）/ 占位（灰），让用户一眼分辨。
- 在侧边栏底部或空态引导区说明各模块与 V6 既有功能的关系，避免"同一个功能两个入口"的混乱。

---

## 附录：关键文件索引

| 作用 | 文件 |
|---|---|
| V7 前端壳 | `frontend/src/v7/pages/V7Dashboard.tsx` |
| V7 API 客户端 | `frontend/src/v7/api/client.ts` |
| 各页面组件 | `frontend/src/v7/pages/{BrainOverview,StateManager,GoalManager,ConstraintManager,VersionManager,EventLog,GenerationConsole,TraceViewer,DecisionLog,CostMonitor,PromptManager}.tsx` |
| 后端路由统一挂载 | `backend/app/v7/api/router.py`；入口 `backend/app/main.py:119` |
| Brain API | `backend/app/v7/api/brain.py` |
| Director（生成/决策）API | `backend/app/v7/api/director.py` |
| Trace API | `backend/app/v7/api/trace.py` |
| Cost API（未接前端） | `backend/app/v7/api/cost.py` + `backend/app/v7/cost/cost_manager.py` |
| Prompt API（未接前端） | `backend/app/v7/api/prompt.py` + `backend/app/v7/prompt/prompt_manager.py` |
| 生成核心（真实 LLM） | `backend/app/v7/director/story_director.py`、`backend/app/v7/generation/generation_engine.py` |
| 决策审批核心 | `backend/app/v7/human/intervention_service.py` |
| V7 建表 | `backend/app/v7/db.py:init_v7_db()`（`create_all`，非 alembic） |
| 相邻智能体入口 | `frontend/src/components/AgentConsole.tsx`（V6 `/api/v1/agents`） |
