# Starlume AI 项目交接说明

> 更新时间：2026-07-29
> 交接目标：让下一位 AI 从当前真实状态继续完成小说主线，不重做 Demo、不丢失已有实现、不把未验收能力写成完成。

## 1. 唯一正确的工作目录

```text
/Users/genius/Documents/Codex/2026-07-23/https-github-com-tradecatlabs-vibe-coding/work/NovelCraft-Personal-Studio
```

`/Users/genius/Documents/NovelCraft Personal Studio` 目前只是旧文档壳，不是 Git 仓库，不得在那里继续开发。

- GitHub：<https://github.com/Catatlina/NovelCraft-Personal-Studio>
- 当前分支：`main`
- 交接前远端基线（历史）：`origin/main @ e5174c4`
- 本轮接手基线（2026-07-29）：同步后 `git rev-parse HEAD` = `f8e343c` = `origin/main`；接手前工作树干净。
- 生产地址：<https://novel.xyjin.xyz>
- 重要：生产文档可确认的最近部署仍为 `91bcf9b`；当前 `main @ f8e343c` 及本批修复均**尚未部署**。生产站不能作为当前 V3 代码已验收的证据。

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

## 1.2 当前接手与 CI 修复 checkpoint（2026-07-29）

- 同步到 `origin/main @ f8e343c` 后确认：Bootstrap 已新增 `generate_story_arc`，当前为 **20 个运行节点（19 个 AI + 1 个人工门禁）**。
- GitHub Actions run `30425548279` 的 frontend、frontend-test、e2e、security 通过，backend 失败：`10 failed, 750 passed, 9 skipped, 1 xpassed`。
- 本批已修复：质量证据只记录实际采样来源；V3 20 节点与完整流程夹具；BYOK 引用参数的同步调度测试；小说优先边界下已退役 Costs/预算 UI 的过期源码断言；交付声明中的过期措辞。
- 当前本地证据：后端 **761 passed, 9 skipped, 1 xpassed**；前端 **12 passed**；构建通过；确定性 E2E **4 passed, 4 skipped**（1 个按需视觉集 + 3 个真实 AI protected 用例均未计入通过）；真实性、交付声明、前后端契约与 `git diff --check` 通过。
- 当前仅建立了本地**可用**证据；新 CI 同版本全绿与部署证据齐备前不能提升为已验收。

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

- 历史 V2 后端单本真实 DeepSeek 19/19 节点创作链已有生产证据，run 为
  `db21a95f-1be5-4232-bb12-84ab98e91dda`；这不等于新增故事弧节点后的 V3 20 节点链已验收。

### 可用

- Starlume 品牌、浅深色主题、主题记忆。
- 72/260px 桌面侧栏、平板收起、手机底部导航。
- 登录、注册、全局错误边界、404。
- 小说首页真实加载、错误、空状态和重试。
- 八个小说主页面入口（含扫榜选书）；其余非小说入口不再由 `App.tsx` 导入和渲染。
- 书库真实建书、详情、章节导入、编辑保存、刷新后持久化。
- 审阅页无证据时不伪造分数。
- 小说设置只保留 AI 连接、创作数据、账号安全。
- `#/ranking` 为真实扫榜选书入口，未知入口显示 404。
- 侧栏悬浮/固定展开不再遮挡书库首卡片。

### 已接线

- 创作向导到真实 Bootstrap 工作流。
- 创作进度、失败详情、重试和人工定名门禁。
- AI 润色、续写、整章重写的预览后应用流程。
- 审阅的评分、问题、优势、一致性、连续性、时间线、人物弧线展示。
- BYOK、知识导入导出、统计与改密。

## 6. 最新验证证据

2026-07-29 当前修复树证据：

```bash
npm test
# 5 files, 12 tests passed

npm run build
# TypeScript + Vite build passed

npm run test:e2e
# 4 passed, 4 skipped

cd ../backend
.venv/bin/pytest tests/ -q
# 761 passed, 9 skipped, 1 xpassed
```

已通过的 E2E：

1. 注册 → 八个小说入口（含扫榜选书） → 真实首页空状态。
2. 旧入口迁移 → 404 → 手机底栏。
3. 建书 → 详情 → 导入章节 → 编辑 → 保存 → 重载后持久化。
4. 审阅无伪分 → 小说设置收敛 → BYOK 会话保存。

被跳过的 E2E：

- 1 个按需八页面视觉截图集（需 `STARLUME_CAPTURE_VISUAL=1`）。
- 3 个真实 AI protected 用例（AI 编辑、运行中进度、向导全链）；本轮刻意未注入 `DEEPSEEK_API_KEY`，不得将跳过计入通过。

## 7. 当前未完成顺序

1. 为当前 V3 20 节点代码注入受保护的真实 DeepSeek Key，重跑向导全链，重点确认 KI-007 `write_polish` 修复与新增 `generate_story_arc` 均真实通过；保留 run、`ai_calls` 和失败/成功证据。
2. 补 NOV-E-003 浏览器失败注入 E2E，证明 AI 失败不会覆盖原文。
3. 以 `STARLUME_CAPTURE_VISUAL=1` 重跑八页面桌面/手机截图集，检查 17 张输出（8×2 + 404）。
4. 补小说设置知识导入/导出与改密的真库正负例 E2E（NOV-S-002/S-003）。
5. 提交并推送本批修复，等待 GitHub Actions 同版本全绿；未绿前 NOV-Q-001 保持可用。
6. 按部署手册部署当前绿色提交，检查健康接口、登录、八页面、切书、建书/保存和真实 AI 主链。
7. 生产验证后才能把当前版本部署和 V3 全链提升为已验收。

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
