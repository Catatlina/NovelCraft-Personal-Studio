# 星禾AI工作台 · AI变更日志

> 版本：V1.0 | 日期：2026-07-20
>
> ⚠️ 每次AI修改必须记录。人类开发者修改也建议记录。

---

## 记录格式

```markdown
### YYYY-MM-DD | 变更人: <name> | 类型: <type>

**变更说明**：简述

**影响范围**：
- 涉及模块
- 涉及文件
- 数据影响
- API影响

**测试结果**：
- 后端: X passed
- 前端: X passed
- E2E: X passed

**关联文档**：更新的文档列表
```

---

## 变更记录

### 2026-07-20 | 变更人: AI Agent | 类型: docs

**变更说明**：根据V5.0总规范，创建完整的 `/docs` 文档体系（20份文档）

**影响范围**：
- 新增文件: SPEC_V5.md, COMPONENT_SPEC.md, TASK_SPEC.md, SKILL_SPEC.md, PLUGIN_SPEC.md, SECURITY_SPEC.md, AI_CODE_GATE.md, CODE_REVIEW_SPEC.md, CI_CD_RULES.md, PROJECT_STATUS.md, CHANGELOG_AI.md, TECH_DEBT.md
- 已有文件: PRODUCT.md, ARCHITECTURE.md, DESIGN_SYSTEM.md, UI_UX_GUIDE.md, DEVELOPMENT_RULES.md, AGENT_SPEC.md, API_SPEC.md, DATABASE_SCHEMA.md, ROADMAP.md

**测试结果**：N/A（纯文档）

**关联文档**：全量 `/docs/*`

---

### 2026-07-20 | 变更人: AI Agent | 类型: docs

**变更说明**：生成《星禾AI工作台 V4.0 多端产品与技术蓝图》

**影响范围**：
- 新增: /workspace/星禾AI工作台-V4.0-多端产品与技术蓝图.md

**测试结果**：N/A（纯文档）

---

### 2026-07-20 | 变更人: NovelCraft Team | 类型: feat

**变更说明**：前端加固 — 客户端超时/命令面板/Settings多页/扫榜归一指标/Vitest单测

**影响范围**：
- 前端: api.ts AbortController超时(60s/600s), CommandPalette.tsx, Settings拆分

**测试结果**：tsc 0错, vitest 9/9 passed

---

### 2026-07-20 | 变更人: NovelCraft Team | 类型: feat

**变更说明**：P2后端加固 — BYOK安全/锁fail-closed/JSONB提列/批次并行/上下文Token预算/断路器令牌桶/注入清洗

**影响范围**：
- 后端: byok.py, concurrency.py, context_budget.py, circuit_breaker.py, gateway.py

**测试结果**：context_budget(7) + circuit_breaker(9) passed
