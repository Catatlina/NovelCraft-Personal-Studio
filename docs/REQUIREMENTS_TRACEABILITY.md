# Starlume AI 小说主线需求追踪矩阵

> 状态只使用：未开始 / 已接线 / 可用 / 已验收。  
> “可用”表示确定性真库链路已通过；“已验收”还要求对应真实 Provider 或生产证据。

| 编号 | 需求 | 前端 | 后端/数据 | 状态 | 当前证据 | 升级门禁 |
|---|---|---|---|---|---|---|
| NOV-G-001 | 用户可注册、登录、退出 | `LoginPage.tsx`、`App.tsx` | `/auth/register`、`/auth/login`、JWT | 已验收 | E2E 主线① + 生产 `novel.xyjin.xyz` 认证 smoke | — |
| NOV-G-002 | 展示八个小说入口（含扫榜选书） | `Layout.tsx`、`App.tsx` | 不改历史数据 | 已验收 | E2E 主线① + visual.spec 截图 + 生产巡检 | — |
| NOV-G-003 | 旧入口迁移、未知入口 404 | `App.tsx`、`NotFoundPage.tsx` | 无 | 已验收 | E2E 主线② + 生产路由 smoke | — |
| NOV-G-004 | 浅深色、主题记忆、响应式 | `ThemeProvider.tsx`、`styles.css` | 浏览器偏好 | 已验收 | 单测 + visual.spec 桌面/手机截图 + 生产巡检 | — |
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
| NOV-S-001 | BYOK 只保存在当前会话 | `Settings.tsx` | 请求 Header 优先 | 已验收 | E2E 主线④；生产请求验证 | — |
| NOV-S-002 | 创作知识导入、导出和统计 | `Settings.tsx` | knowledge/stats API | 已接线 | 页面/API 接线 | 真库数据操作 E2E |
| NOV-S-003 | 修改密码 | `Settings.tsx` | auth password API | 已接线 | 页面/API 接线 | 正负例 E2E |
| NOV-Q-001 | 单元、构建和确定性主链门禁 | Vitest、Playwright | 真 PostgreSQL/FastAPI | 已验收 | 提交 `07a8c0f`：本地后端 761 passed / 9 skipped / 1 xpassed、前端 12 passed、build、E2E 4 passed / 4 skipped、三项静态校验；Actions `30439322188` 五项全绿 | 后续批次继续维持同提交 CI |
| NOV-Q-002 | 真实 AI 新 UI 全链 | protected Playwright | DeepSeek、run/ai_calls | 可用 | protected “小说主线⑤” 1 passed (3.3m)；run `a416b8a8-2bcb-4ad1-8f3d-d50c0956ba4d` 20/20 nodes、20 succeeded ai_calls；首章请求含 1451 字符装配上下文；正文 35 段/4581 非空白字符；本地后端 771 passed / 9 skipped / 1 xpassed | 当前修复提交推送且 CI 全绿；最终生产 smoke 后提升已验收 |
| NOV-D-001 | 当前版本推送和部署 | GitHub Actions、Docker | 生产基础设施 | 已接线 | 历史生产版本为 `91bcf9b`；当前 main 与本批修复均未部署 | 当前提交推送、CI 全绿、部署及生产 smoke |

## 更新规则

- 修改需求或实现时，同一批次更新本表。
- 状态提升必须在“当前证据”中写入命令、测试、run、提交或生产验证。
- 只存在代码、路由、按钮或类型定义时，最高为“已接线”。
- 失败或跳过的测试不能写成通过。
