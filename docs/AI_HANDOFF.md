# Starlume AI 项目交接说明

> 更新时间：2026-07-28  
> 交接目标：让下一位 AI 从当前真实状态继续完成小说主线，不重做 Demo、不丢失已有实现、不把未验收能力写成完成。

## 1. 唯一正确的工作目录

```text
/Users/genius/Documents/Codex/2026-07-23/https-github-com-tradecatlabs-vibe-coding/work/NovelCraft-Personal-Studio
```

`/Users/genius/Documents/NovelCraft Personal Studio` 目前只是旧文档壳，不是 Git 仓库，不得在那里继续开发。

- GitHub：<https://github.com/Catatlina/NovelCraft-Personal-Studio>
- 当前分支：`main`
- 交接前远端基线（历史）：`origin/main @ e5174c4`
- 接手实测（2026-07-28）：`git rev-parse HEAD` = `876d826` = `origin/main`，工作树干净；`bdd20f0`、`c3e0af8` 已随 `876d826`（docs: checkpoint Starlume rescue handoff）推送，原"尚未推送"已过时。
- 生产地址：<https://novel.xyjin.xyz>
- 重要：当前 Starlume 新 UI 已推送至 `origin/main`（`876d826`），但**尚未部署**；生产站 `https://novel.xyjin.xyz` 仍运行旧构建，不能作为新 UI 已验收证据。

交接提交完成后，以 `git status`、`git log --oneline --decorate -12` 和 `git rev-parse HEAD` 的实时输出为准，不要把本文中的旧 HEAD 当作不可变事实。

## 1.1 接手复验 checkpoint（2026-07-28）

下一位 AI（2026-07-28 接手）按 `AI_CONTINUITY` 强制闭环实测，仅恢复真实状态，未改动产品代码：

- 实时 Git：`git status` 干净；`git branch --show-current` = `main`；`git log` HEAD = `876d826`（= `origin/main`）；`git diff --check` 通过。
- 单元：`cd frontend && npm test` → **11 passed**（5 文件），与第 6 节一致。
- 构建：`npm run build` → TypeScript + Vite 通过；仅保留 `api.ts` 动静态混合导入与空 `react` chunk 的既有警告。
- E2E：`npm run test:e2e` → **4 passed, 1 skipped**；第 5 条 `e2e/main-chain.spec.ts:134`（protected 真实 AI 全链）因本机无 `DEEPSEEK_API_KEY` 被 `test.skip` 真实跳过，未计入通过。
- 真实性门禁：`bash scripts/ai_development_gate.sh` → AST 真实性与 whitespace 通过；suspicion scan 按设计返回 3（宽泛告警）。逐条解释见 `KNOWN_ISSUES.md` KI-005（全部为测试 monkeypatch / UI placeholder / 反伪注释 / 合法空态 / 非小说历史兜底，非业务伪实现）。
- 文档↔代码一致性：抽样确认 `Layout.tsx` 主导航为八项（含扫榜选书）；`App.tsx` 导入 `RankingCenter` 用于扫榜选书页面，其余非小说组件（Hotspot/PublishDashboard/Studio/Collaboration/IntelligenceAgent 等均未出现）；protected E2E 为真实 `test.skip` 而非伪通过。

未完成顺序第一项（protected 真实 AI E2E）状态：**✅ 已完成（2026-07-28，本地真实 Key 环境）**。执行 `npx playwright test e2e/main-chain.spec.ts --grep "protected"` → **1 passed (13.2m)**。证据：run `8f1fd62b-5ad8-4208-8fd8-887f33425631`（succeeded）、19 条真实 `ai_calls`（¥0.1889）、产物《午夜头条》+ 第一章 2350 chars、截图 protected-02..06。过程中修复 3 个真实阻断（Wizard step 校验 / e2e-backend 缺 Celery worker / dev 库迁移落后），详见 KI-001。`test.skip` 保留，无 Key 环境仍真实跳过。Key 存放于 gitignored `.env.local`，不入库。

## 2. 当前产品契约

- 用户可见品牌统一为 **Starlume AI**。
- 当前只做小说，主导航保留八项：
  1. 小说首页
  2. 创作向导
  3. 扫榜选书
  4. 我的书库
  5. 创作进度
  6. 章节编辑器
  7. 审阅与一致性
  8. 小说设置
- 非小说模块从产品 UI 隐藏，但现阶段不得删除其历史数据和仍被后端使用的源码。
- 老入口必须迁移到小说主线；未知入口必须显示真实 404。
- AI 编辑必须“生成结果 → 差异预览 → 用户应用或放弃 → 保存版本”；AI 失败不得覆盖原文。
- 设计方向为 Apple 式安静、克制、留白；支持浅色、深色、桌面、平板、手机。
- 所有小说创作链路最终必须符合需求文档，不以“页面能打开”代替业务验收。

## 3. 技术架构

- 前端：React 19、TypeScript、Vite、TipTap、Vitest、Playwright。
- 后端：FastAPI、SQLAlchemy、Alembic。
- 数据：PostgreSQL。
- 缓存/队列：Redis、Celery Worker、Celery Beat。
- AI：DeepSeek 为当前真实主验收 Provider；其他 Provider 只在具备真实凭据和证据后提升状态。
- 部署：`docker-compose.prod.yml`、Nginx、生产域名；权威流程见 `docs/NovelCraft-开发文档/14-部署与运维手册.md`。
- 认证：JWT；测试与生产都必须使用至少 32 字节密钥。

## 4. 必读顺序

1. `AGENTS.md`
2. 本文
3. `docs/REQUIREMENTS_TRACEABILITY.md`
4. `docs/KNOWN_ISSUES.md`
5. `docs/ACCEPTANCE_CRITERIA.md`
6. `docs/AI_CONTINUITY.md`
7. `docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md`
8. `PROJECT_PROGRESS.md`
9. `docs/NovelCraft-开发文档/37-新增需求任务分解-20260713.md`
10. 与正在修改模块直接相关的 PRD、API、数据库、设计、测试与部署文档

## 5. 本轮已经实现

### 已验收

- 后端单本真实 DeepSeek 19/19 节点创作链已有生产证据，run 为
  `db21a95f-1be5-4232-bb12-84ab98e91dda`；这只证明后端单本链，不等于新 UI 已验收。

### 可用

- Starlume 品牌、浅深色主题、主题记忆。
- 72/260px 桌面侧栏、平板收起、手机底部导航。
- 登录、注册、全局错误边界、404。
- 小说首页真实加载、错误、空状态和重试。
- 八个小说主页面入口（含扫榜选书）；其余非小说入口不再由 `App.tsx` 导入和渲染。
- 书库真实建书、详情、章节导入、编辑保存、刷新后持久化。
- 审阅页无证据时不伪造分数。
- 小说设置只保留 AI 连接、创作数据、账号安全。
- 旧 `#/ranking` 入口规范化到 `#/wizard`。
- 侧栏悬浮/固定展开不再遮挡书库首卡片。

### 已接线

- 创作向导到真实 Bootstrap 工作流。
- 创作进度、失败详情、重试和人工定名门禁。
- AI 润色、续写、整章重写的预览后应用流程。
- 审阅的评分、问题、优势、一致性、连续性、时间线、人物弧线展示。
- BYOK、知识导入导出、统计与改密。

## 6. 最新验证证据

在 `frontend/` 执行：

```bash
npm test
# 5 files, 11 tests passed

npm run build
# TypeScript + Vite build passed

npm run test:e2e
# 4 passed, 1 skipped
```

已通过的 E2E：

1. 注册 → 八个小说入口（含扫榜选书） → 真实首页空状态。
2. 旧入口迁移 → 404 → 手机底栏。
3. 建书 → 详情 → 导入章节 → 编辑 → 保存 → 重载后持久化。
4. 审阅无伪分 → 小说设置收敛 → BYOK 会话保存。

被跳过的 E2E：

- 真实 AI 向导 → 人工定名 → 首章 → 审阅 → 导出。
- 原因：当前本机没有 `DEEPSEEK_API_KEY`。测试位于
  `frontend/e2e/main-chain.spec.ts`，不得删除跳过条件或伪造 Provider 来“通过”。

## 7. 当前未完成顺序

1. ~~使用受保护的真实 DeepSeek Key 执行新 UI protected E2E，并保留 run、调用账本和截图证据。~~ ✅ 完成（2026-07-28）：1 passed (13.2m)，run `8f1fd62b`，19 条 ai_calls，证据见 KI-001。
2. 补 AI 编辑“生成 → 预览 → 放弃/应用 → 版本恢复”的真实浏览器 E2E。
3. 补创作进度运行中、失败、重试、人工定名、19 节点完成态的浏览器证据。
4. 完成七个页面的桌面/手机截图集与视觉回归。
5. 更新 `README.md` 中仍写“19 Tab/扫榜默认入口”的过时说明。
6. 运行工程真实性门禁；宽泛告警必须逐项解释，不能静默忽略。
7. 提交、推送 `main`，等待 GitHub Actions 全绿。
8. 按部署手册部署，检查健康接口、登录、八页面（含扫榜选书）、建书/保存和真实 AI 主链。
9. 生产验证后才能把对应状态提升为“已验收”。

## 8. 禁止破坏

- 不得重写成另一个简化项目。
- 不得用 Mock、固定 JSON、`setTimeout` 或 Toast 冒充成功。
- 不得为通过测试关闭认证、权限、校验或真实 Provider 门禁。
- 不得直接把 AI 返回覆盖进正文。
- 不得删除旧数据、数据库迁移或仍被后端主链使用的历史模块。
- 不得提交 `.env`、API Key、服务器私钥、数据库备份、构建产物或依赖目录。
- 不得把测试跳过项计入通过数。
- 不得在未部署时宣称生产已更新。

## 9. 接手后的第一批命令

```bash
git status
git branch --show-current
git log --oneline --decorate -12
git diff --check

cd frontend
npm test
npm run build
npm run test:e2e

cd ..
bash scripts/ai_development_gate.sh
```

如果真实性门禁因已知宽泛扫描返回 3，先阅读完整输出并更新
`docs/KNOWN_ISSUES.md`。只有确认每条都是非业务伪实现后，才允许按项目规范使用
`GATE_ALLOW_WARNINGS=1` 复验；这不等于告警被修复。

## 10. 交付报告格式

必须按 `AGENTS.md` 输出“已完成 / 未完成 / 不能宣称完成的项”，状态只使用：

```text
未开始 / 已接线 / 可用 / 已验收
```

没有同一版本的浏览器、接口、持久化或真实 Provider 证据时，不得使用“已验收”。
