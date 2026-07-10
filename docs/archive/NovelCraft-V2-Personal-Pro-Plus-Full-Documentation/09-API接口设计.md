# API 接口设计

## 概述

RESTful API + SSE 实时推送。Base URL: `/api/v1`

## 认证

- JWT (access + refresh token)
- Header: `Authorization: Bearer <token>`
- 所有接口（除 /auth/* 和 /healthz）需要认证

## 模块与端点（约 80 个）

### Auth
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/register | 注册 |
| POST | /auth/login | 登录 |
| POST | /auth/refresh | 刷新 token |
| POST | /auth/logout | 登出 |

### Projects
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /projects | 项目列表/创建 |
| GET/PUT/DELETE | /projects/{id} | 项目详情/更新/删除 |
| GET/POST/DELETE | /projects/{id}/members | 成员管理 |

### Contents (C1)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /projects/{id}/contents | 内容列表/创建 |
| GET/PUT | /contents/{id} | 内容详情/更新（自动版本快照） |
| POST | /contents/{id}/ai/{op} | AI 操作（polish/expand/condense/rewrite/deai） |
| POST | /contents/{id}/derive | 派生（一稿多平台） |

### Novels & Bootstrap
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /projects/{id}/novels | 创建小说 |
| POST | /novels/{id}/bootstrap | 启动 bootstrap 工作流 |
| GET | /novels/{id}/chapters | 章节列表 |

### Workflows & Runs (C2)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /workflows | 工作流列表/创建 |
| GET/PUT | /workflows/{id} | 工作流详情/更新定义 |
| POST | /workflows/{id}/run | 启动运行 |
| GET | /runs/{id} | 运行状态 |
| GET | /runs/{id}/events | SSE 进度流 |
| POST | /runs/{id}/nodes/{key}/confirm | human 节点确认 |
| POST | /runs/{id}/nodes/{key}/retry | 单节点重试 |
| POST | /runs/{id}/pause | 暂停 |
| POST | /runs/{id}/resume | 恢复 |
| POST | /runs/{id}/cancel | 取消 |

### AI & Prompts (C3)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /prompts | Prompt 列表/创建 |
| GET/PUT | /prompts/{id} | Prompt 详情/更新（新版本） |
| GET | /ai-calls | AI 调用记录（可按 run_id 过滤） |
| GET | /ai-calls/costs | 成本统计 |
| GET | /model-routes | 模型路由配置 |

### Knowledge (C4)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /knowledge | 知识列表/录入 |
| GET/PUT/DELETE | /knowledge/{id} | 知识条目管理 |
| POST | /knowledge/search | 向量检索 |
| POST | /knowledge/ingest | 文件/网页入库 |

### Versions (C5)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /contents/{id}/versions | 版本列表 |
| GET | /contents/{id}/versions/{vid} | 版本详情 |
| POST | /contents/{id}/versions/{vid}/restore | 恢复版本 |
| GET | /contents/{id}/versions/{vid}/diff | 版本对比 |

### Publishing (C7)
| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /platform-accounts | 平台账号管理 |
| POST | /contents/{id}/publish | 发布到平台 |
| GET | /publish-records | 发布记录 |
| GET | /metrics | 数据回流统计 |

### Admin & Health
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /healthz | 健康检查 |
| GET | /admin/audit-logs | 审计日志 |
| GET | /admin/budgets | 预算状态 |
