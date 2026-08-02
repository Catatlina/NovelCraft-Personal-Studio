# Starlume AI 全量测试汇总报告（2026-08-02）

> 汇总本会话（2026-07-31 ～ 2026-08-02）执行的全部测试与验证结果。
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
| **Playwright E2E 全量** | **17 passed / 10 skipped / 0 failed**（27 用例，10 skip 均为 AI Key 未注入或条件性跳过，非失败；明细见 `docs/E2E_RESULT_20260802.md`） |

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

- ~~前端 Playwright e2e 全量（#164）~~ ✅ **已完成**（17 passed / 0 failed，见 `docs/E2E_RESULT_20260802.md`）
- ~~生产 Web 功能走查（#162）~~ ✅ **已完成**（见第 3 节）
- 覆盖率统计（#171）—— 未执行（整体≥70% / 核心≥80% 待跑）

---

*报告生成：2026-08-02 · 本地与生产版本一致：720f40b*
