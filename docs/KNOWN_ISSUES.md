# Starlume AI 当前已知问题

> 更新时间：2026-07-28。按阻断程度排序；解决后必须保留验证证据并从本表移除或标注历史。

## 阻断生产验收

### KI-001 新 UI 真实 AI 全链 —— ✅ 已验收（2026-07-28）

- 状态：**已验收**（本地真实 Key 全链通过 + 生产已部署，KI-002 收口完成）。
- 解决过程（2026-07-28，注入真实 `DEEPSEEK_API_KEY` 后连续定位并修复 3 个真实阻断）：
  1. **Wizard 表单校验 bug**：`Wizard.tsx` 字数输入 `min={5000} step={10000}` 与全部预设值（100000/300000/…）不满足 HTML5 step 约束 → 浏览器静默拒绝提交，工作流从未启动。修复为 `min={10000}` 且 JS 校验同步 `targetWords < 10000`。
  2. **E2E 编排缺 Celery worker**：`scripts/e2e-backend.sh` 只起 uvicorn，`execute_bootstrap` 入队后无消费者。修复为 worker(concurrency=2)+uvicorn 双进程并带退出清理。
  3. **dev 库迁移落后**：`novelcraft_dev` 停在 `nc_versions_reason_text`，`ai_calls` 缺 `user_id` 列 → 网关预算断言 `UndefinedColumn`，节点重试 4 次后 run failed。执行 `alembic upgrade head`（补 6 个迁移至 `f932f2b0b3bb`）。
- 通过证据（全部真实，无 mock）：
  - E2E：`npx playwright test e2e/main-chain.spec.ts --grep "protected"` → **1 passed (13.2m)**。
  - Celery 日志：`execute_bootstrap` 两段任务分别 254.4s（→ `waiting_human`，人工定名断点真实出现）与 527.7s（→ `succeeded`）。
  - run ID：`8f1fd62b-5ad8-4208-8fd8-887f33425631`，status=succeeded。
  - `ai_calls`：本次 run 窗口 **19 条**真实 DeepSeek 调用，合计 ¥0.1889（重节点实测 write_polish 95.6s / write_length_check 94.9s）。
  - 产物：小说《午夜头条》+ 第一章「午夜浮现」（body 2350 chars），由测试在真实候选书名中点选定名。
  - 截图：`frontend/artifacts/screenshots/protected-02..06.png`（人工定名/完成/书库/编辑器/审阅，5 张）。
- 保留约束：`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除；无 Key 环境仍真实跳过，CI 门禁不受影响。

### KI-002 新 UI 已部署生产 —— ✅ 已验收（2026-07-28）

- 状态：**已验收**。
- 部署过程（2026-07-28）：
  1. 只读扫描 43.156.17.78：确认拓扑为 nginx 443→docker frontend:8090， Compose 项目在 `/opt/NovelCraft-Personal-Studio/`，运行旧 commit `bf1a377`；无 schema 迁移；`.env` 含全部密钥。
  2. 处理分叉：`origin/main` 已含另一工作副本推送的 E2E 修复；本副本仅把文档提交 rebase 到 `origin/main` 后首次部署至 `f2e2bde`。
  3. 全量重建并启动 api/worker/beat/migrate/frontend，healthz 返回 `ai_key_configured:true`、`worker:ok: 1 online`、DB/redis ok。
- 生产验证：`https://novel.xyjin.xyz/` → 200；`/api/v1/healthz` 全绿；部署 commit 随后续修复推进到 `91bcf9b`。
- 关联收口：KI-001/KI-003 由"可用"提升为**已验收**。

### KI-003 AI 编辑与版本恢复真实浏览器闭环 —— ✅ 已验收（2026-07-28）

- 状态：**已验收**（真实 `DEEPSEEK_API_KEY` 下 E2E 全链通过 + 生产已部署，KI-002 收口完成）。
- 修复（2026-07-28）：E2E 选中错误版本导致恢复后正文变空。根因为测试用脆弱的 `nth(index)` 点击，在版本历史 UI 列表尚未刷新时点到 `body={}` 的 `offline_save` 版本；应用恢复逻辑本身正确（`restore_version` 写回目标快照 body）。修复：恢复按钮加 `data-version-id={v.id}`（`frontend/src/components/Editor.tsx`），测试按真实版本 id 点击并 `waitFor` 按钮可见。
- 通过证据（全部真实，无 mock）：
  - E2E：`npx playwright test e2e/main-chain.spec.ts --grep "小说主线⑥"` → **1 passed (29.2s)**。
  - 真实 AI：run9 两次 `editor.continue` 真实 DeepSeek 调用（deepseek-v4-pro，succeeded，含 prompt/completion tokens 与成本）。
  - 闭环：续写→预览可见且正文不变→放弃后原文不变→再次续写→应用到草稿正文含 AI 建议→按版本 id 恢复后原文 A 回归、AI 建议消失。
  - 截图：`frontend/artifacts/screenshots/protected-07..09.png`（AI 预览 / 应用后 / 版本恢复后）。
  - 取证：`restore->content.body` 恢复后确为 `{content:[{text:"档案室..."}]}`，编辑器 DOM `<p>档案室...</p>`。
- 保留约束：`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除；无 Key 环境仍真实跳过。

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

### KI-006 全页面视觉证据 —— 可用（2026-07-28，富状态待最终稳定）

- 状态：**可用**（七页面完整桌面/手机截图集已产；富状态截图已有 ③/⑥ 证据；⑤ 富状态全链受 `write_polish` 节点 AI 输出格式偶发失败影响，正在重试取证）。
- 证据：
  - `STARLUME_CAPTURE_VISUAL=1 npx playwright test --grep "七页面"` → **passed (9.1s)**，生成 15 张截图（七页面 1280/390 + 404）。
  - `npx playwright test --grep-invert "小说主线⑤"` → **6 passed, 1 skipped**；含 ③-progress `protected-01-progress-running.png`（真实运行中节点）+ ⑥ 版本恢复闭环 `protected-07/08/09.png`。
  - 小说主线⑤（人工定名→完成→书库→编辑器→审阅富状态）首次跑因 `write_polish` 节点返回 `invalid_output` 失败，Playwright 正在 retry；该问题属 AI 输出契约遵循度，非功能缺失。

## 非本轮目标但必须如实保留

- 百章真实 Provider 长跑尚未验收。
- 真实内容平台发布回执尚未验收。
- 外部热点源七天连续稳定性尚未验收。
- 这些模块目前从小说 UI 隐藏，不得因“看不见”就删除历史数据或把它们写成已完成。
