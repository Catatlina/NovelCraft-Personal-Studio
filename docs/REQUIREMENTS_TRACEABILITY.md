# Starlume AI 小说主线需求追踪矩阵

## 2026-08-02 最新单链路决策

质量对比已完成选型：V7 真实 20 章平均 92.0、最低 91.0，V6 平均 79.6、最低 72.0。故正文生成不再维护双轨，V7 为唯一 canonical chain；V6 只承担兼容事实、`contents`、编辑器和导出。

| 需求 | 状态 | 当前证据 | 未闭合门禁 |
|---|---|---|---|
| 正文生成唯一链路 | 可用 | `08942f3` 已部署；`continue`、批量、自动续写、人工重生成和 Bootstrap 首章均委托 V7 Director；生产 smoke 15/15，V7 质量通过后幂等写回 V6 `contents` | 生产 20 章 Provider 长跑 |
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
| NOV-D-001 | 当前版本推送和部署 | GitHub Actions、Docker | 生产基础设施 | 可用 | `7c06fe3` 已推送并部署到 `novel.xyjin.xyz`；迁移到 `nc_v7_novel_project_mapping`；生产 smoke 15/15、浏览器走查 4/4 | 生产真实 20 章双轨与人工盲评不属于部署 smoke |

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
| 当前提交生产部署 | 可用 | `7c06fe3`；Docker 应用容器重建；迁移 head；公网 healthz 200 | 生产 20 章质量长跑 |
| 生产用户入口 | 可用 | 生产 smoke 15/15；生产 Playwright 走查 4/4 | 真实 Provider 生成质量和人工盲评 |
