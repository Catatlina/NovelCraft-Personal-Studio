# 星禾AI工作台 · 数据库Schema

> 版本：V1.0 | 日期：2026-07-20 | 角色：后端架构师
>
> 基于 NovelCraft V2.2 现有26+张表，扩展V1新增表。

---

## 一、数据库概览

- **数据库**：PostgreSQL + pgvector（向量检索）
- **迁移工具**：Alembic（单头线性迁移）
- **当前迁移版本**：17个迁移
- **表数量**：26+张

---

## 二、现有核心表（保持）

### 2.1 用户与认证

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户 | id, username, email, password_hash, is_active |
| `user_settings` | 用户设置 | user_id, theme, default_model |
| `api_keys` | BYOK密钥引用 | user_id, provider, key_ref (不存明文) |

### 2.2 项目与小说

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `projects` | 项目 | id, name, owner_id, status |
| `project_members` | 项目成员 | project_id, user_id, role (viewer/editor/owner) |
| `novels` | 小说 | id, project_id, title, genre, status, word_count |
| `chapters` | 章节 | id, novel_id, chapter_number, title, status |
| `contents` | 内容 | id, chapter_id, body (TipTap JSON), version |

### 2.3 扫榜

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `ranking_sources` | 榜单数据源 | id, name, platform, url |
| `ranking_snapshots` | 榜单快照 | id, source_id, scanned_at |
| `ranking_items` | 榜单条目 | id, snapshot_id, title, author, metrics |
| `book_analyses` | 书籍分析 | id, item_id, analysis_json |

### 2.4 工作流

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `runs` | 运行记录 | id, novel_id, workflow_type, status |
| `run_nodes` | 运行节点 | id, run_id, node_type, status, output |
| `run_events` | 运行事件 | id, run_id, event_type, data |

### 2.5 知识库

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `knowledge_items` | 知识条目 | id, project_id, title, content, tags |
| `knowledge_embeddings` | 向量嵌入 | id, item_id, embedding (pgvector) |

### 2.6 发布

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `platform_connections` | 平台连接 | id, user_id, platform, credentials (Fernet加密) |
| `publish_records` | 发布记录 | id, content_id, platform, status |

### 2.7 协作

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `collaboration_invites` | 邀请 | id, project_id, email, role, status |
| `operation_logs` | 操作日志 | id, project_id, user_id, action, detail |

### 2.8 计费

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `plans` | 套餐 | id, name, monthly_budget_cny, price |
| `subscriptions` | 订阅 | id, user_id, plan_id, status, expires_at |
| `budgets` | 预算 | id, subscription_id, used_cny |
| `ai_calls` | AI调用记录 | id, user_id, provider, model, input_tokens, output_tokens, cost_cny |

---

## 三、V1新增表

### 3.1 Skill系统

```sql
-- Skill定义表
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,          -- skill_novel_explosive_title
    name VARCHAR(200) NOT NULL,                 -- 爆款标题生成
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    category VARCHAR(50) NOT NULL,              -- novel / content / tool
    description TEXT,
    author VARCHAR(200) DEFAULT '星禾官方',
    icon VARCHAR(50),
    input_schema JSONB NOT NULL,                -- 输入参数定义
    output_schema JSONB NOT NULL,               -- 输出格式定义
    prompt_template VARCHAR(200),               -- Prompt模板引用
    model_preference VARCHAR(50),               -- 推荐模型
    estimated_tokens INTEGER DEFAULT 500,
    is_builtin BOOLEAN DEFAULT FALSE,           -- 是否内置
    is_public BOOLEAN DEFAULT FALSE,            -- 是否公开
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Skill安装表（用户-Skill关联）
CREATE TABLE skill_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    status VARCHAR(20) DEFAULT 'active',        -- active / disabled
    installed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, skill_id)
);

-- Skill执行记录
CREATE TABLE skill_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    inputs JSONB NOT NULL,
    outputs JSONB,
    ai_call_id UUID REFERENCES ai_calls(id),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### 3.2 Agent系统

```sql
-- Agent定义表
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,          -- agent_novel_author
    name VARCHAR(200) NOT NULL,
    version VARCHAR(20) DEFAULT '1.0.0',
    category VARCHAR(50) NOT NULL,
    description TEXT,
    goal JSONB NOT NULL,                        -- Agent目标定义
    workflow JSONB NOT NULL,                    -- DAG工作流定义
    memory_config JSONB,                        -- 记忆配置
    model_preference JSONB,                     -- 模型偏好
    trigger_type VARCHAR(20) DEFAULT 'manual',  -- manual / scheduled / event
    trigger_config JSONB,                       -- 触发配置
    is_builtin BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Agent-Skill关联表
CREATE TABLE agent_skills (
    agent_id UUID NOT NULL REFERENCES agents(id),
    skill_id UUID NOT NULL REFERENCES skills(id),
    PRIMARY KEY (agent_id, skill_id)
);

-- Agent运行记录
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    user_id UUID NOT NULL REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    status VARCHAR(20) DEFAULT 'pending',       -- pending/running/waiting_human/completed/failed
    current_step VARCHAR(100),
    progress DECIMAL(5,2) DEFAULT 0,            -- 0.00 ~ 100.00
    inputs JSONB,
    outputs JSONB,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Agent运行步骤记录
CREATE TABLE agent_run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES agent_runs(id),
    step_id VARCHAR(100) NOT NULL,              -- 对应workflow中的step.id
    step_name VARCHAR(200),
    skill_id UUID REFERENCES skills(id),
    status VARCHAR(20) DEFAULT 'pending',
    inputs JSONB,
    outputs JSONB,
    ai_call_id UUID REFERENCES ai_calls(id),
    retry_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

### 3.3 Plugin系统（V2+ 预留）

```sql
-- Plugin定义表（V2实现）
CREATE TABLE plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    version VARCHAR(20) DEFAULT '1.0.0',
    type VARCHAR(50) NOT NULL,                  -- datasource / publish / format / provider / theme
    description TEXT,
    author VARCHAR(200),
    config_schema JSONB,
    is_builtin BOOLEAN DEFAULT FALSE,
    is_public BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Plugin安装表
CREATE TABLE plugin_installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    plugin_id UUID NOT NULL REFERENCES plugins(id),
    config JSONB,
    status VARCHAR(20) DEFAULT 'active',
    installed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, plugin_id)
);
```

---

## 四、数据库迁移规范

### 4.1 迁移规则

```
1. 单头线性：Alembic保持单头，合并冲突取两侧超集
2. 可逆迁移：每个upgrade必须有对应的downgrade
3. 先测试：upgrade → downgrade → upgrade 循环验证
4. 不删列：用软删除，不物理删除列（除非V2+大版本）
5. 索引先行：新列如需查询，同时建索引
```

### 4.2 迁移文件命名

```
alembic/versions/
├── nc_v1_skills.sql          # Skill系统
├── nc_v1_agents.sql          # Agent系统
└── nc_v2_plugins.sql         # Plugin系统（V2）
```

---

## 五、ER关系简图

```
users ──┬── projects ──── novels ──── chapters ──── contents
        │       │
        │   project_members
        │
        ├── api_keys
        ├── subscriptions ──── plans
        │       │
        │   budgets
        │
        ├── skill_installations ──── skills
        │       │
        │   skill_executions
        │
        ├── agent_runs ──── agents ──── agent_skills
        │       │
        │   agent_run_steps
        │
        ├── plugin_installations ──── plugins
        │
        └── ai_calls
```

---

> **注意**：现有26+张表结构保持完全不变。V1新增表仅做加法。
