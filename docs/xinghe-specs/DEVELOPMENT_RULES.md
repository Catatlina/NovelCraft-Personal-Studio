# 星禾AI工作台 · 开发规则

> 版本：V1.0 | 日期：2026-07-20 | 角色：CTO
>
> ⚠️ 本文档对AI和人类开发者都具有强制约束力。

---

## 一、开发前必读

**最高规范：[SPEC_V5.md](./SPEC_V5.md)** — 项目开发最高宪法

**任何代码修改前，必须先读取以下文档：**

1. [SPEC_V5.md](./SPEC_V5.md) — 总规范（最高优先级）
2. [PRODUCT.md](./PRODUCT.md) — 了解产品定位和非目标
3. [ARCHITECTURE.md](./ARCHITECTURE.md) — 了解模块边界
4. [PROJECT_STATUS.md](./PROJECT_STATUS.md) — 了解当前项目状态
5. [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md) — 了解UI规范
6. [UI_UX_GUIDE.md](./UI_UX_GUIDE.md) — 了解交互规范
7. [COMPONENT_SPEC.md](./COMPONENT_SPEC.md) — 了解组件清单
8. [ROADMAP.md](./ROADMAP.md) — 了解开发计划
9. [AGENT_SPEC.md](./AGENT_SPEC.md) — 如果涉及Agent开发
10. [SKILL_SPEC.md](./SKILL_SPEC.md) — 如果涉及Skill开发
11. [PLUGIN_SPEC.md](./PLUGIN_SPEC.md) — 如果涉及Plugin开发
12. [API_SPEC.md](./API_SPEC.md) — 如果涉及API修改
13. [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) — 如果涉及数据库修改
14. [SECURITY_SPEC.md](./SECURITY_SPEC.md) — 如果涉及安全相关
15. [TASK_SPEC.md](./TASK_SPEC.md) — 如果涉及异步任务

---

## 二、修改前必须分析

### 任何代码修改前，必须输出：

```
《修改影响分析》
├── 修改目标：要解决什么问题
├── 涉及文件：具体哪些文件需要修改
├── 涉及模块：影响哪些模块
├── 数据影响：是否涉及数据库变更
├── API影响：是否改变API契约
├── 前端影响：前端哪些组件受影响
├── 风险分析：可能出问题的地方
└── 测试方案：如何验证修改正确
```

### 未经影响分析，禁止直接修改代码。

---

## 三、禁止事项

| ❌ 禁止 | 说明 |
|--------|------|
| **删除功能** | 不能删除现有功能、接口、数据 |
| **删除API** | 不能删除现有API端点 |
| **假数据** | 不能用Mock/假数据替代真实逻辑 |
| **临时方案** | 不能用临时方案代替正式方案 |
| **破坏兼容** | 不能改变现有API的请求/响应格式 |
| **直接调Provider** | 任何模块不能绕过AI Engine直接调AI |
| **硬编码颜色** | 必须使用Design Token |
| **重复造组件** | 同类组件出现2次必须抽离 |
| **页面内写CSS** | 样式必须在Design Token或组件内定义 |
| **跳过测试** | 必须测试功能/接口/数据库/异常/边界 |

---

## 四、开发流程

```
需求分析
    ↓
方案设计
    ↓
影响分析  ← 必须输出书面分析
    ↓
开发
    ↓
测试（功能/接口/数据库/异常/边界）
    ↓
输出《开发变更报告》
```

---

## 五、开发变更报告模板

每次开发完成后，必须输出：

```markdown
## 《开发变更报告》

### 修改内容
- 具体修改了哪些文件和功能

### 新增功能
- 新增了什么能力

### 测试结果
- 后端测试: X passed / Y skipped
- 前端测试: X passed
- E2E测试: X passed
- 手动验证: 截图或描述

### 风险
- 可能的影响和风险点
```

---

## 六、代码规范

### 6.1 前端规范

```
组件化原则：
页面只负责组合，业务逻辑放入 hooks/service

目录规范：
components/   # 通用组件
pages/        # 页面（组合组件）
hooks/        # 自定义hooks
lib/          # 工具函数、API客户端

样式规范：
所有颜色 → var(--token-name)
所有间距 → var(--space-N)
所有字号 → var(--text-N)
禁止裸色值（stylelint守卫）
```

### 6.2 后端规范

```
模块化原则：
保持模块化单体架构，不要过早微服务

目录规范：
apps/         # 应用层（业务模块）
engine/       # AI Engine
platform/     # Skill/Agent/Plugin
core/         # 基础设施
api/v1/       # API路由（保持兼容）

新增功能：
先考虑放在 apps/ 下作为独立模块
保持 api/v1/ 向后兼容
```

### 6.3 AI调用规范

```
所有AI调用必须：
1. 通过 AI Engine (engine/)
2. 记录到 ai_calls 表
3. 经过 Token 统计
4. 经过预算校验
5. 经过断路器/重试/超时保护

禁止：
直接 import openai / anthropic
绕过 gateway.py
```

---

## 七、测试要求

| 测试类型 | 要求 |
|----------|------|
| **后端单元测试** | pytest，新增功能必须有测试 |
| **前端单元测试** | vitest，组件必须有测试 |
| **E2E测试** | Playwright，核心链路必须有 |
| **API契约测试** | 验证OpenAPI schema |
| **数据库迁移测试** | upgrade → downgrade → upgrade 循环 |

### 禁止：只看页面就算测试通过。

必须验证：
- ✅ 功能正确
- ✅ API返回正确
- ✅ 数据库变更正确
- ✅ 异常情况处理正确
- ✅ 边界情况处理正确

---

## 八、文档更新规则

```
开发完成后，必须检查是否需要更新：

□ SPEC_V5.md       — 如果规范本身需要调整
□ PRODUCT.md       — 新增功能？更新能力清单
□ ARCHITECTURE.md  — 架构变化？更新架构图
□ PROJECT_STATUS.md — 完成任务？更新状态
□ API_SPEC.md      — API变更？更新接口文档
□ DATABASE_SCHEMA.md — 表结构变更？更新Schema
□ DESIGN_SYSTEM.md — 新增组件？更新组件清单
□ COMPONENT_SPEC.md — 新增组件？更新组件文档
□ UI_UX_GUIDE.md   — 交互变更？更新指南
□ ROADMAP.md       — 完成任务？标记完成
□ CHANGELOG_AI.md  — 任何变更？记录日志
□ TECH_DEBT.md     — 产生技术债？登记
```

---

## 九、Git规范

```
分支命名：
feature/xxx    — 新功能
fix/xxx        — 修复
refactor/xxx   — 重构
docs/xxx       — 文档

Commit信息：
<type>: <简短描述>

类型：
feat: 新功能
fix: 修复
refactor: 重构
docs: 文档
test: 测试
chore: 杂项

示例：
feat: 新增AI Engine统一调用入口
fix: 修复SSE流式断连重试问题
docs: 更新API_SPEC.md添加Skill接口
```

---

## 十、质量门禁

合并前必须通过：

| 门禁 | 标准 |
|------|------|
| **后端测试** | 全部通过 |
| **前端构建** | tsc --noEmit 0错误 |
| **前端测试** | 全部通过 |
| **E2E测试** | 核心链路通过 |
| **Lint** | stylelint + eslint 0警告 |
| **安全扫描** | SAST CI通过 |
| **OpenAPI验证** | schema有效 |

---

> ⚠️ 以上规则对AI和人类开发者同等生效。违反规则 = 代码不合规。
