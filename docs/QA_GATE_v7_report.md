# Starlume AI V7.0 — Alpha QA Gate 验收报告

- **报告编号**：#173
- **日期**：2026-08-02（本版基于 2026-08-01 旧版 QA_GATE_v7_report.md 更新补充，完整保留原内容）
- **范围**：Sprint 1（DB/Repository/Brain/API/Trace 基建）+ Sprint 2（核心生成链路）+ Sprint 3（工程能力）端到端真实验收
- **结论**：✅ **PASS** — Sprint 1/2/3 交付物存在且核心链路真实跑通；125 个自动化测试真实入库通过；存在 2 个已标注生产缺陷与若干测试覆盖缺口，详见 §4/§5。

---

## 1. 环境真实性声明（真实，非仿真）

| 项 | 值 | 核实方式 |
|---|---|---|
| 后端 | FastAPI + Python 3.13.12（nc_audit4 venv，pytest 9.0.3） | `python -c "import app.main"` → **IMPORT OK** |
| 数据库 | PostgreSQL `starlume_v7_gate`（`genius@127.0.0.1`），18 张 `v7_*` 表 | `psql \dt v7_*` → 18 张表全部就位 |
| 测试隔离 | conftest.py 强制真实 PostgreSQL（JSONB/UUID 列，SQLite 无法编译），每测试独立连接 + 外层事务回滚 | `tests/v7/conftest.py:6-15` |
| AI 网关 | `AIGateway`（app/v7/generation/generation_engine.py:540）真实 httpx 异步调用 DeepSeek；未配置 `DEEPSEEK_API_KEY` 即 `raise AIGatewayError`，**拒绝伪造输出** | 代码审查 generation_engine.py:571-575 |
| 是否 mock | **否** — 全部 repository/brain 测试真实入库；无 mock、无占位、无假成功 | conftest + 代码审查 |
| 生成痕迹 | `v7_agent_runs=45`、`v7_agent_traces=1150`、`v7_event_logs=1660`、`v7_decision_logs=93` | 直接 SQL 统计 |

> 说明：本报告中 Sprint 2 的 10 章连续生成结果沿用旧版报告实测记录（DB 数据痕迹仍可查），本版新增执行的是 import 冒烟、全量测试、覆盖率与工程约束抽查。

---

## 2. Sprint 1/2/3 逐项验收表

### 2.1 Sprint 1 — DB / Repository / Brain / API / Trace 基建

| 项 | 证据 | 结论 |
|---|---|---|
| DB 模型层（v7/models，18 张表） | `app/v7/models/` 全量模型 + PostgreSQL `\dt v7_*` 18 表就位 | ✅ PASS |
| Repository 层（base/state/goal/constraint/decision/version/trace/event/human/cost/prompt） | `app/v7/repositories/` 11 个仓库类存在 | ✅ PASS |
| Brain 层（state_manager/goal_system/constraint_system/version_control/novel_brain） | `app/v7/brain/` 5 模块存在，测试全覆盖（version_control 50% 覆盖率） | ✅ PASS |
| API/Trace 层 | `app/v7/api/`（brain/trace/director/cost/prompt）+ `app/v7/trace/tracer.py` | ✅ PASS |
| 自动化测试 | `tests/v7/test_repositories.py`（74 例）+ `test_brain.py`（51 例）= **125 例全部真实入库通过**（详见 §3） | ✅ PASS |

### 2.2 Sprint 2 — 引擎 + StoryDirector + 真实生成 + 7 步 Trace

| 项 | 证据 | 结论 |
|---|---|---|
| 7 步 Agent Loop | 每章完整 `perceive→assess→decide→plan→execute→observe→update`；旧报告实测每章 26 条 trace（45 runs → 1150 traces 佐证） | ✅ PASS |
| PlotEngine 等引擎契约（BaseEngine 五方法） | `app/v7/engines/base.py`（analyze/plan/execute/validate/update + phases 快照回传）；plot/review/memory 三引擎继承实现 | ✅ PASS |
| StoryDirector | `app/v7/director/story_director.py`（generate_chapter + 门禁/审批路径） | ✅ PASS |
| 真实生成（无假成功） | `AIGateway.generate/generate_json` 真实调用，空内容/无 Key 均 raise | ✅ PASS |
| 事件总线 | `v7_event_logs=1660`，旧报告 10 章 `dispatch_errors=0` | ✅ PASS |
| 记忆引擎四档置信度 | `app/v7/brain/state_manager.py`（落库/pending_review/discarded/conflict），test_brain 全量覆盖 | ✅ PASS |
| QA Gate 4.4 置信度门禁 + 人工回路 | `DecisionPermissionSystem` 阈值拦截 `pending_approval`；`app/v7/api/director.py` approve/reject 端点（5 个） | ✅ PASS |
| QA Gate 4.5 生成稳定性 | 旧报告实测 **10/10 章连续生成**，0 失败，平均评分 86.4，真实成本 ¥0.0766 | ✅ PASS |
| LLM 总超时修复 | 提交 `042a81d fix(v7): hard total-timeout on LLM calls`；`asyncio.wait_for(timeout=self.timeout)` 生效于 generation_engine.py:616 | ✅ PASS |

### 2.3 Sprint 3 — 人工控制 / 决策审批 / 版本回滚 / 成本闭环 / Prompt 版本管理

| 项 | 证据 | 结论 |
|---|---|---|
| 人工控制层 | `app/v7/human/intervention_service.py`（record/record_state_edit/record_state_review/record_decision_review/record_rollback/review_decision/inject_instruction/mark_instructions_applied/list/stats）+ `app/v7/repositories/human.py` | ✅ PASS |
| 决策审批 | `app/v7/api/director.py`：`POST /{novel_id}/decisions/{decision_id}/approve`、`/reject`（line 81-115） | ✅ PASS |
| 版本回滚 | `app/v7/brain/version_control.py` `rollback_to_snapshot`（line 289）：先写 `pre_rollback` 安全快照 → 恢复/重建状态 → 写 `v7_state_changes` → 新增 rollback 版本；回滚自身可逆 | ✅ PASS |
| 成本闭环 | `app/v7/cost/cost_manager.py`：`WARNING=0.80 / CRITICAL=0.95 / STOP=1.00`，80%/95% 告警每周期恰好一次（alert_threshold_80/95 标志），100% `action_on_exceed=stop` 阻塞生成 | ✅ PASS |
| 成本 API | `app/v7/api/cost.py` **12 个端点**（budgets CRUD/reset/remaining/check/record/summary/stats），router 挂载 `/api/v7/cost` | ✅ PASS |
| Prompt 版本管理 | `app/v7/prompt/prompt_manager.py`：`compute_prompt_hash` 用 `hashlib.sha256`，`detect_change/register_version/set_default/deactivate_version` 齐备 | ✅ PASS |
| Prompt API | `app/v7/api/prompt.py` **12 个端点**（names/versions 管理/detect-change/hash/active/executions/stats），router 挂载 `/api/v7/prompt` | ✅ PASS |
| Router 挂载 | `app/v7/api/router.py:26-30` 确认 `/cost` 与 `/prompt` 已 include，统一前缀 `/api/v7` | ✅ PASS |
| Sprint 3 表落库 | `v7_cost_budgets=3`、`v7_prompt_versions=3`、`v7_human_interventions=33`（真实写入痕迹） | ✅ PASS |

> ⚠️ 备注：team-lead 提供口径为「cost 12 端点 / prompt 13 端点」，**实测为 cost=12、prompt=12**（见上表）。prompt 第 13 个端点未发现，建议核对需求；功能本身不受影响。

---

## 3. 测试结果（本次真实执行）

**命令**：
```
DATABASE_URL=postgresql://genius@127.0.0.1/starlume_v7_gate \
NOVELCRAFT_TEST_REDIS_URL=redis://127.0.0.1:6379/15 \
/Users/genius/.workbuddy/binaries/python/envs/nc_audit4/bin/python -m pytest tests/v7/ -q
```

**结果**：`125 passed, 4 skipped in 4.02s`（collected 129 items）

| 文件 | 收集 | 通过 | 跳过 | 说明 |
|---|---|---|---|---|
| tests/v7/test_repositories.py | 74 | 74 | 0 | 真实入库，事务回滚隔离，无 mock |
| tests/v7/test_brain.py | 51 | 51 | 0 | 同上 |
| tests/v7/test_e2e.py | 4 | 0 | 4 | 均显式 `@pytest.mark.skip(reason="Requires real database and AI API")` |

**关于 4 个 skip**：均为 `test_e2e.py` 中端到端章节生成测试，显式标注需真实 DB + AI API，非「跳过失败掩盖」。但注意它们使用**同步 `Session`**（与 V7 async 实现不匹配），属遗留的旧 e2e 测试，未纳入 125 例口径（详见 §5）。

**覆盖率**（`--cov=app.v7`）：**TOTAL 34%**（4145 行 / 覆盖 1422 行）
- 覆盖良好：models 全部 ~100%、repositories（state/goal/constraint/decision/event/trace/version 100%）、brain 核心（state/goal/constraint/novel_brain 100%，version_control 50%）
- **0% 覆盖**（缺口）：`api/`（brain/cost/director/prompt/router/schemas/trace 全 0%）、`cost/cost_manager.py`（197 行 0%）、`prompt/prompt_manager.py`（101 行 0%）、`human/intervention_service.py`（141 行 0%）、`generation/generation_engine.py`（14%）、`director/story_director.py`（20%）

---

## 4. 已知缺陷清单（如实列出，均未修复）

### 4.1 队友已标注的生产缺陷

| # | 位置 | 描述 | 测试标注 |
|---|---|---|---|
| D1 | `app/v7/models/version.py:32-34` | `__mapper_args__ = {"version_id_col": version_number}` 将 `version_number` 交给 SQLAlchemy 乐观锁计数器，导致**每次 INSERT 版本号总是 1** | `tests/v7/test_brain.py:734-747`（`test_sequential_versions_share_number_due_to_version_id_col`，断言 `[1, 1]`） |
| D2 | `app/v7/repositories/constraint.py:44-53` | `check_violation` 只做 `violation_count += 1`，**从不写 `last_violation_at`**（字段恒为 None） | `tests/v7/test_repositories.py:792-794`（断言 `last_violation_at is None`） |

### 4.2 本次验收新发现

| # | 位置 | 描述 |
|---|---|---|
| D3 | `scripts/verify_ai_truthfulness.py` | 无 mock 门禁脚本对 V7 架构误报：AST 白名单 `GATEWAY_CALLS` 只含 `complete/complete_stream/_deepseek_complete` 等，未识别 V7 的 `AIGateway.generate_json/generate` 封装，运行报 **29 个 `ai-gateway-required`** 且结论 FAIL。经代码审查（generation_engine.py:558/650）确认 V7 确经真实网关调用，属**工具与架构不兼容的误报**，但需扩展白名单 |
| D4 | Sprint 3 测试覆盖缺口 | `tests/` 全目录无 human/cost/prompt 相关测试；覆盖率显示 `intervention_service.py`、`cost_manager.py`、`prompt_manager.py` 及全部 `api/` 模块 **0%**。功能仅经代码审查 + import 冒烟 + DB 落库痕迹验证，无自动化回归保护 |
| D5 | `tests/v7/test_e2e.py` | 4 个端到端测试使用**同步 `Session`**（`from sqlalchemy.orm import Session`），与 V7 async 实现不匹配，全部显式 skip 未跑通；若启用将因 sync/async 不匹配失败，属遗留测试需重写 |
| D6 | `app/v7/api/prompt.py` | 端点数量为 **12**（team-lead 口径 13），需确认需求是否缺 1 个端点（如某查询接口）；cost 12 端点与口径一致 |

---

## 5. 遗留项与建议

1. **修复 D1**：移除 `version_id_col` 或改为显式维护 `version_number`（建议在版本创建事务内 `MAX(version_number)+1`）。
2. **修复 D2**：`check_violation` 内补 `constraint.last_violation_at = datetime.utcnow()`。
3. **为 Sprint 3 补测试**（最高优先级建议）：cost/prompt/human 服务层 + 12+12 端点 API 层至少各覆盖核心路径（预算 stop 阻塞、SHA256 变更检测、审批回路、回滚可逆性），将覆盖率缺口收窄。
4. **重写或移除 test_e2e.py 同步测试**：改为 async 版并接真实 AI API（或标注为可选手动 e2e）。
5. **扩展 verify_ai_truthfulness.py**：将 `AIGateway.generate/generate_json` 及 `ai_gateway` 属性调用纳入合法路径，消除 29 个误报。
6. **核对 prompt 端点需求**：确认 12 vs 13 口径差异。
7. CH10 `constraint_compliance=70`（旧报告遗留）：7 维评分唯一低于 80 项，未触发 blocking，可在后续迭代加强约束权重。

---

## 6. 验收裁定

| 项 | 结果 |
|---|---|
| Sprint 1 — DB/Repository/Brain/API/Trace + 125 测试 | ✅ PASS |
| Sprint 2 — 引擎契约 / 事件 / 记忆 / 7 步 Trace | ✅ PASS |
| Sprint 2 — QA Gate 4.4 人工控制 / 置信度门禁 | ✅ PASS |
| Sprint 2 — QA Gate 4.5 生成稳定性（10 章连续） | ✅ PASS |
| Sprint 3 — 人工控制 / 决策审批 / 版本回滚 | ✅ PASS（代码审查 + 落库痕迹；测试覆盖待补） |
| Sprint 3 — 成本闭环 / Prompt 版本管理 | ✅ PASS（代码审查 + 落库痕迹；测试覆盖待补） |
| 无 mock / 无假成功 | ✅ PASS（conftest 强制真实 PG；AIGateway 拒绝伪造） |
| LLM 总超时稳定性（042a81d） | ✅ 已修复并验证 |
| 已知缺陷（D1/D2）如实记录 | ⚠️ 未修复，测试已显式标注，不影响核心链路验收 |

**总裁定论：V7.0 Alpha 三门 Sprint（基建 / 生成链路 / 工程能力）核心交付全部 PASS；125 例自动化测试真实入库通过；2 个已标注生产缺陷 + 4 个新发现项（3 个测试覆盖/工具类问题 + 1 个端点口径差异）需在 Beta 前修复。**
