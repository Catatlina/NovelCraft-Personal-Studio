# NovelCraft Personal Studio — API 接口规范（V2.1 定案版）

> 本文档为后端 FastAPI（`api → service → repository`）的对外接口契约，是前端与第三方集成方的唯一事实参考。
> 与《架构评审报告 V2.1》《MVP 方案》《技术实施方案》保持一致：统一内容模型（C1）、工作流引擎（C2）、AI Gateway（C3）、Knowledge Hub（C4）、版本系统（C5）、叙事一致性引擎（C6）、发布网关（C7）、追踪治理（C8）。
> 所有端点前缀为 `/api/v1`（注：MVP 方案 §5 增量表中的 `/api/...` 为相对简写，全量版统一收敛到 `/api/v1`）。
>
> 文档版本：**V2.2**　基线范围：**全量 13 模块 + 扫榜/书库主轴**。

### V2.2 产品主轴新增资源

扫榜成书与统一书库为P0，API至少提供：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/ranking/library/books?project_id=` | 统一书库首批接口；完整筛选/分页待后续任务 |
| GET | `/api/v1/ranking/sources?project_id=` | 榜单来源和最近成功/失败状态 |
| POST | `/api/v1/ranking/sources/{source}/scan?project_id=` | 同步采集并持久化快照；来源失败返回 502 和失败快照 |
| GET | `/api/v1/ranking/snapshots?project_id=` | 项目榜单快照列表 |
| GET | `/api/v1/ranking/snapshots/{id}` | 榜单快照和条目 |
| POST | `/api/v1/ranking/snapshots/{id}/retry` | 仅重放失败快照；新快照记录 `retry_of_snapshot_id` |
| POST | `/api/v1/ranking/snapshots/{id}/analyze` | Gateway 结构化市场分析；严格校验后才写候选；Provider 失败返回 503 + `pending_provider`，不得生成固定候选 |
| GET | `/api/v1/ranking/topics?project_id=` | 原创选题池 |
| POST | `/api/v1/ranking/topics/{id}/generate-book` | 建书入库；已有题名时跳过人工选名，从 n3 启动生成 |
| POST | `/novels/from-inspiration` | 次要灵感入口，复用成书工作流并自动入库 |
| POST | `/hotspots/scan-and-generate` | 热点分析并生成多平台内容矩阵 |

所有创建小说的响应必须先返回持久化 `book_id`，生成失败不得删除书库记录；通过 `workflow_run_id`继续追踪。榜单源失败使用明确错误码，不得返回`200 + []`伪装成功。

---

## 目录

1. [通用约定](#1-通用约定)
2. [RBAC 权限矩阵](#2-rbac-权限矩阵)
3. [SSE 实时事件规范](#3-sse-实时事件规范)
4. [端点清单（按模块）](#4-端点清单按模块)
   - 4.1 [auth 认证](#41-auth-认证模块)
   - 4.2 [projects & project_members 项目与成员](#42-projects--project_members-项目与成员)
   - 4.3 [contents 统一内容](#43-contents-统一内容-c1)
   - 4.4 [novels 小说引导](#44-novels-小说引导)
   - 4.5 [versions 版本系统](#45-versions-版本系统-c5)
   - 4.6 [workflows & runs 工作流与运行](#46-workflows--runs-工作流与运行-c2)
   - 4.7 [knowledge Knowledge Hub](#47-knowledge-knowledge-hub-c4)
   - 4.8 [prompts 提示词实验室](#48-prompts-提示词实验室)
   - 4.9 [ai-calls AI 调用追踪](#49-ai-calls-ai-调用追踪-c8)
   - 4.10 [narrative 叙事一致性引擎](#410-narrative-叙事一致性引擎-c6)
   - 4.11 [publish 发布网关](#411-publish-发布网关-c7)
   - 4.12 [metrics 数据回流与 ROI](#412-metrics-数据回流与-roi)
   - 4.13 [admin 管理与运维](#413-admin-管理与运维)
5. [Webhook 回调与文件上传](#5-webhook-回调与文件上传)
6. [OpenAPI 生成说明](#6-openapi-生成说明)

---

## 1. 通用约定

### 1.1 Base Path 与版本

- 所有 REST 与 SSE 端点统一前缀：`/api/v1`。
- 版本号只在路径出现一次；破坏性变更走 `v2`，不向后兼容时另起前缀。
- 用户身份资源（如 `/me`）也属于 `/api/v1` 命名空间。

### 1.2 认证方式（Bearer JWT，access + refresh）

采用**短期 access token + 长期 refresh token** 双令牌模式，基于 FastAPI `HTTPBearer` 依赖注入，权限由 `require_role` 装饰器在 `api` 层强制校验。

| 令牌 | 存储 | 有效期 | 用途 |
|---|---|---|---|
| `access_token` | 内存 / 短期 | 30 分钟 | 所有业务接口 `Authorization: Bearer <access>` |
| `refresh_token` | httpOnly Cookie（SameSite=Lax） | 30 天（可轮转） | 仅用于 `/auth/refresh` 换取新 access |

**刷新流程**：

```
1. 客户端携带 access 调接口 → 401 + code=TOKEN_EXPIRED
2. 客户端用 refresh_token（Cookie 自动带）POST /api/v1/auth/refresh
3. 服务端校验 refresh 未过期且未进吊销表(Redis) → 返回新 access_token
4. 失败(refresh 过期/吊销) → 401 + code=REFRESH_INVALID → 强制重新登录
```

- access 过期不吊销 refresh；refresh 一次一用（旋转），旧 refresh 立即入吊销表。
- 登出（`/auth/logout`）将当前 refresh 入吊销表并清 Cookie。
- CSRF 防护：所有非 GET 且使用 Cookie 凭证的请求需 `X-CSRF-Token` 头（SameSite + token 双因子），纯 Bearer 接口不受影响。

### 1.3 统一响应包络（结论）

**结论：全系统统一使用 `{code, message, data}` 包络**，成功与错误都返回该结构，HTTP 状态码与 `code` 协同（2xx 时 `code=0`；4xx/5xx 时 `code` 为业务错误枚举，详见 §1.5）。

理由：前端用 `openapi-ts` 生成客户端后，单一解析分支即可处理成功/失败；SSE 之外无需区分裸资源体与错误体，降低客户端复杂度。列表接口的 `data` 为带分页元信息的对象（见 §1.4）。

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "cnt_8fa2",
    "title": "示例章节"
  }
}
```

错误示例：

```json
{
  "code": "CONTENT_NOT_FOUND",
  "message": "content not found: cnt_8fa2",
  "data": null
}
```

### 1.4 分页规范

列表类端点**同时支持两种分页**，由调用方选择：

- **偏移分页（默认）**：`?page=1&page_size=20`，返回 `{ items, page, page_size, total, total_pages }`，适用于后台管理、成员列表等低频翻页。
- **游标分页**：`?cursor=eyJ...&limit=50`，返回 `{ items, next_cursor, has_more }`，适用于 ai_calls、metrics、SSE 日志等高增量流，避免深翻页性能衰减。

`page_size` / `limit` 上限均为 `100`，超出按上限截断并返回 `code=LIMIT_EXCEEDED` 警告（仍返回数据）。排序统一用 `?sort=-created_at`（前导 `-` 表降序）。

分页响应包络：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 134,
    "total_pages": 7
  }
}
```

### 1.5 错误码表

HTTP 状态码为粗粒度分类，`code` 为业务细粒度枚举（字符串 SnakeUpper），`message` 为可展示人类文案（后端可国际化，默认中文）。

**协议级（HTTP 4xx/5xx）**：

| HTTP | code | 触发场景 |
|---|---|---|
| 400 | `BAD_REQUEST` | 参数校验失败、JSON 解析错误、meta Schema 校验错误 |
| 401 | `TOKEN_EXPIRED` / `TOKEN_MISSING` / `REFRESH_INVALID` | 未携带/过期/非法令牌 |
| 403 | `FORBIDDEN` / `ROLE_DENIED` | 已认证但角色无权（如 Viewer 调写接口） |
| 404 | `NOT_FOUND` / `CONTENT_NOT_FOUND` / `PROJECT_NOT_FOUND` / `RUN_NOT_FOUND` | 资源不存在 |
| 409 | `CONFLICT` / `VERSION_CONFLICT` | 乐观锁冲突（L2 离线编辑 base_version_id 不符） |
| 413 | `PAYLOAD_TOO_LARGE` | 上传文件超 `max_upload_size` |
| 422 | `VALIDATION_ERROR` | Pydantic 校验细节错误（detail 含字段级原因） |
| 429 | `RATE_LIMITED` | 限流触发（见 §1.6），含 `Retry-After` 头 |
| 500 | `INTERNAL_ERROR` | 未捕获异常 |
| 503 | `PROVIDER_DEGRADED` / `PENDING_BUDGET` | AI Provider 全降级 / 预算触顶熔断 |

**业务级（通用前缀 `BIZ_`）**：

| code | 说明 |
|---|---|
| `META_SCHEMA_INVALID` | content.meta 不符合该 type 的 Pydantic Schema 注册表 |
| `ROLE_DENIED` | RBAC 拦截（同上 403） |
| `BUDGET_EXCEEDED` | 任务/项目/日三级预算任一触顶 |
| `SIMILARITY_BLOCKED` | 仿写相似度 `sim≥0.75`，需强制重写（C4 生成闸） |
| `SIMILARITY_NEEDS_HUMAN` | `0.6≤sim<0.75` 高风险，需 human 节点确认 |
| `PUBLISH_SAFETY_REJECTED` | 内容安全过滤（敏感词/平台规则/未过相似度闸）拦截 |
| `AUTO_PUBLISH_DISABLED` | 国内平台全自动未开启却请求全自动 |
| `HUMAN_NODE_WAITING` | 节点处于 waiting_human，需先 confirm |
| `NODE_NOT_RETRYABLE` | 节点状态不允许 retry（如 running） |
| `RUN_NOT_RUNNABLE` | run 已终态（succeeded/failed/cancelled） |
| `WEBHOOK_SIGNATURE_INVALID` | Webhook 签名校验失败 |
| `IDEMPOTENCY_REPLAY` | 幂等键重复且仍在处理（见 §1.7） |
| `LIMIT_EXCEEDED` | 分页上限被截断（非错误，警告级） |

### 1.6 幂等键约定（Idempotency-Key）

用于 **AI 出站队列重放**（Offline First L3）及所有写操作的防重复：

- 客户端在**会触发异步 run / AI 调用的写请求**头中附带 `Idempotency-Key: <uuidv4>`。
- 服务端以 `(user_id, Idempotency-Key)` 为键在 Redis 记录 24h：
  - 首次 → 执行，记录返回结果指纹；
  - 重复且已完成 → 直接返回首次结果（`code=0`，不重复扣费）；
  - 重复且进行中 → 返回 `409 IDEMPOTENCY_REPLAY` 或等待后返回原结果。
- 适用端点：`POST /novels/{id}/bootstrap`、`POST /runs`、`POST /contents/{id}/ai/{op}`、`POST /publish/records`、`POST /knowledge/ingest/*`。
- 不带 Key 的此类请求仍执行，但不保证重放安全（建议客户端始终携带）。

### 1.7 限流响应

- 限流维度：按 `(user_id 或 IP, 端点组)` 令牌桶，AI 出站另受 Provider RPM 限制。
- 触发返回 `429 RATE_LIMITED`，并带标准头：
  - `Retry-After: 12`（秒）
  - `X-RateLimit-Limit: 60`
  - `X-RateLimit-Remaining: 0`
  - `X-RateLimit-Reset: 1710000000`
- 前端在 SSE/重放场景应指数退避（base 1s，cap 30s）。

### 1.8 时间格式与编码

- 所有时间字段：`ISO8601 UTC`，形如 `2026-07-10T09:29:25Z`（后缀 `Z` 表示 UTC，禁止本地时区偏移）。
- 请求体：`application/json; charset=utf-8`，中文直引号字段名（`"key"`）。
- 文件上传：`multipart/form-data`（见 §5.2）。
- 二进制/向量不进 JSON；embedding 仅在 knowledge 检索内部使用，API 不暴露原始向量。

---

## 2. RBAC 权限矩阵

三类角色（`owner` / `editor` / `viewer`），由 `project_members.role` 决定。Owner 全权；Editor 可读写内容与跑工作流，不可删项目/管成员/改预算/改发布全自动开关；Viewer 只读。

> 符号：`✓` 允许　`✗` 拒绝　`◐` 受限（仅本人创建/仅读自己）

| 端点族 | owner | editor | viewer |
|---|---|---|---|
| auth（自身） | ✓ | ✓ | ✓（仅 `/me`） |
| projects 读 | ✓ | ✓ | ✓ |
| projects 写/删 | ✓ | ✗ | ✗ |
| project_members 管理 | ✓ | ✗ | ✗ |
| contents 读 | ✓ | ✓ | ✓ |
| contents 写/AI 操作 | ✓ | ✓ | ✗ |
| novels/bootstrap | ✓ | ✓ | ✗ |
| versions 读/恢复 | ✓ | ✓ | ✓（读）/✗（恢复） |
| workflows 读 | ✓ | ✓ | ✓ |
| workflows 写/删 | ✓ | ✗（仅 owner 改定义） | ✗ |
| runs 启动/控制(confirm/retry/pause/resume/cancel) | ✓ | ✓ | ✗ |
| knowledge 读 | ✓ | ✓ | ✓ |
| knowledge 写（入库/学习） | ✓ | ✓ | ✗ |
| prompts 读 | ✓ | ✓ | ✓ |
| prompts 写/实验室批跑 | ✓ | ✓ | ✗ |
| ai-calls 读 | ✓ | ✓ | ✓（仅本项目） |
| narrative 读 | ✓ | ✓ | ✓ |
| narrative 写（维护实体/伏笔） | ✓ | ✓ | ✗ |
| publish 账号/记录读 | ✓ | ✓ | ✓ |
| publish 全自动开关 | ✓ | ✗ | ✗ |
| publish 发布动作 | ✓ | ✓（半自动/手动） | ✗ |
| metrics 读 | ✓ | ✓ | ✓ |
| metrics 录入 | ✓ | ✓ | ✗ |
| admin（预算/模型路由/敏感词/备份） | ✓ | ✗ | ✗ |
| audit_logs 读 | ✓ | ✗ | ✗ |

**校验实现**：`api` 层依赖 `get_current_user` + `require_role(project_id, min_role)`，越权统一返回 `403 ROLE_DENIED`，并写 `audit_logs`。所有写操作落审计（谁/何时/对什么/做了什么）。

---

## 3. SSE 实时事件规范

工作流运行进度与通知通过 **Server-Sent Events** 推送，单条 run 一个流。

- 端点：`GET /api/v1/runs/{run_id}/events`
- 认证：Bearer access（SSE 不支持 Cookie 自动带，必须显式 `Authorization`）。
- `Content-Type: text/event-stream`，`Cache-Control: no-cache`，`Connection: keep-alive`。
- 支持断线续传：客户端在重连时带 `Last-Event-ID: <id>` 头，服务端从对应事件序号补发。

**事件类型**（每行为一个 `event:` + `data:` 帧）：

| event | 含义 | data 关键字段 |
|---|---|---|
| `node_started` | 节点开始执行 | `node_key, agent, started_at` |
| `node_progress` | 节点中间进度（如生成 token 流/百分比） | `node_key, progress(0-1), partial?` |
| `node_waiting_human` | 节点挂起待人工确认 | `node_key, gate_type, prompt, options?` |
| `node_succeeded` | 节点成功 | `node_key, output_ref, ai_call_ids[], cost` |
| `node_failed` | 节点失败（未达重试上限或终态） | `node_key, error, attempt` |
| `run_done` | 整个 run 进入终态 | `run_id, status(succeeded/failed/cancelled), summary` |

**心跳**：服务端每 `15s` 发送一帧 `: heartbeat\n\n`（注释行，客户端忽略但保活）。

**示例帧**：

```
event: node_started
id: 1024
data: {"run_id":"run_77","node_key":"n7","agent":"Writer","started_at":"2026-07-10T09:30:01Z"}

event: node_progress
id: 1025
data: {"run_id":"run_77","node_key":"n7","progress":0.42}

event: node_waiting_human
id: 1030
data: {"run_id":"run_77","node_key":"n2","gate_type":"select_title","prompt":"请选定书名","options":["《星轨》","《残响》","《长夜书》"]}

event: run_done
id: 1100
data: {"run_id":"run_77","status":"succeeded","summary":"8/8 节点完成，成本 ¥1.32"}
```

**客户端约定**：收到 `node_waiting_human` 弹出确认卡 → 调 `POST /runs/{id}/nodes/{key}/confirm`；断线后重连用 `Last-Event-ID` 避免重复渲染；流关闭即 run 终态。

---

## 4. 端点清单（按模块）

> 字段约定：每个端点给出 **方法 / 路径 / 权限 / 请求 / 响应示例 / 错误**。
> `权限` 列写最低所需角色（owner/editor/viewer）。`Body` 为 JSON 字段表：`字段名: 类型 [必填?]`。
> 公共错误（401/403/429/500）在各端点省略，仅在特有错误出现时列出。

---

### 4.1 auth 认证模块

#### 4.1.1 注册
`POST /api/v1/auth/register`　权限：公开

Body：
- `email: string [必填]`　邮箱
- `password: string [必填]`　密码（≥8 位）
- `display_name: string [选填]`　昵称

响应：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user_id": "usr_12",
    "email": "a@b.com",
    "access_token": "eyJ...",
    "refresh_token_set": true
  }
}
```
错误：`EMAIL_TAKEN`(409)、`BAD_REQUEST`(400)。

#### 4.1.2 登录
`POST /api/v1/auth/login`　权限：公开

Body：`email: string [必填]`、`password: string [必填]`

响应：同 register（返回 token）。
错误：`CREDENTIAL_INVALID`(401)。

#### 4.1.3 刷新 access
`POST /api/v1/auth/refresh`　权限：refresh cookie

响应：
```json
{ "code": 0, "message": "ok", "data": { "access_token": "eyJ..." } }
```
错误：`REFRESH_INVALID`(401)。

#### 4.1.4 登出
`POST /api/v1/auth/logout`　权限：已认证

响应：`{ "code": 0, "message": "ok", "data": null }`

#### 4.1.5 当前用户
`GET /api/v1/auth/me`　权限：已认证

响应：
```json
{ "code": 0, "message": "ok", "data": { "user_id":"usr_12", "email":"a@b.com", "display_name":"作家甲" } }
```

---

### 4.2 projects & project_members 项目与成员

#### 4.2.1 创建项目
`POST /api/v1/projects`　权限：已认证（自动成为 owner）

Body：`name: string [必填]`、`description: string [选填]`

响应：
```json
{ "code":0, "message":"ok", "data": { "id":"prj_3", "name":"我的小说集", "owner_id":"usr_12", "created_at":"2026-07-10T09:29:25Z" } }
```

#### 4.2.2 项目列表
`GET /api/v1/projects`　权限：已认证（仅返回自己参与的）

Query：`page,page_size / cursor,limit`、`sort`

响应：`data.items[]` 为项目摘要。

#### 4.2.3 获取项目
`GET /api/v1/projects/{project_id}`　权限：成员

#### 4.2.4 更新项目
`PUT /api/v1/projects/{project_id}`　权限：owner

Body：`name?`、`description?`

#### 4.2.5 删除项目
`DELETE /api/v1/projects/{project_id}`　权限：owner

响应：`{code:0,...}`。错误：`PROJECT_NOT_FOUND`(404)。

#### 4.2.6 成员列表
`GET /api/v1/projects/{project_id}/members`　权限：成员

响应 `data.items[]`：`{user_id,email,display_name,role}`

#### 4.2.7 添加成员
`POST /api/v1/projects/{project_id}/members`　权限：owner

Body：`email: string [必填]`、`role: enum[editor,viewer] [必填]`

响应：`{user_id,role}`。错误：`USER_NOT_FOUND`(404)、`ROLE_INVALID`(400)。

#### 4.2.8 更新成员角色
`PUT /api/v1/projects/{project_id}/members/{user_id}`　权限：owner

Body：`role: enum[editor,viewer] [必填]`。错误：`CANNOT_DOWNGRADE_OWNER`(409)。

#### 4.2.9 移除成员
`DELETE /api/v1/projects/{project_id}/members/{user_id}`　权限：owner

错误：`CANNOT_REMOVE_OWNER`(409)。

---

### 4.3 contents 统一内容（C1）

统一内容模型：一切皆 content，`type` 枚举含 `novel/volume/chapter/short_story/flash_fiction/wechat_article/toutiao/xhs_note/zhihu_answer/video_script` 等；`body` 为 Tiptap JSON；`meta` 为类型专属 JSONB（需经 Schema 注册表校验）。

#### 4.3.1 创建内容
`POST /api/v1/contents`　权限：editor

Body：`project_id: string [必填]`、`type: enum [必填]`、`parent_id: string [选填]`（书籍结构树）、`title: string [必填]`、`body: object [选填]`（Tiptap JSON）、`meta: object [选填]`

响应：`{id,type,parent_id,title,status,created_at}`。错误：`META_SCHEMA_INVALID`(400)、`PARENT_NOT_FOUND`(404)。

#### 4.3.2 内容树查询
`GET /api/v1/contents/tree`　权限：成员

Query：`project_id [必填]`、`root_id?`（默认项目根）、`depth?`（默认 3）

响应：
```json
{ "code":0, "message":"ok", "data": {
  "id":"prj_3","type":"root","children":[
    {"id":"nov_1","type":"novel","title":"星轨","children":[
      {"id":"vol_1","type":"volume","title":"第一卷","children":[
        {"id":"ch_1","type":"chapter","title":"第一章","meta":{"seq":1}}
      ]}
    ]}
  ]
}}
```

#### 4.3.3 内容列表（按 type 过滤）
`GET /api/v1/contents`　权限：成员

Query：`project_id [必填]`、`type?`（如 `chapter`）、`parent_id?`、`status?`、`page,page_size`、`sort`

响应：`data.items[]` 为内容摘要列表。

#### 4.3.4 获取单条内容
`GET /api/v1/contents/{content_id}`　权限：成员

响应：`{id,project_id,parent_id,type,title,body,meta,status,owner_id,created_at,updated_at}`

#### 4.3.5 更新内容（自动版本快照）
`PUT /api/v1/contents/{content_id}`　权限：editor

Body：`title?`、`body?`（Tiptap JSON）、`meta?`、`label?`、`base_updated_at?`、`client_mutation_id?`

在线保存不传同步字段；离线重放必须传服务端最后一次 `updated_at` 作为 `base_updated_at`，并传 UUID 型 `client_mutation_id`。命中相同 mutation 时直接返回第一次结果。

响应：更新后内容；离线同步额外返回 `sync_status=applied|conflict`。发生冲突时不静默覆盖服务器正文，而是将本地稿写入 `versions` 分支并返回 `conflict_version_id`，供三方对比 UI 处理。

#### 4.3.6 删除内容
`DELETE /api/v1/contents/{content_id}`　权限：editor

错误：`CONTENT_NOT_FOUND`(404)。

#### 4.3.7 AI 操作（润色/改写/续写/扩写/缩写/去AI味）
`POST /api/v1/contents/{content_id}/ai/{op}`　权限：editor

`op ∈ {polish(润色), rewrite(改写), continue(续写), expand(扩写), compress(缩写), humanize(去AI味)}`

Body：`selection: string`、`instruction: string [选填]`、`client_mutation_id: string [离线重放必填]`。相同 mutation 已成功时直接返回 `ai_calls.output`，不会再次调用模型或扣费。

响应：
```json
{ "code":0, "message":"ok", "data": {
  "content_id":"ch_1",
  "op":"polish",
  "result_body": {"type":"doc","content":[...]},
  "ai_call_id":"ac_901",
  "cost":0.012,
  "similarity": null
}}
```
错误：`OP_INVALID`(400)、`BUDGET_EXCEEDED`(503)、`SIMILARITY_BLOCKED`(业务，仿写类 op)、`HUMAN_NODE_WAITING`（需确认时）。

> 所有 AI 操作统一走 C3 Gateway，落 `ai_calls` 计费与追踪；`humanize`(去AI味) 为 Editor Agent 操作集之一。

#### 4.3.8 内容元数据 Schema 校验预览
`POST /api/v1/contents/validate-meta`　权限：editor

Body：`type: enum [必填]`、`meta: object [必填]`

响应：`{valid:true}` 或 `{valid:false, errors:[{field,message}]}`。错误：`META_SCHEMA_INVALID` 详情在此返回。

---

### 4.4 novels 小说引导

#### 4.4.1 创建小说（content type=novel）
`POST /api/v1/projects/{project_id}/novels`　权限：editor

Body：`title: string [必填]`、`inspiration: string [必填]`（一句话~一段灵感）、`genre: string [选填]`（题材）、`style: string [选填]`（风格）、`target_words: int [选填]`（目标字数）

响应：`{id:"nov_1",type:"novel",title:"星轨",status:"draft"}`

#### 4.4.2 启动 bootstrap 六件套工作流
`POST /api/v1/novels/{novel_id}/bootstrap`　权限：editor

> 第一条预设工作流（C2 引擎 v0 线性 chain + human 节点）：书名(3候选)→简介卖点→世界观→人物(3~6)→总纲→第一章→7维审核。

Body：`Idempotency-Key: header [建议]`、`options?`（覆盖默认节点参数）

响应：
```json
{ "code":0, "message":"ok", "data": {
  "run_id":"run_77",
  "workflow_id":"wf_bootstrap",
  "status":"running",
  "nodes":["n1_gen_titles","n2_select_title","n3_gen_synopsis","n4_gen_worldview","n5_gen_characters","n6_gen_outline","n7_gen_chapter1","n8_review_7dim"],
  "events_url":"/api/v1/runs/run_77/events"
}}
```
错误：`NOVEL_NOT_FOUND`(404)、`IDEMPOTENCY_REPLAY`(409)。

---

### 4.5 versions 版本系统（C5）

#### 4.5.1 版本列表
`GET /api/v1/contents/{content_id}/versions`　权限：成员（viewer 可读）

Query：`page,page_size`、`reason?`（manual/ai_rewrite/auto_save/restore）

响应 `data.items[]`：`{version_no,parent_version_id,reason,author_id,created_at}`

#### 4.5.2 版本对比 diff
`GET /api/v1/contents/{content_id}/versions/{v1}/diff/{v2}`　权限：成员

响应：
```json
{ "code":0, "message":"ok", "data": {
  "base_version":5, "target_version":6,
  "diff":"@@ -12,3 +12,4 @@\n 旧句\n-废稿\n+新稿润色后",
  "diff_type":"text"
}}
```
> 正文类用 diff-match-patch 文本 diff；结构化实体用字段级 diff（`diff_type:"fields"`）。

#### 4.5.3 恢复版本
`POST /api/v1/contents/{content_id}/versions/{version_no}/restore`　权限：editor（viewer ✗）

Body：`create_branch: bool [选填]`（默认 false，生成恢复版本而非覆盖）

响应：`{restored_version_no, content_id}`。错误：`VERSION_NOT_FOUND`(404)。

---

### 4.6 workflows & runs 工作流与运行（C2）

#### 4.6.1 工作流列表
`GET /api/v1/workflows`　权限：成员

Query：`project_id?`、`is_preset?`（true/false）、`page,page_size`

响应 `data.items[]`：`{id,name,is_preset,node_count,updated_at}`

#### 4.6.2 获取工作流定义
`GET /api/v1/workflows/{workflow_id}`　权限：成员

响应：`{id,name,is_preset,definition:{nodes:[...],edges:[...]}}`

#### 4.6.3 创建工作流（自定义）
`POST /api/v1/workflows`　权限：owner（仅 owner 改定义）

Body：`name: string [必填]`、`definition: object [必填]`（节点数组 DAG，节点类型 ∈ {agent,human,tool,branch}）

响应：`{id,name,is_preset:false}`。错误：`DEFINITION_INVALID`(400)。

#### 4.6.4 更新/删除工作流
`PUT /api/v1/workflows/{workflow_id}`（owner）/`DELETE /api/v1/workflows/{workflow_id}`（owner，仅自定义可删，预设 reject `PRESET_READONLY`(409)）

#### 4.6.5 启动 run
`POST /api/v1/workflows/{workflow_id}/runs`　权限：editor

Body：`project_id: string [必填]`、`context: object [选填]`、`schedule_id?`、`Idempotency-Key: header [建议]`

响应：`{run_id,status:"running",events_url:"/api/v1/runs/{run_id}/events"}`

#### 4.6.6 获取 run 状态
`GET /api/v1/runs/{run_id}`　权限：成员

响应：
```json
{ "code":0, "message":"ok", "data": {
  "run_id":"run_77","workflow_id":"wf_bootstrap","status":"running",
  "nodes":[
    {"node_key":"n1","status":"succeeded","attempt":1},
    {"node_key":"n2","status":"waiting_human","attempt":0}
  ],
  "context":{},"created_at":"2026-07-10T09:30:00Z"
}}
```

#### 4.6.7 SSE 进度
`GET /api/v1/runs/{run_id}/events`　权限：成员（Bearer 必带）— 见 §3。

#### 4.6.8 human 节点确认
`POST /api/v1/runs/{run_id}/nodes/{node_key}/confirm`　权限：editor

Body：`decision: object [必填]`（如 `{"selected_title":"《星轨》"}` 或 `{"approve":true}`）

响应：`{node_key,status:"succeeded",run_status:"running"}`。错误：`HUMAN_NODE_WAITING`(若已确认)、`NODE_NOT_FOUND`(404)。

#### 4.6.9 单节点重试
`POST /api/v1/runs/{run_id}/nodes/{node_key}/retry`　权限：editor

Body：`force: bool [选填]`（默认 false，仅 failed 可重试）

响应：`{node_key,status:"running"}`。错误：`NODE_NOT_RETRYABLE`(409)。

#### 4.6.10 暂停 run
`POST /api/v1/runs/{run_id}/pause`　权限：editor

响应：`{run_id,status:"paused"}`。错误：`RUN_NOT_RUNNABLE`(409)。

#### 4.6.11 恢复 run
`POST /api/v1/runs/{run_id}/resume`　权限：editor

响应：`{run_id,status:"running"}`，断点续跑（节点级幂等，succeeded 跳过）。

#### 4.6.12 取消 run
`POST /api/v1/runs/{run_id}/cancel`　权限：editor

响应：`{run_id,status:"cancelled"}`。

#### 4.6.13 run 列表
`GET /api/v1/runs`　权限：成员

Query：`project_id?`、`workflow_id?`、`status?`、`page,page_size`

---

### 4.7 knowledge Knowledge Hub（C4）

`kind` 枚举：`character/worldview/setting/hotspot/article/golden_line/title/platform_rule/brand_style/style_card/prompt_ref/webpage/file`。

#### 4.7.1 手动入库
`POST /api/v1/knowledge/items`　权限：editor

Body：`project_id?`（缺省 global）、`scope: enum[global,project] [必填]`、`kind: enum [必填]`、`title: string [必填]`、`content: string [必填]`、`source_type: enum[original,licensed,public_domain,third_party] [必填]`（入库闸授权标注）、`meta?`

响应：`{id,kind,version_head}`。错误：`SOURCE_TYPE_REQUIRED`(400)。

#### 4.7.2 网页入库
`POST /api/v1/knowledge/ingest/web`　权限：editor

Body：`url: string [必填]`、`kind?`、`scope?`、`Idempotency-Key: header`

响应：`{job_id,status:"queued"}`（Celery 抓取解析，进度走 job SSE 或轮询）。

#### 4.7.3 文件上传解析入库
`POST /api/v1/knowledge/ingest/file`　权限：editor（multipart，见 §5.2）

Form：`file: binary [必填]`、`kind?`、`scope?`、`source_type?`

响应：`{job_id,status:"queued"}`（支持 PDF/Word/Markdown 解析切片）。

#### 4.7.4 检索 kb.search
`POST /api/v1/knowledge/search`　权限：成员

Body：`query: string [必填]`、`scope?`、`kinds: array [选填]`、`k: int [选填,默认8]`、`project_id?`

响应：
```json
{ "code":0, "message":"ok", "data": {
  "results":[
    {"item_id":"ki_5","kind":"character","title":"林晚","score":0.91,"chunk_text":"..."}
  ]
}}
```

#### 4.7.5 四库管理（列表/获取/更新/删除）
- `GET /api/v1/knowledge/items`　成员　Query：`scope?,kind?,project_id?,page,page_size`
- `GET /api/v1/knowledge/items/{item_id}`　成员
- `PUT /api/v1/knowledge/items/{item_id}`　editor（更新触发新 version_head）
- `DELETE /api/v1/knowledge/items/{item_id}`　editor

#### 4.7.6 风格学习 / 拆书分析
`POST /api/v1/knowledge/style-learn`　权限：editor

Body：`sample_item_ids: array [必填]`（样本集）、`name: string [必填]`（style_card 名）

响应：`{style_card_id,status:"queued"}`。错误：`INSUFFICIENT_SAMPLES`(400)。

`POST /api/v1/knowledge/book-analyze`　权限：editor

Body：`source_content_id: string [必填]`（小说原文）、`aspects: array [选填]`（开篇结构/爽点/节奏/标签）

响应：`{analysis_card_id,status:"queued"}`（产物写 style/analysis 卡）。

#### 4.7.7 相似度检测结果
`GET /api/v1/knowledge/similarity`　权限：成员

Query：`content_id [必填]` 或 `text [必填]`

响应：
```json
{ "code":0, "message":"ok", "data": {
  "sim":0.68,
  "method":"max(cosine,5gram)",
  "verdict":"needs_human",
  "passed":false
}}
```
> 阈值：`sim≥0.75`→`blocked`（强制重写）；`0.6≤sim<0.75`→`needs_human`；`<0.6`→`passed`。检测记录落 `ai_calls.meta`。

---

### 4.8 prompts 提示词实验室

`prompts` 表键：`name+version+model`。

#### 4.8.1 提示词列表/详情
`GET /api/v1/prompts`　成员　Query：`name?,model?,page,page_size`
`GET /api/v1/prompts/{prompt_id}`　成员

#### 4.8.2 创建新版本
`POST /api/v1/prompts`　权限：editor

Body：`name: string [必填]`、`model: string [必填]`、`template: string [必填]`（Jinja2）、`output_schema?`、`changelog?`

响应：`{id,version,created_at}`。

#### 4.8.3 版本对比
`GET /api/v1/prompts/{pid1}/diff/{pid2}`　成员（字段级 diff）

#### 4.8.4 golden case 管理
`GET/POST /api/v1/prompts/{prompt_id}/golden-cases`　editor（POST 新增固定 input+期望断言）

#### 4.8.5 实验室批跑
`POST /api/v1/prompts/lab/run`　权限：editor

Body：`input_ref: string [必填]`、`prompt_versions: array [必填]`、`models: array [选填]`

响应：`{lab_run_id,status:"queued"}`（同 input × {prompt/model} 矩阵写 `ai_calls`）。

#### 4.8.6 A/B 分流配置
`POST /api/v1/prompts/ab`　权限：editor

Body：`route_key: string [必填]`、`variants: array[{prompt_id,weight}] [必填]`

响应：`{ab_id}`（router 按权重分流，效果看 ai_calls 聚合）。

---

### 4.9 ai-calls AI 调用追踪（C8）

> 单一事实源 `ai_calls`：支撑输入输出记录、成本、模型质量对比、A/B、Prompt 实验室回放。

#### 4.9.1 追踪查询
`GET /api/v1/ai-calls`　权限：成员（仅本项目）

Query：`run_id?`、`run_node_id?`、`agent?`、`task_type?`、`provider?`、`model?`、`status?`、`cursor,limit`（推荐游标）、`sort:-created_at`

响应：
```json
{ "code":0, "message":"ok", "data": {
  "items":[
    {"id":"ac_901","agent":"Writer","task_type":"gen_chapter","provider":"deepseek","model":"deepseek-chat",
     "prompt_tokens":1200,"completion_tokens":3400,"cost":0.052,"latency_ms":8200,"status":"success",
     "created_at":"2026-07-10T09:31:00Z"}
  ],
  "next_cursor":"eyJ...","has_more":true
}}
```

#### 4.9.2 单条调用明细
`GET /api/v1/ai-calls/{ai_call_id}`　成员

响应含 `input`/`output` JSONB 全文（含 7 层上下文装配结果与丢弃日志，供回放定位）。

#### 4.9.3 成本聚合
`GET /api/v1/ai-calls/aggregate`　成员

Query：`project_id?,granularity: enum[run,project,daily,model] [必填]`、`range?`

响应：`{total_cost,by_model:{...},by_task_type:{...},call_count}`。

---

### 4.10 narrative 叙事一致性引擎（C6）

在 Content/Knowledge 之上叠加小说专属结构。

#### 4.10.1 实体状态看板
`GET /api/v1/narrative/{novel_id}/entities`　成员

响应：`data.items[]`：`{entity,type,location,relations[],holdings[],known_info[],updated_chapter}`。

#### 4.10.2 维护实体状态
`PUT /api/v1/narrative/{novel_id}/entities/{entity}`　editor

Body：`location?`、`relations?`、`holdings?`、`known_info?`

#### 4.10.3 伏笔看板
`GET /api/v1/narrative/{novel_id}/foreshadows`　成员

响应 `data.items[]`：`{id,planted_chapter,content,planned_recover_chapter,status: enum[open,recovered,expired]}`。

#### 4.10.4 创建/更新伏笔
`POST /api/v1/narrative/{novel_id}/foreshadows`　editor（Body：`content,planned_recover_chapter`）
`PUT /api/v1/narrative/{novel_id}/foreshadows/{id}`　editor（含 `status` 回收）

#### 4.10.5 时间线
`GET /api/v1/narrative/{novel_id}/timeline`　成员（Query：`chapter?`）
`POST /api/v1/narrative/{novel_id}/timeline`　editor（Body：`chapter,event,at_time`）

> timeline_events 抽取章内事件入表，支撑跨章矛盾检测。

#### 4.10.6 人物弧线
`GET /api/v1/narrative/{novel_id}/arcs`　成员
`PUT /api/v1/narrative/{novel_id}/arcs/{arc_id}`　editor（Body：`stage_goal,progress`）

#### 4.10.7 巡检报告
`POST /api/v1/narrative/{novel_id}/inspect`　editor

Body：`scope: enum[chapter,volume,book] [必填]`、`target_id?`

响应：`{report_id,status:"queued"}`（每 10 章巡检 / 卷级复盘，输出 OOC/设定冲突/前文一致性/节奏 检测族 + 7 维质量分）。

#### 4.10.8 7 维审核结果获取
`GET /api/v1/narrative/{novel_id}/reviews/{chapter_id}`　成员

响应：`{scores:{plot,pace,character,style,consistency,emotion,hook},issues:[...],radar:[...]}`（Reviewer Agent 输出，生成与审核异构 provider）。

---

### 4.11 publish 发布网关（C7）

适配器模式 `PublisherAdapter`：format/publish/fetch_metrics，每平台一个 adapter。发布前强制过内容安全过滤（敏感词+平台规则+仿写相似度标记）。

#### 4.11.1 平台账号列表/绑定
`GET /api/v1/publish/accounts`　成员
`POST /api/v1/publish/accounts`　editor

Body：`platform: enum[wechat,toutiao,xhs,zhihu,baijia,dayu,wangyi,medium,substack,x,royalroad,kdp] [必填]`、`credential: object [必填]`（Fernet 加密存储）

响应：`{id,platform,status:"linked"}`。

#### 4.11.2 发布全自动开关（强约束）
`PUT /api/v1/publish/auto-publish-config`　权限：owner（editor ✗）

Body：`platform: enum [必填]`、`enabled: bool [必填]`、`ack_risk: bool [必填]`（"已知悉平台条款与封号风险"二次确认）

响应：`{platform,enabled,audit_logged:true}`。错误：`AUTO_PUBLISH_DISABLED`（未 ack 或国内平台未显式开启却全自动）。

> 国内平台全自动默认关闭；开启后首篇仍强制 human 确认节点；连续失败自动降级半自动并告警。

#### 4.11.3 发布（三模式）
`POST /api/v1/publish/records`　权限：editor

Body：`content_id: string [必填]`、`platform: enum [必填]`、`mode: enum[manual,semi,auto] [必填]`、`account_id?`、`Idempotency-Key: header`

- `manual`：返回排版后内容 + 一键复制文本，无自动化风险；
- `semi`（默认）：Playwright 填充，**停在待人工点击态**（返回 `status:"awaiting_human_click"`）；
- `auto`：仅官方 API 平台（medium/substack/x/wordpress），系统直调；国内平台未开启则 `AUTO_PUBLISH_DISABLED`。

响应：
```json
{ "code":0, "message":"ok", "data": {
  "record_id":"pr_55","platform":"zhihu","mode":"semi",
  "status":"awaiting_human_click","preview_url":null
}}
```
错误：`PUBLISH_SAFETY_REJECTED`(业务，内容安全拦截)、`SIMILARITY_BLOCKED`(仿写未过闸)、`AUTO_PUBLISH_DISABLED`。

#### 4.11.4 发布记录列表/详情
`GET /api/v1/publish/records`　成员（Query：`content_id?,platform?,status?,page,page_size`）
`GET /api/v1/publish/records/{record_id}`　成员

`status ∈ {draft,queued,awaiting_human_click,published,failed,degraded}`。

#### 4.11.5 内容安全过滤预检
`POST /api/v1/publish/safety-check`　editor

Body：`content_id: string [必填]`、`platform: enum [必填]`

响应：`{passed:bool, hits:[{type:"sensitive_word"|"platform_rule"|"similarity",detail}]}`。

> 与 §5.1 仿写产物闸同一拦截点；未过相似度闸的仿写产物在此被拒。

#### 4.11.6 国内全自动风险确认（首篇）
`POST /api/v1/publish/records/{record_id}/confirm-auto`　editor

Body：`confirm: bool [必填]`

响应：`{status:"published"|"rejected"}`（每平台首篇强制人工确认，之后可按平台记忆选择）。

---

### 4.12 metrics 数据回流与 ROI

回流分级：API 平台自动拉取 → 无 API 半自动（粘贴/OCR）→ 手动录入兜底。

#### 4.12.1 数据回流录入
`POST /api/v1/metrics/ingest`　权限：editor

Body：`content_id: string [必填]`、`platform: enum [必填]`、`date: string(YYYY-MM-DD) [必填]`、`metrics: object [必填]`（views/likes/comments/shares/reads/favs 等）、`source: enum[api,semi,manual] [必填]`

响应：`{id,content_id,platform,date}`。错误：`METRIC_INVALID`(400)。

#### 4.12.2 Webhook 自动回流
`POST /api/v1/metrics/webhook/{platform}`　权限：公开（签名校验，见 §5.1）

#### 4.12.3 表现分析
`GET /api/v1/metrics/analyze`　成员

Query：`content_id?,platform?,range?`、`group_by: enum[platform,date,content]`

响应：`{series:[{date,platform,views,...}],top_contents:[...]}`。

#### 4.12.4 ROI 面板
`GET /api/v1/metrics/roi`　成员

Query：`project_id?,range?`

响应：`{total_cost,total_revenue_est,roi,by_platform:{cost,revenue,roi},by_content:[...]}`（成本来自 ai_calls 聚合，收益来自 metrics）。

---

### 4.13 admin 管理与运维

仅 owner 可访问（RBAC 矩阵 admin 行）。

#### 4.13.1 model_routes 配置
`GET /api/v1/admin/model-routes`　owner
`PUT /api/v1/admin/model-routes`　owner

Body：`task_type: string [必填]`、`primary: {provider,model,params} [必填]`、`fallbacks: array [选填]`

响应：`{task_type,updated_at}`（Redis 热更新，降级链：主→备→PENDING_PROVIDER）。

#### 4.13.2 预算配置
`GET/PUT /api/v1/admin/budgets`　owner

Body：`scope: enum[task,project,daily] [必填]`、`limit: number [必填]`（CNY）

响应：`{scope,limit,used,currency:"CNY"}`。

#### 4.13.3 敏感词表
`GET /api/v1/admin/sensitive-words`　owner（Query：`page,page_size`）
`POST /api/v1/admin/sensitive-words`　owner（Body：`word,level,category`）
`DELETE /api/v1/admin/sensitive-words/{id}`　owner

#### 4.13.4 备份状态
`GET /api/v1/admin/backup/status`　owner

响应：`{last_backup_at,location,retention_days:30,last_restore_drill:"2026-06-01"}`（每日 02:00 pg_dump|age 加密→异地，RPO≤24h/RTO≤1h）。

#### 4.13.5 审计日志
`GET /api/v1/admin/audit-logs`　owner

Query：`actor_id?,action?,entity_type?,range?,cursor,limit`

响应：`{items:[{who,when,action,entity_type,entity_id,detail}],next_cursor}`。

#### 4.13.6 健康检查
`GET /api/v1/healthz`　权限：公开（Nginx/compose healthcheck 用）

响应：`{status:"ok",db:"ok",redis:"ok",queue_depth:0,disk:"ok"}`。异常时 `503` + `PROVIDER_DEGRADED` 等。

---

## 5. Webhook 回调与文件上传

### 5.1 Webhook / 平台数据回流回调

- 端点：`POST /api/v1/metrics/webhook/{platform}`（见 §4.12.2）。
- 认证：**签名校验**，非 Bearer。平台在头带 `X-NC-Signature: sha256=<hmac>`（对 `raw_body` 用平台共享密钥 HMAC-SHA256），服务端重算比对。
- 失败返回 `401 WEBHOOK_SIGNATURE_INVALID`；成功 `200 {code:0}`。
- 幂等：以 `event_id`（平台事件 ID）去重，重复事件静默返回成功。
- 超时：处理需在 5s 内返回，重活（如 OCR）入 Celery 异步；平台重试遵循其退避策略。
- 其他回调：发布网关适配器 `fetch_metrics()` 内部拉取不走过 Webhook；未来第三方事件（如评论回流）沿用同一签名约定，路径 `/api/v1/webhooks/{type}`。

### 5.2 文件上传约定（multipart）

- 端点：`POST /api/v1/knowledge/import?project_id={id}`。
- `Content-Type: multipart/form-data`；字段 `file` 为二进制；调用者必须是项目 Owner/Editor。
- 限制：原文件 ≤20 MB、PDF ≤300 页、解析文本 ≤200 万字符、单文件最多写入 100 个知识条目；超限返回 413/400。
- 允许扩展名：`.pdf, .docx, .md, .txt, .json, .jsonl`；不依赖客户端可伪造的 MIME 单独放行。
- 处理：请求内完成受限解析，写入 `knowledge_items` 后原子重建 `knowledge_vectors`；返回 `imported/chunks/item_ids`。
- 安全：当前版本不保存原始上传文件，只保存解析后的受限文本；不提供文件直链。

---

## 6. OpenAPI 生成说明

- **后端 schema 为单一事实源**：所有接口用 FastAPI `APIRouter` + Pydantic `BaseModel` 声明请求/响应，自动产出 `/api/v1/openapi.json`（带 `tags` 分组对应 §4 模块）。
- 响应包络 `{code,message,data}` 用统一 `ApiResponse[T]` 泛型模型，OpenAPI 中 `data` 为 `T`；错误响应用 `response_model` 标注 `ApiError`。
- 枚举（type/kind/role/mode/status）全部用 `Enum` 定义，生成带约束的客户端类型。
- **前端用 `openapi-ts` 生成客户端**：

```bash
# frontend/
npx openapi-ts --input http://localhost:8000/api/v1/openapi.json \
  --output src/api/client --client fetch
```

- 生成的 `schemas/*` 与 `paths/*` 禁止手改；后端改 schema → 重新生成 → 类型即同步，杜绝前后端契约漂移。
- SSE 端点（`/runs/{id}/events`）不进 OpenAPI 标准生成，前端用原生 `EventSource` 封装 `useSSE` hook（见技术实施方案 §2），`Last-Event-ID` 由 hook 管理。
- 文档可读性：每个端点 `summary`/`description` 用中文；`tags` 取模块名（auth/projects/contents/...），Swagger UI 自动分组。
- 版本兼容：破坏性变更升 `v2`，旧的 `/api/v1/openapi.json` 保留至下游迁移完成。

---

## 附录 A：端点速查（按模块计数）

| 模块 | 端点数（估） | 关键能力 |
|---|---|---|
| auth | 5 | 注册/登录/刷新/登出/me |
| projects & members | 9 | CRUD + 成员三角色管理 |
| contents (C1) | 8 | 统一内容树/AI 六件套/元校验 |
| novels | 2 | 创建 + bootstrap 工作流 |
| versions (C5) | 3 | 列表/diff/恢复 |
| workflows & runs (C2) | 13 | 定义 + run 全生命周期控制 |
| knowledge (C4) | 7 | 入库三通道/检索/四库/风格/相似度 |
| prompts | 6 | 版本/golden/lab/A·B |
| ai-calls (C8) | 3 | 追踪/明细/聚合 |
| narrative (C6) | 8 | 实体/伏笔/时间线/弧线/巡检/审核 |
| publish (C7) | 6 | 账号/全自动开关/三模式/安全/确认 |
| metrics | 4 | 录入/webhook/分析/ROI |
| admin | 6 | 模型路由/预算/敏感词/备份/审计/健康 |
| **合计** | **~80** | 覆盖 C1~C8 全量 |

> 说明：以上为 REST 端点计数，未含 SSE 流（§3）与 Webhook（§5.1）。实际随迭代微调，以 `openapi.json` 为准。

## 附录 B：与源文档一致性核对

- 路径前缀 `/api/v1`：对齐技术实施方案 §1 后端 `api/v1/` 模块划分；MVP §5 表为相对简写，已收敛。
- meta Schema 注册表校验：`contents` 写路径强制，对齐架构评审 §2 红线。
- bootstrap 八节点：对齐 MVP §3 / 架构评审 §3 预设工作流。
- 四节点类型 + 执行语义（节点级幂等/断点续跑/human 挂起不占 worker/失败单点重试）：对齐架构评审 §3 验收红线。
- C4 三道闸与相似度阈值：`similarity` 端点 + `SIMILARITY_*` 错误码对齐 §5.1。
- C7 三模式 + 国内全自动强约束：`publish` 模块 `mode` + `auto-publish-config` 对齐 §8.1。
- Offline L3 幂等重放：`Idempotency-Key` 约定对齐 §9。
- C5 文本/字段 diff：`versions/diff` 对齐 §6。
- C6 七层装配/实体/伏笔/时间线/弧线/巡检：`narrative` 模块对齐 §7。
- 统一响应包络结论：本规范 §1.3 明确采用 `{code,message,data}`。

---
*文档结束 · NovelCraft Personal Studio API 接口规范 V2.1*
