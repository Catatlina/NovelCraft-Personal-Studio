# Starlume AI 小说主线需求追踪矩阵

> 状态只使用：未开始 / 已接线 / 可用 / 已验收。  
> “可用”表示确定性真库链路已通过；“已验收”还要求对应真实 Provider 或生产证据。

| 编号 | 需求 | 前端 | 后端/数据 | 状态 | 当前证据 | 升级门禁 |
|---|---|---|---|---|---|---|
| NOV-G-001 | 用户可注册、登录、退出 | `LoginPage.tsx`、`App.tsx` | `/auth/register`、`/auth/login`、JWT | 可用 | E2E 主线① | 生产认证 smoke |
| NOV-G-002 | 只展示七个小说入口 | `Layout.tsx`、`App.tsx` | 不改历史数据 | 可用 | E2E 主线① | 生产七页面巡检 |
| NOV-G-003 | 旧入口迁移、未知入口 404 | `App.tsx`、`NotFoundPage.tsx` | 无 | 可用 | E2E 主线② | 生产路由 smoke |
| NOV-G-004 | 浅深色、主题记忆、响应式 | `ThemeProvider.tsx`、`styles.css` | 浏览器偏好 | 可用 | 单测 + 本地桌面/手机检查 | 全页面截图回归 |
| NOV-H-001 | 首页显示真实书籍和运行状态 | `WorkspaceDashboard.tsx` | `/library/books`、`/runs/latest` | 可用 | 单测、E2E 空状态 | 有书/有运行生产证据 |
| NOV-W-001 | 输入创意、题材、风格、篇幅并启动 | `Wizard.tsx` | Bootstrap API、真实 Gateway | 已接线 | 无 Key 阻断、接口接线 | protected E2E |
| NOV-W-002 | AI 策划后必须人工确认书名 | `Progress.tsx` | `human_confirm_title` 节点 | 已接线 | 组件测试、后端生产 run | 新 UI 人工定名 E2E |
| NOV-P-001 | 展示真实节点、产物、失败和重试 | `Progress.tsx` | Runs、nodes、retry API | 已接线 | 单测、真实字段渲染 | 运行中/失败/完成 E2E |
| NOV-L-001 | 书库加载、搜索、筛选、排序 | `BookLibrary.tsx` | `/library/books` | 可用 | 真实空态与建书 E2E | 分页/筛选 E2E |
| NOV-L-002 | 详情、章节目录和导入 | `BookLibrary.tsx` | novel/detail/import API | 可用 | E2E 主线③ | 生产 smoke |
| NOV-L-003 | TXT/MD 导出 | `BookLibrary.tsx` | export API | 已接线 | 按钮/API 接线 | 下载内容断言 + protected E2E |
| NOV-E-001 | 编辑章节并真实持久化 | `Editor.tsx`、`RichEditor.tsx` | `PUT /contents/{id}`、versions | 可用 | E2E 主线③刷新持久化 | 生产 smoke |
| NOV-E-002 | AI 编辑先预览再应用或放弃 | `Editor.tsx`、`editorPreview.ts` | content AI API、版本保存 | 已接线 | 3 条单测 | 真实 AI 浏览器 E2E |
| NOV-E-003 | AI 失败不覆盖原文 | `App.tsx`、`Editor.tsx` | Gateway 显式失败 | 已接线 | 代码与单测边界 | 浏览器失败注入 E2E |
| NOV-E-004 | 版本查看与恢复 | 编辑器版本区 | versions API | 已接线 | API/页面既有接线 | 浏览器恢复后持久化 |
| NOV-R-001 | 无审阅证据时不伪造评分 | `Review.tsx` | run review outputs | 可用 | E2E 主线④ | 生产空态 smoke |
| NOV-R-002 | 展示七维、一致性、连续性和问题证据 | `Review.tsx` | review/consistency nodes | 已接线 | 后端真实 run 有证据 | protected E2E + 截图 |
| NOV-S-001 | BYOK 只保存在当前会话 | `Settings.tsx` | 请求 Header 优先 | 可用 | E2E 主线④ | 生产请求验证 |
| NOV-S-002 | 创作知识导入、导出和统计 | `Settings.tsx` | knowledge/stats API | 已接线 | 页面/API 接线 | 真库数据操作 E2E |
| NOV-S-003 | 修改密码 | `Settings.tsx` | auth password API | 已接线 | 页面/API 接线 | 正负例 E2E |
| NOV-Q-001 | 单元、构建和确定性主链门禁 | Vitest、Playwright | 真 PostgreSQL/FastAPI | 可用 | 11/11；build；4 passed, 1 skipped（protected 真实 AI 全链因本机无 Key 跳过） | CI 同版本全绿 |
| NOV-Q-002 | 真实 AI 新 UI 全链 | protected Playwright | DeepSeek、run/ai_calls | 已接线 | 后端旧版生产 19/19 | 新 UI protected E2E |
| NOV-D-001 | 当前版本推送和部署 | GitHub Actions、Docker | 生产基础设施 | 未开始 | 新 UI 尚未推送 | CI 全绿→部署→生产 smoke |

## 更新规则

- 修改需求或实现时，同一批次更新本表。
- 状态提升必须在“当前证据”中写入命令、测试、run、提交或生产验证。
- 只存在代码、路由、按钮或类型定义时，最高为“已接线”。
- 失败或跳过的测试不能写成通过。
