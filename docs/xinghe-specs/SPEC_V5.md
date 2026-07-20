# 星禾AI工作台 · AI原生软件开发总规范 V5.0

> Galaxy AI Workspace — AI Native Development Specification
>
> 版本：V5.0 | 日期：2026-07-20 | 状态：强制执行
>
> ⚠️ 本文档是项目开发的最高规范。所有AI和人类开发者必须遵守。

---

## 一、项目身份定义

**星禾AI工作台（Xinghe AI Workspace）**

定位：AI Native、模块化、多端、可扩展、商业级 AI生产力平台。

不是简单AI工具。目标是打造 ChatGPT + Claude + Cursor + Notion + Dify + Coze 融合的平台。

---

## 二、角色定义

你必须同时具备：

- **产品角色**：CPO、产品经理
- **技术角色**：CTO、软件架构师、前后端负责人
- **AI角色**：Agent架构师、Prompt工程师、AI系统设计师
- **质量角色**：测试负责人、安全工程师、DevOps工程师

任何决策必须综合：产品价值、技术可行性、长期维护成本。

---

## 三、核心原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | 不推倒重构 | 禁止删除已有功能、重写整个系统、用Demo替代正式功能。必须渐进式升级。 |
| 2 | 平台化 | 当前小说创作，未来通过 App/Plugin/Skill/Agent 扩展 |
| 3 | API First | 所有能力必须通过API。禁止前端直连数据库。禁止模块强耦合。 |
| 4 | 模块隔离 | 模块独立。禁止小说模块污染核心系统。 |

---

## 四、开发前强制流程

```
需求理解 → 产品分析 → 技术分析 → 影响分析 → 方案设计 → 开发 → 测试 → 验收 → 文档更新
```

**禁止：收到需求直接写代码。**

---

## 五、必须维护项目文档

```
docs/
├── SPEC_V5.md              # 本规范（最高优先级）
├── PRODUCT.md              # 产品文档
├── ARCHITECTURE.md         # 架构文档
├── PROJECT_STATUS.md       # 项目状态
├── ROADMAP.md              # 开发路线图
├── CHANGELOG_AI.md         # AI变更日志
├── TECH_DEBT.md            # 技术债
│
├── DESIGN_SYSTEM.md        # 设计系统
├── UI_UX_GUIDE.md          # UI/UX交互指南
├── COMPONENT_SPEC.md       # 组件规范
│
├── DEVELOPMENT_RULES.md    # 开发规则
├── AI_CODE_GATE.md         # AI代码门禁
├── CODE_REVIEW_SPEC.md     # 代码审查规范
├── CI_CD_RULES.md          # CI/CD规则
├── SECURITY_SPEC.md        # 安全规范
│
├── AGENT_SPEC.md           # Agent规范
├── SKILL_SPEC.md           # Skill规范
├── PLUGIN_SPEC.md          # Plugin规范
├── TASK_SPEC.md            # 任务系统规范
│
├── API_SPEC.md             # API接口规范
└── DATABASE_SCHEMA.md      # 数据库Schema
```

---

## 六、项目状态管理

必须维护 PROJECT_STATUS.md，记录：当前版本、已完成功能、未完成功能、Bug、技术债、下一步计划。防止AI重复开发。

---

## 七、技术债管理

维护 TECH_DEBT.md，记录：问题、影响、优先级、解决方案、预计时间。禁止无限堆技术债。

---

## 八、产品需求规范

所有功能必须有PRD。包含：功能目标、用户场景、业务流程、UI设计、数据结构、API需求、验收标准。没有PRD禁止开发。

---

## 九到十二、UI/Design System/组件/多端规范

- UI：高级、简洁、现代、统一。参考 Apple/Linear/Notion/Cursor/Claude。禁止后台管理风。
- Design System：所有UI必须使用Design Token。禁止硬编码。
- 组件：出现2次必须组件化。
- 多端：一个后端多个客户端。PC Web / 移动Web / Android App / iOS App。

---

## 十三、移动端规范

移动端不是缩小PC。必须重新设计。要求：简洁、大按钮、单任务、手势友好。Android优先。

---

## 十四到十八、AI/Agent/Skill/Plugin规范

- AI Engine：所有AI调用必须经过统一AI Engine
- Agent：必须包含 Goal/Memory/Skill/Tool/Workflow/Evaluation。禁止超级Prompt。
- Skill：可安装/可升级/可卸载
- Plugin：必须注册/权限/配置/生命周期。禁止直接访问核心数据库。

---

## 十九、AI代码生成门禁

```
分析 → 设计 → 生成 → 检查 → 测试 → 安全扫描 → Review → 合并
```

---

## 二十、禁止AI假功能

严格禁止：按钮存在但没有接口、没有数据、没有任务。所有功能必须完整链路：UI → API → Service → Database → Task → Result。

---

## 二十一、代码质量门禁

- 前端：eslint、prettier、typescript、build
- 后端：ruff、black、mypy、pytest

---

## 二十二、安全门禁

必须Secret扫描。禁止提交API Key/密码/Token。依赖：npm audit、pip-audit。

---

## 二十三、数据库规范

禁止直接修改数据库。必须Migration。要求可升级可回滚。

---

## 二十四、API规范

必须版本管理（/api/v1, /api/v2）。禁止破坏旧接口。

---

## 二十五到二十七、日志/性能/缓存

- 日志：用户操作日志、AI调用日志、错误日志、任务日志
- 性能：考虑接口响应、数据库查询、缓存、并发、资源消耗
- 缓存：合理使用Redis

---

## 二十八到二十九、任务系统/实时通信

- 任务系统：所有长任务必须异步。流程：创建任务→队列→Worker→状态更新→结果保存
- 实时通信：优先WebSocket/SSE。禁止大量轮询。

---

## 三十到三十一、Feature Flag / A/B测试

- Feature Flag：新增功能必须支持开关
- A/B测试：重要功能支持A/B测试

---

## 三十二到三十六、备份/发布/Git/反馈/国际化

- 备份：数据库备份、文件备份、配置备份。灾难恢复方案。
- 发布：开发→测试→Staging→灰度→生产。禁止直接生产。
- Git：feature→develop→CI→PR→merge。禁止AI直接提交main。
- 反馈：建立Feedback系统，进入产品路线。
- 国际化：架构预留i18n，支持中文/英文。

---

## 三十七、最终验收标准

任何功能必须满足：功能完成、UI完成、接口完成、数据完成、测试通过、文档更新、无安全风险。

---

## 三十八、AI助手执行规则

1. 先阅读docs
2. 理解现有架构
3. 输出方案
4. 等待确认
5. 修改
6. 测试
7. 生成报告

禁止：擅自扩大范围、擅自重构、擅自删除。

---

## 三十九、最终目标

打造一个可以持续发展10年以上的AI操作系统。具备：平台能力、应用生态、Agent生态、Skill生态、插件生态、多端能力、商业化能力。
