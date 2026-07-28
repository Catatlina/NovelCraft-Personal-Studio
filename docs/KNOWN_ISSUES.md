# Starlume AI 当前已知问题

> 更新时间：2026-07-28。按阻断程度排序；解决后必须保留验证证据并从本表移除或标注历史。

## 阻断生产验收

### KI-001 新 UI 真实 AI 全链尚未执行

- 状态：已接线。
- 现象：`frontend/e2e/main-chain.spec.ts` 第五条 protected 用例被跳过。
- 原因：当前本机没有 `DEEPSEEK_API_KEY`。
- 不可接受的处理：删除 `test.skip`、使用 Mock Provider、写死候选书名或伪造完成状态。
- 正确下一步：在受保护环境注入真实 Key，执行该用例，保存 run ID、`ai_calls`、关键截图和导出正文断言。
- 接手复验（2026-07-28）：`git rev-parse HEAD` = `876d826`（= `origin/main`，工作树干净）；`npm run test:e2e` 实测 **4 passed, 1 skipped**，第 5 条 `e2e/main-chain.spec.ts:134` 因 `test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY")` 真实跳过；本机 shell 与 `.env*` 均无任何 `DEEPSEEK_API_KEY`（仅 `.env.example` 含占位值）。结论：仍阻断，状态保持"已接线"，新 UI 不得宣称已验收。

### KI-002 新 UI 已推送、尚未部署

- 状态：进行中（已推送，未部署）。
- 接手复验（2026-07-28）：`git rev-parse HEAD` = `876d826` = `origin/main`，工作树干净；说明交接 checkpoint 提交（含 `bdd20f0`、`c3e0af8`）**已推送**，原"未推送"描述已过时（本文自承以实时 git 为准）。
- `origin/main` 现为 `876d826`，但生产站 `https://novel.xyjin.xyz` 仍运行旧构建，不能代表当前 Starlume UI。
- 下一步：本批交接 checkpoint 提交并推送 → 等待 GitHub Actions 全绿 → 按 `docs/NovelCraft-开发文档/14-部署与运维手册.md` 部署 → 生产 smoke。

### KI-003 AI 编辑与版本恢复缺真实浏览器闭环

- 状态：已接线。
- 已有：差异预览单测、应用/放弃 UI、保存版本接线。
- 缺少：真实 Provider 结果、放弃后原文不变、应用后刷新持久、旧版本恢复。

## 文档和门禁问题

### KI-004 README 仍描述旧产品入口

- README 仍写“扫榜中心默认入口”和“19 Tab”，与当前小说优先七页面契约不一致。
- 下一位 AI 应在功能验收前更新，不能据旧 README 恢复已隐藏入口。

### KI-005 真实性门禁存在宽泛告警

- `bash scripts/ai_development_gate.sh` 的 AST 真实性与 whitespace 已通过。
- suspicion scan 会命中测试 mock、输入 placeholder、历史非小说 fallback 字段和自然空集合，默认返回 3。
- 必须逐条阅读输出；只有确认不是生产假实现后，才可按规范用
  `GATE_ALLOW_WARNINGS=1` 复验并记录解释。
- 允许告警不等于修复告警，也不能据此宣称全项目完成。
- 接手逐条解释（2026-07-28，全部非业务伪实现）：脚本三类扫描命中均属《23》§10 允许的良性命中——
  1. **mock/fallback/placeholder/deprecated/空返回** 命中约 120 行，均为以下之一：测试代码 `vi.fn().mock*`/`vi.stubGlobal('fetch',...)`（api.test.ts、ThemeProvider.test.tsx、Progress.test.tsx、WorkspaceDashboard.test.tsx）——单元测试对网络/timer 的 monkeypatch，符合《23》§10 规则 1，非产品 mock provider；前端 `placeholder=` HTML 属性（LoginPage/Wizard/Settings/BookLibrary 等输入框）——UI 占位符，非生成结果；反伪实现注释（`never fake success`、`暂无数据 placeholder`、`report real numbers instead of 0/0 placeholder`）——显式拒绝伪造；合法空态 `return []`/`return {}`（db.py、各 service 无数据分支、circuit_breaker、hotspot 采集失败态）——有错误语义/空态文案，非静默成功；`hotspot_collector.py` 的 `fallback_url`——平台官网兜底链接（用户手动访问），非 AI 生成兜底，采集失败仍按源返回状态/502；`gateway.py`/`config.py` 的 `fallback_json`——仅为 model_routes 表列名，`config.py` 已 `max_length=0` 禁止业务 fallback，网关注释明确 "No mock or fallback generation"；`ranking_adapter.py:197` `return [("261","都市日常","1")]  # fallback`——历史非小说榜单解析兜底默认分类，不在小说产品路径，保留但不得计入小说主线完成；`core/security.py:25` `JWT_SECRET="dev-secret-change-in-production"`——开发默认密钥，仅当未设环境变量时生效，E2E/生产必须用 ≥32 字节密钥（E2E 已用 32 字节 secret）；`platform/modules/manager.py:96` `# TODO: clone repo...`——插件市场未接入口，非完成声明。
  2. **固定模板/伪造输出措辞** 仅 `gateway.py:791`、`config.py:24` 两条注释，说明已移除硬编码预算常量，非生成模板。
  3. **硬编码 active/wired 自报告** 仅 `api/v1/billing.py:82` `UPDATE ... status='active'`——订阅付费成功后的真实状态写库，由真实支付/更新驱动，非能力自报告。
  - 结论：全部命中为非业务伪实现；按《23》§10 用 `GATE_ALLOW_WARNINGS=1` 复验仅表示"已确认良性"，不等于修复告警，也不能据此外推全项目完成。

### KI-006 当前全页面视觉证据不完整

- 已人工检查首页、登录、书库、向导、进度空态、编辑器空态、审阅空态、设置和 404 的部分桌面/手机状态。
- 尚缺同一提交下七页面完整桌面/手机截图集，以及有书、有运行、有审阅证据的页面状态。

## 非本轮目标但必须如实保留

- 百章真实 Provider 长跑尚未验收。
- 真实内容平台发布回执尚未验收。
- 外部热点源七天连续稳定性尚未验收。
- 这些模块目前从小说 UI 隐藏，不得因“看不见”就删除历史数据或把它们写成已完成。
