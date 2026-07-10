# SQL 建表规划

## 核心建表语句（关键表）

### contents — 统一内容模型
```sql
CREATE TABLE contents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    project_id UUID NOT NULL REFERENCES projects(id),
    parent_id UUID REFERENCES contents(id),
    type VARCHAR(50) NOT NULL,  -- novel/volume/chapter/short_story/wechat_article/...
    title VARCHAR(500) NOT NULL,
    body JSONB,                 -- Tiptap JSON
    meta JSONB,                 -- 类型专属字段
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    owner_id UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX contents_project_id_idx ON contents(project_id);
CREATE INDEX contents_parent_id_idx ON contents(parent_id);
CREATE INDEX contents_type_idx ON contents(type);
```

### versions — 通用版本系统
```sql
CREATE TABLE versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    entity_type VARCHAR(50) NOT NULL,  -- content/knowledge_item/prompt/workflow
    entity_id UUID NOT NULL,
    version_no INTEGER NOT NULL,
    parent_version_id UUID REFERENCES versions(id),
    snapshot JSONB NOT NULL,
    reason VARCHAR(50) NOT NULL,  -- manual/ai_rewrite/auto_save/restore
    author_id UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX versions_entity_idx ON versions(entity_type, entity_id);
```

### workflows — 工作流定义
```sql
CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    name VARCHAR(200) NOT NULL,
    is_preset BOOLEAN NOT NULL DEFAULT FALSE,
    definition JSONB NOT NULL,  -- 节点数组 DAG
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### workflow_runs — 运行实例
```sql
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    project_id UUID NOT NULL REFERENCES projects(id),
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    context JSONB,
    schedule_id UUID REFERENCES schedules(id),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### run_nodes — 节点执行记录
```sql
CREATE TABLE run_nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id),
    node_key VARCHAR(100) NOT NULL,
    agent VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    input JSONB,
    output JSONB,
    ai_call_ids UUID[] DEFAULT '{}',
    attempt INTEGER NOT NULL DEFAULT 1,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    UNIQUE(run_id, node_key)
);
```

### ai_calls — AI 调用全追踪
```sql
CREATE TABLE ai_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    run_node_id UUID REFERENCES run_nodes(id),
    agent VARCHAR(100),
    task_type VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_name VARCHAR(100),
    prompt_version INTEGER,
    input JSONB,
    output JSONB,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost NUMERIC(10,6),
    latency_ms INTEGER,
    status VARCHAR(30) NOT NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);  -- 按月分区
```

### knowledge_items — 知识库
```sql
CREATE TABLE knowledge_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    scope VARCHAR(20) NOT NULL DEFAULT 'project',  -- global/project
    project_id UUID REFERENCES projects(id),
    kind VARCHAR(50) NOT NULL,  -- character/worldview/hotspot/article/...
    title VARCHAR(500) NOT NULL,
    content TEXT,
    meta JSONB,
    source_url TEXT,
    file_ref VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### knowledge_vectors — 向量索引（pgvector）
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE knowledge_vectors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    item_id UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    chunk_no INTEGER NOT NULL,
    embedding vector(1536),
    chunk_text TEXT NOT NULL
);
CREATE INDEX knowledge_vectors_hnsw_idx ON knowledge_vectors
    USING hnsw (embedding vector_cosine_ops);
```
