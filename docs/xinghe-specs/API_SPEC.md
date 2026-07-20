# 星禾AI工作台 · API接口规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：后端架构师
>
> 基于 NovelCraft V2.2 现有API体系，扩展V1新增接口。

---

## 一、API设计原则

| 原则 | 说明 |
|------|------|
| **统一信封** | 所有响应格式 `{code, message, data}` |
| **版本化** | URL路径版本 `/api/v1/` |
| **向后兼容** | 新增路由，不修改/删除现有路由 |
| **分页标准** | `limit`(默认50) + `offset`(默认0) |
| **幂等性** | 写操作带 `Idempotency-Key` header |
| **流式优先** | AI调用默认SSE流式返回 |
| **错误码语义化** | 使用语义化错误码，非纯数字 |

---

## 二、通用规范

### 2.1 统一响应信封

```json
// 成功
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": { ... }
}

// 分页
{
  "code": "SUCCESS",
  "message": "操作成功",
  "data": {
    "items": [...],
    "total": 100,
    "limit": 50,
    "offset": 0
  }
}

// 错误
{
  "code": "PROVIDER_RATE_LIMITED",
  "message": "AI服务暂时繁忙，请稍后重试",
  "data": null,
  "trace_id": "abc-123"
}
```

### 2.2 错误码体系

| HTTP状态码 | 错误码 | 说明 |
|-----------|--------|------|
| 400 | `VALIDATION_ERROR` | 请求参数错误 |
| 401 | `UNAUTHORIZED` | 未认证 |
| 403 | `FORBIDDEN` | 无权限 |
| 404 | `NOT_FOUND` | 资源不存在 |
| 402 | `BUDGET_EXCEEDED` | AI额度不足 |
| 429 | `PROVIDER_RATE_LIMITED` | AI服务限流 |
| 429 | `RATE_LIMITED` | 请求频率限制 |
| 500 | `INTERNAL_ERROR` | 内部错误 |
| 502 | `PROVIDER_ERROR` | AI服务错误 |
| 503 | `DB_POOL_EXHAUSTED` | 数据库连接池耗尽 |

### 2.3 认证

```
所有API（除 /auth/login 和 /auth/register）：
Header: Authorization: Bearer <access_token>

BYOK（用户自带密钥）：
Header: X-Api-Key: <user_api_key>
（仅内存存储，不落库，关闭会话清除）
```

---

## 三、现有API（保持兼容）

### 3.1 认证 `/api/v1/auth/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/register` | 注册 |
| POST | `/auth/login` | 登录 |
| POST | `/auth/refresh` | 刷新Token |
| GET | `/auth/me` | 当前用户信息 |

### 3.2 项目 `/api/v1/projects/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/projects` | 项目列表 |
| POST | `/projects` | 创建项目 |
| GET | `/projects/{id}` | 项目详情 |
| PUT | `/projects/{id}` | 更新项目 |
| DELETE | `/projects/{id}` | 删除项目 |
| POST | `/projects/{id}/novels` | 创建小说 |

### 3.3 小说 `/api/v1/novels/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/novels/{id}` | 小说详情 |
| POST | `/novels/{id}/bootstrap` | 启动自动成书 |
| POST | `/novels/{id}/continue` | 继续生成 |

### 3.4 扫榜 `/api/v1/ranking/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ranking/sources` | 数据源列表 |
| POST | `/ranking/sources/{source}/scan` | 扫描榜单 |
| GET | `/ranking/snapshots` | 快照列表 |
| GET | `/ranking/snapshots/{id}` | 快照详情 |
| POST | `/ranking/snapshots/{id}/analyze` | 分析快照 |

### 3.5 书库 `/api/v1/library/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/library/books` | 书库列表 |
| GET | `/library/books/{id}` | 书籍详情 |
| DELETE | `/library/books/{id}` | 删除书籍 |

### 3.6 内容 `/api/v1/contents/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/contents/{id}` | 获取内容 |
| PUT | `/contents/{id}` | 更新内容 |
| POST | `/contents/{id}/ai/{op}` | AI操作（rewrite/expand/polish/deai） |
| POST | `/contents/{id}/ai/{op}/stream` | AI操作流式 |

### 3.7 工作流 `/api/v1/runs/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/runs/{id}` | 运行详情 |
| GET | `/runs/{id}/events` | SSE事件流 |
| POST | `/runs/{id}/nodes/{node_id}/confirm` | 人工确认 |

### 3.8 知识库 `/api/v1/knowledge/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge` | 知识列表 |
| POST | `/knowledge` | 添加知识 |
| GET | `/knowledge/search` | 搜索知识 |
| POST | `/knowledge/style-learn` | 风格学习 |
| POST | `/knowledge/check-similarity` | 相似度检查 |
| GET | `/knowledge/daily-briefing` | 每日晨报 |

### 3.9 热点 `/api/v1/hotspots/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/hotspots` | 热点列表 |
| GET | `/hotspots/history` | 历史热点 |

### 3.10 发布 `/api/v1/publish/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/publish/records` | 发布记录 |
| POST | `/publish` | 执行发布 |

### 3.11 管理 `/api/v1/admin/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/providers` | Provider列表 |
| PUT | `/admin/providers/{id}` | 更新Provider配置 |
| GET | `/admin/model-routes` | 模型路由 |
| GET | `/admin/budgets` | 预算列表 |
| GET | `/admin/prompts` | Prompt列表 |

---

## 四、V1新增API

### 4.1 AI Engine `/api/v1/engine/`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/engine/chat` | 通用AI对话（SSE流式） |
| POST | `/engine/complete` | 通用AI补全（SSE流式） |
| GET | `/engine/models` | 可用模型列表 |
| GET | `/engine/usage` | Token使用统计 |

#### POST `/engine/chat`

```json
// 请求
{
  "messages": [
    {"role": "user", "content": "帮我分析最近番茄小说榜单的趋势"}
  ],
  "model": "deepseek-chat",        // 可选，默认auto
  "temperature": 0.7,              // 可选
  "max_tokens": 2000,              // 可选
  "context": {                      // 可选，注入上下文
    "project_id": "xxx",
    "novel_id": "xxx"
  }
}

// 响应（SSE流式）
data: {"type": "delta", "content": "根据"}
data: {"type": "delta", "content": "最近"}
...
data: {"type": "done", "usage": {"input_tokens": 150, "output_tokens": 500}}
```

### 4.2 Skill中心 `/api/v1/skills/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/skills` | Skill列表（含安装状态） |
| GET | `/skills/{id}` | Skill详情 |
| POST | `/skills/{id}/install` | 安装Skill |
| POST | `/skills/{id}/execute` | 执行Skill |
| PUT | `/skills/{id}/toggle` | 启用/禁用 |
| DELETE | `/skills/{id}` | 卸载Skill |

#### POST `/skills/{id}/execute`

```json
// 请求
{
  "inputs": {
    "genre": "末世",
    "theme": "生存",
    "keywords": ["丧尸", "进化"]
  }
}

// 响应
{
  "code": "SUCCESS",
  "message": "Skill执行成功",
  "data": {
    "skill_id": "skill_novel_explosive_title",
    "output": {
      "titles": [
        {"title": "末世：我从丧尸堆里爬出来", "score": 8.5},
        {"title": "末日进化：我的基因与众不同", "score": 7.8}
      ]
    },
    "usage": {"tokens": 500, "cost_cny": 0.005}
  }
}
```

### 4.3 Agent中心 `/api/v1/agents/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/agents` | Agent列表 |
| POST | `/agents` | 创建Agent |
| GET | `/agents/{id}` | Agent详情 |
| PUT | `/agents/{id}` | 更新Agent配置 |
| POST | `/agents/{id}/run` | 运行Agent |
| GET | `/agents/{id}/runs` | Agent运行历史 |
| GET | `/agents/{id}/runs/{run_id}` | 运行详情 |
| GET | `/agents/{id}/runs/{run_id}/events` | 运行事件（SSE） |
| POST | `/agents/{id}/runs/{run_id}/confirm` | 人工确认 |

### 4.4 商业化 `/api/v1/billing/`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/billing/plans` | 套餐列表 |
| GET | `/billing/subscription` | 当前订阅 |
| POST | `/billing/subscribe` | 订阅套餐 |
| GET | `/billing/usage` | 用量统计 |
| GET | `/billing/invoices` | 账单列表 |

### 4.5 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/healthz` | 健康检查（含worker ping + queue_depth） |

---

## 五、SSE流式规范

### 5.1 连接

```
GET /api/v1/engine/chat
Headers:
  Authorization: Bearer <token>
  Accept: text/event-stream
  Last-Event-ID: <last_event_id>  // 断点续传
```

### 5.2 事件格式

```
data: {"type": "delta", "content": "文本片段"}

data: {"type": "error", "code": "PROVIDER_ERROR", "message": "..."}

data: {"type": "done", "usage": {"input_tokens": 100, "output_tokens": 200}}
```

### 5.3 重连机制

```
客户端维护 Last-Event-ID
断开后自动重连
重连时携带 Last-Event-ID 实现断点续传
最多重试3次，间隔指数退避
```

---

## 六、WebSocket规范（V2+）

### 连接

```
ws://host/api/v1/sync/ws?token=<jwt_token>
```

### 事件类型

| 事件 | 方向 | 说明 |
|------|------|------|
| `agent.run.progress` | Server→Client | Agent执行进度 |
| `agent.run.completed` | Server→Client | Agent执行完成 |
| `project.updated` | Server→Client | 项目信息更新 |
| `ping` | Bidirectional | 心跳 |

---

> **注意**：现有129条API路由保持完全不变。新增路由仅做加法。
