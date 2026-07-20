# 星禾AI工作台 · 架构文档

> 版本：V1.0 | 日期：2026-07-20 | 角色：CTO · 软件架构师

---

## 一、当前架构（基于 NovelCraft V2.2）

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Frontend)                       │
│  React 19 · TypeScript · Vite · Tiptap                  │
│  29组件 · 19个Tab · Design Token (doc12)                │
│  状态管理：App集中state + 自定义hooks                     │
└────────────────────┬────────────────────────────────────┘
                     │ REST / SSE
                     │ Nginx (反向代理)
┌────────────────────┴────────────────────────────────────┐
│                  后端 (Backend)                          │
│  FastAPI · Python 3.11                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ api/v1/  │ │  ai/     │ │ services/│ │ workers/ │   │
│  │ 129路由  │ │ 4Provider│ │ 15服务   │ │ Celery   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ core/    │ │ gateway  │ │ config   │                │
│  │ authz    │ │ AI调度   │ │ 配置管理  │                │
│  │ retry    │ │ 断路器   │ │          │                │
│  │ byok     │ │ Token预算│ │          │                │
│  └──────────┘ └──────────┘ └──────────┘                │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│                  数据层 (Data)                           │
│  PostgreSQL (26+表, pgvector) · Redis · Celery Beat     │
└─────────────────────────────────────────────────────────┘
```

### 当前项目结构

```
backend/app/
├── api/v1/           # API路由（扁平结构）
│   ├── auth.py
│   ├── projects.py
│   ├── novels.py
│   ├── ranking.py
│   ├── library.py
│   ├── knowledge.py
│   ├── publish.py
│   ├── ...
│   └── admin/
├── ai/               # AI Provider
│   └── providers/    # deepseek/claude/openai/gemini
├── core/             # 基础设施
│   ├── security.py
│   ├── authz.py      # 统一鉴权
│   ├── retry.py      # 重试策略
│   ├── byok.py       # 密钥安全
│   ├── circuit_breaker.py
│   ├── context_budget.py
│   └── billing.py
├── services/         # 业务服务（15个）
├── workers/          # Celery任务
├── gateway.py        # AI调用网关
├── main.py           # FastAPI入口
├── config.py
└── db.py

frontend/src/
├── components/       # 29个组件
├── lib/              # api.ts, offlineCache.ts
├── design/           # tokens.css, compat.css
├── theme/            # tokens.ts
├── App.tsx           # 编排器
└── main.tsx
```

---

## 二、目标架构（V1 → V2 → V3）

### V1 目标架构：平台底座

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Web)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  │ 工作台   │ │ 小说App  │ │ 设置     │                │
│  │ Dashboard│ │ NovelApp │ │ Settings │                │
│  └──────────┘ └──────────┘ └──────────┘                │
│  共享：Design System · API Client · Hooks               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────────┐
│              后端 — 模块化单体                           │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │              AI Engine（新增）                     │  │
│  │  统一入口 · Prompt管理 · Token统计 · 成本追踪      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ apps/    │ │ platform/│ │ core/    │               │
│  │ novel/   │ │ skills/  │ │ authz    │               │
│  │ content/ │ │ agents/  │ │ security │               │
│  │ hotspot/ │ │ plugins/ │ │ billing  │               │
│  └──────────┘ └──────────┘ └──────────┘               │
│                                                        │
│  api/v1/ — 保持兼容，不破坏现有路由                       │
└─────────────────────────────────────────────────────────┘
```

### V1 后端目录结构（渐进迁移，不一次搬家）

```
backend/app/
├── core/              # 核心基础设施（保持）
│   ├── security.py
│   ├── authz.py
│   ├── retry.py
│   ├── byok.py
│   ├── circuit_breaker.py
│   ├── context_budget.py
│   ├── concurrency.py
│   └── billing.py
│
├── engine/            # 🆕 AI Engine（新增）
│   ├── __init__.py
│   ├── router.py          # 统一AI调用入口
│   ├── provider_manager.py
│   └── token_tracker.py
│
├── apps/              # 🆕 应用层（新增，渐进迁移）
│   ├── __init__.py
│   └── novel/             # 小说App
│       ├── __init__.py
│       ├── router.py      # 从 api/v1/novels.py 渐进迁移
│       └── skills/        # 小说专用Skills
│
├── platform/          # 🆕 平台扩展（新增）
│   ├── __init__.py
│   ├── skills/            # Skill管理
│   │   ├── manager.py
│   │   └── builtin/       # 内置Skills
│   ├── agents/            # Agent管理
│   │   ├── manager.py
│   │   └── builtin/       # 内置Agents
│   └── plugins/           # Plugin管理（V2+）
│
├── api/v1/            # API路由（保持兼容）
├── ai/                # AI Provider（保持）
├── services/          # 业务服务（保持）
├── workers/           # Celery任务（保持）
├── gateway.py         # AI调用网关（保持，逐步迁移到engine）
├── main.py
├── config.py
└── db.py
```

---

## 三、模块边界（重要）

### 核心规则

```
┌─────────────────────────────────────────────┐
│  任何模块调用AI，必须通过 AI Engine           │
│                                             │
│  ✅ 正确：                                   │
│  NovelApp → AI Engine → Provider            │
│                                             │
│  ❌ 错误：                                   │
│  NovelApp → OpenAI API（直接调用）           │
└─────────────────────────────────────────────┘
```

### 模块职责

| 模块 | 可以做什么 | 不能做什么 |
|------|-----------|-----------|
| **apps/novel** | 小说CRUD、扫榜、成书流程 | 不能直接调Provider、不能修改其他App数据 |
| **engine** | AI调用、模型路由、Token统计 | 不包含业务逻辑 |
| **platform/skills** | Skill注册/安装/启用/禁用/执行 | 不定义Skill内容（内容在App中） |
| **platform/agents** | Agent注册/编排/运行/状态 | 不定义Agent目标（目标在App中） |
| **core** | 认证、鉴权、安全、计费 | 不包含业务逻辑 |

### 数据归属

```
项目 → 属于某个App
小说 → 属于小说App（apps/novel）
知识库条目 → 属于知识库系统
用户 → 属于core（跨App共享）
AI调用记录 → 属于engine（跨App共享）
```

---

## 四、关键架构决策（ADR）

| ID | 决策 | 理由 | 日期 |
|----|------|------|------|
| ADR-001 | 保持模块化单体，不做微服务 | 当前团队规模1-5人，微服务运维成本>收益 | 2026-07 |
| ADR-002 | 渐进迁移到apps/目录，不一次搬家 | 现有代码稳定，大搬家风险高 | 2026-07 |
| ADR-003 | AI调用必须通过AI Engine | 统一Token统计、成本追踪、模型路由 | 2026-07 |
| ADR-004 | 前端不引入zustand/TanStack Query | 当前App集中state+hooks足够，降低复杂度 | 2026-07 |
| ADR-005 | 不引入react-router | 内部state切换足够，后续按需加hash路由 | 2026-07 |
| ADR-006 | 数据库保持单头线性迁移 | Alembic单头，合并冲突取两侧超集 | 2026-07 |
| ADR-007 | BYOK密钥不落库 | 浏览器密钥仅内存存储，关闭会话清除 | 2026-07 |

---

## 五、数据库

### 核心表（26+张）

| 类别 | 表 | 说明 |
|------|-----|------|
| **用户** | users, user_settings | 用户与设置 |
| **认证** | api_keys | BYOK密钥引用 |
| **项目** | projects, project_members | 项目与成员 |
| **小说** | novels, chapters, contents | 小说/章节/内容 |
| **扫榜** | ranking_snapshots, ranking_items, book_analyses | 榜单数据 |
| **工作流** | runs, run_nodes, run_events | 工作流执行 |
| **知识库** | knowledge_items, knowledge_embeddings | 知识条目+向量 |
| **发布** | publish_records, platform_connections | 发布记录 |
| **协作** | collaboration_invites, operation_logs | 协作 |
| **计费** | ai_calls, budgets, subscriptions, plans | AI调用/预算/套餐 |
| **Skill** | 🆕 skills, skill_installations | Skill定义/安装 |
| **Agent** | 🆕 agents, agent_runs | Agent定义/运行 |

> 详见 [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)

---

## 六、API设计原则

| 原则 | 说明 |
|------|------|
| **统一信封** | `{code, message, data}` |
| **版本化** | `/api/v1/` |
| **流式优先** | AI调用默认SSE |
| **幂等性** | 写操作带 `Idempotency-Key` |
| **向后兼容** | 新增路由，不删除/修改现有路由 |

> 详见 [API_SPEC.md](./API_SPEC.md)

---

## 七、安全架构

| 层级 | 措施 |
|------|------|
| **传输** | HTTPS + Nginx |
| **认证** | JWT (access + refresh token) |
| **鉴权** | 统一authz.py，角色层级 viewer(0) < editor(1) < owner(2) |
| **AI密钥** | BYOK内存存储，不落库，关闭会话清除 |
| **平台凭据** | Fernet加密存储 |
| **注入防护** | Prompt输入清洗（控制字符+注入短语过滤） |
| **限流** | slowapi + 断路器 + 令牌桶 |

---

> **下一步**：阅读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md) 了解开发纪律
