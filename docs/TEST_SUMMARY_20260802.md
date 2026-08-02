# Starlume AI 全量测试汇总报告（2026-08-02）

## 0. 最新单链路回归（本轮）

- 生成质量选型：V7 真实 20 章平均 92.0、最低 91.0，高于 V6 的 79.6/72.0；正文生成已收口为 V7 唯一链路。
- 兼容边界：V6 只承载事实/知识、`contents`、编辑器和导出；V7 通过质量门后幂等写回 V6。
- 本轮后端全量：**849 passed、138 skipped、1 xpassed、2 warnings**；canonical V7 目标回归 **46 passed、2 warnings**。
- `verify_ai_truthfulness.py`、`verify_delivery_claims.py`、Python 编译检查和 `git diff --check` 通过。
- 本轮路由收口已提交为 `08942f3` 并部署；生产 smoke 15/15，浏览器走查 4 个用例均有通过证据。部署验证不等于生产长篇质量验收。

> 汇总本会话（2026-07-31 ～ 2026-08-02）执行的全部测试与验证结果；末尾追加本轮本地收口证据。
> 覆盖：V7 引擎测试 / 编辑器回归 / 前端单测 / 构建 / 生产 smoke / 生产浏览器走查 / 50 章连续生成评估。

---

## 1. 后端测试（真实 PostgreSQL，无 mock）

| 测试集 | 结果 | 说明 |
|---|---|---|
| tests/v7/test_repositories.py | **74 passed** | 仓库层（state/goal/constraint/version/trace/event/human/cost/prompt）真实入库 |
| tests/v7/test_brain.py | **51 passed** | Brain 层（state_manager/goal_system/constraint_system/version_control/novel_brain） |
| tests/v7/ 合计 | **125 passed, 4 skipped** | 4 个 skip 为 test_e2e.py 同步 Session 遗留测试（显式 skip，非掩盖） |
| tests/test_editor_regression_20260801.py | **13 passed** | 编辑器回归：deai 字数门禁/prompt 篇幅要求/预览替换/apply 落库契约/兜底 |
| tests/test_write_polish_repair.py 等（编辑器相关） | **53 passed** | 润色修复/章节审阅门禁/修复引擎/bootstrap |
| 相关全量合计 | **180 passed, 4 skipped** | V7 125 + 回归 13 + 编辑器相关 42 |

**测试环境**：PostgreSQL `starlume_v7_gate`（真实 JSONB/UUID 列），conftest 强制真实 PG + 外层事务回滚，AIGateway 未配 Key 即拒绝伪造输出。

## 2. 前端测试与构建

| 项 | 结果 |
|---|---|
| vitest 全量 | **32 passed**（9 个测试文件：Progress/Review/Settings/ThemeProvider/WorkspaceDashboard/editorPreview 回归等） |
| TypeScript 类型检查 | tsc --noEmit 通过 |
| 生产构建 | npm run build 通过（dist 产出正常） |
| **Playwright E2E 最终复跑** | **17 passed / 10 skipped / 0 failed**（27 用例；Provider/条件性 skip 不计入通过；明细见 `docs/E2E_RESULT_20260802.md`） |

## 3. 生产验证

| 项 | 结果 |
|---|---|
| prod_smoke.py（14 项） | **14/14 PASS，失败项：无**（登录/建书/V3 bootstrap 20 节点/八页面可达/切书） |
| 生产浏览器走查（Playwright，e2e/prod-walkthrough-v2.spec.ts） | **通过**：八页面可达 + V7 Cost Monitor 真实渲染（无 mock 数据）+ V7 Prompts 真实渲染（无 mock hash，真实空态） |
| 生产 cost/prompt API | 4 端点全部 200（budgets/summary/names/versions） |

## 4. 50 章连续生成评估（真实 AI，¥0.81）

- 50/50 章完成，**205,913 字**，真实 DeepSeek 调用，总成本 **¥0.8055**
- 四维均值：可读性 85.7 / 连续性 86.6 / 连贯性 84.1 / 准确性 86.8 / 综合 84.4
- 跨章程序化校验：AI 腔 0 / 现代口语 0 / 角色名漂移 0；真相提前全揭 4 处；归墟灯代价省略 13 章
- 长程趋势：连贯性/准确性末端小幅下滑（已在 720f40b 修复：上下文窗口 30→120、维度级 review 拦截）
- 完整报告：`docs/QA_50chap_report.md` + 图表 `docs/qa_50chap_chart.json`

## 5. 缺陷修复清单（本会话全部修复并部署）

| 缺陷 | 修复 commit |
|---|---|
| 编辑器 AI 建议应用不上（offline_conflict 回滚） | 1306484 |
| deai/润色字数不足 2000（三层防护：prompt 篇幅要求 + 门禁重跑 + 回退原文） | 1306484 / 0339308 |
| 生产「卡章节初稿」（worker SIGKILL 自愈 + 24h 上限 + LLM 总超时） | 00bcbc6 / 0b3758c / 042a81d |
| LLM 调用无限挂起（httpx 无总时长超时） | 042a81d |
| V7 mock 壳（Cost/Prompt/Trace/Generation/Config） | 720f40b |
| D1 版本号恒 1（version_id_col） | 720f40b |
| D2 last_violation_at 恒 NULL | 720f40b |
| 50 章长程质量衰减（上下文窗口/维度拦截） | 720f40b |

## 6. 待办（未完成）

- ~~前端 Playwright e2e 全量（#164）~~ ✅ **已验证**（最终复跑 17 passed / 10 skipped / 0 failed；无 Provider Key 的正向 AI 用例仍不计入质量验收，见 `docs/E2E_RESULT_20260802.md`）
- ~~生产 Web 功能走查（#162）~~ ✅ **已完成**（见第 3 节）
- 覆盖率统计（#171）—— 未执行（整体≥70% / 核心≥80% 待跑）

---

*历史报告生成：2026-08-02；本轮工作树含未提交的 V6/V7 合并与生成质量整改，尚未推送或部署生产。*

## 7. 本轮收口追加证据（2026-08-02）

- 后端全量：`backend/.venv/bin/python -m pytest backend/tests -q` → **843 passed, 138 skipped, 1 xpassed, 2 warnings**。
- 前端：`npm test -- --run` → **9 个文件、32 个测试通过**；`npm run build` 通过。
- 端到端历史回归：`npm run test:e2e` → **18 passed, 9 skipped, 0 failed**；为避免并发测试互相消耗生产注册限流，E2E 后端仅通过 `NOVELCRAFT_REGISTER_RATE_LIMIT=120/minute` 覆盖测试环境，生产默认仍为 `5/minute`。本轮最终复跑为 **17 passed, 10 skipped, 0 failed**。
- 数据库：Alembic 当前为 `nc_v6_v7_runtime_ledger (head)`；Prompt 播种脚本重复执行仍返回同一组 8 个 runtime Prompt 身份。
- 静态门禁：`verify_ai_truthfulness.py`、`verify_delivery_claims.py`、`git diff --check`、Python 编译检查通过；强制 `bash scripts/ai_development_gate.sh` 仍以 **exit 3** 结束，原因是既有宽泛 suspicion scan，详见 `docs/KNOWN_ISSUES.md` KI-005。

## 8. 继续整改后的最新证据（2026-08-02）

- 后端全量最新：`843 passed、138 skipped、1 xpassed、2 warnings`；新增 V7 读者体验、Prompt 权限、project mapping、生成质量提示测试均通过。
- 前端：`npm test -- --run` 为 **9 个文件、32 tests passed**；`npm run build` 通过。
- E2E 最新复跑：`npm run test:e2e` 为 **17 passed、10 skipped、0 failed**；多出的 1 个 skip 是重执行控件在本次未观测到可操作异步 run 时按设计跳过，无 Provider key 的 AI 用例继续保持真实 skip/失败语义。
- 数据库最新：`alembic current` 为 `nc_v7_novel_project_mapping`；Prompt seed 8 个运行时身份的新默认版本已落库；`v7_novel_project_links` 回填 6994 条。
- ai-workbench 参考资产已形成评估文档并接入代码，不能把参考项目本身的弱自动评级当作生成质量证据。
- 强制 `bash scripts/ai_development_gate.sh` 仍为 exit 3；这是已解释的宽泛扫描告警，不等于 AI 真值检查失败，但也不能写成门禁全绿。

## 9. 真实 Provider 双轨与产品链复验（2026-08-02）

| 检查项 | 结果 | 证据 |
|---|---|---|
| V6 真实双轨 | 20/20 章节、平均 79.6、最低 72.0 | `dual-track-evidence.json` |
| V7 真实双轨 | 20/20 章节、平均 92.0、最低 91.0 | `dual-track-evidence.json` |
| V7 跨章交接契约 | 20/20 | `dual-track-evidence.json`、V6 `contents.meta` |
| 跨版本账本 | 369 成功、0 失败、3.190506 元 | `ai_execution_ledger` 对账 |
| Prompt provenance | V6 7 个、V7 6 个 Prompt identity | `ai_execution_ledger` 对账 |
| V6 书库/编辑器/完成度 | 真实 HTTP 200；20/20 reviewed | `product-chain-evidence.json` |
| TXT/Markdown/EPUB | 全部 HTTP 200；EPUB 有效 ZIP | `product-chain-evidence.json` |

自动回放和产品链当前为**可用**。盲评包虽已生成 20 个 case，但 0/20 case 有两位评审，故生成质量目标仍不能标记为**已验收**。

浏览器 E2E 最终复跑：**17 passed、10 skipped、0 failed**；10 个 skip 均为 Provider/异步状态/截图 opt-in 条件，不计入生成质量验收。

## 10. 生产部署验证（2026-08-02）

- `PROD_BASE=https://novel.xyjin.xyz backend/.venv/bin/python scripts/prod_smoke.py`：**15/15 通过**，未注入 Provider Key。
- `BASE_URL=https://novel.xyjin.xyz npx playwright test e2e/prod-walkthrough*.spec.ts`：**4 passed**。
- 生产迁移：`nc_v7_novel_project_mapping (head)`；8 个 runtime Prompt identity 已播种；发布前备份已生成。
- 生产 smoke/浏览器走查只证明部署和用户入口可用，不替代真实 20 章质量长跑与人工盲评。
