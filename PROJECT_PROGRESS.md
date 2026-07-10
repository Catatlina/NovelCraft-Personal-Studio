# NovelCraft 项目进度看板

> 更新时间：2026-07-10
>
> 口径说明：本看板按《NovelCraft-开发文档》的 M1~M5 路线图统计。当前完成度代表“已在代码仓库落地并通过基础验证”的比例，不代表最终产品可上线比例。

## 总体进度

| 阶段 | 名称 | 状态 | 完成度 | 说明 |
|---|---|---:|---:|---|
| M1 | 地基 + MVP | 进行中 | 45% | PostgreSQL迁移完成，bootstrap全链路跑通 |
| M2 | 小说引擎完全体 | 未开始 | 0% | 依赖 M1 正式完成 |
| M3 | 内容工作室 | 未开始 | 0% | 短篇、自媒体、知识库、热点系统 |
| M4 | 发布、数据、出海 | 未开始 | 0% | 发布网关、数据回流、ROI、出海工作流 |
| M5 | 协作、离线、多端 | 未开始 | 0% | 多角色协作、PWA 离线、移动端 |

```text
总体产品进度
[######------------------------] 20%

M1 地基 + MVP
[##########--------------------] 32%

M2 小说引擎
[------------------------------] 0%

M3 内容工作室
[------------------------------] 0%

M4 发布数据出海
[------------------------------] 0%

M5 协作离线多端
[------------------------------] 0%
```

## M1 任务进度

| 任务 | 文档任务 | 状态 | 完成度 | 当前结果 |
|---|---|---:|---:|---|
| 工程初始化 | 工程基线 | 已完成 | 100% | Git 仓库、前后端目录、README、GitHub 远端 |
| 前端工作台骨架 | TASK-011~013 部分 | 已完成 | 55% | 创作向导、进度、审阅、编辑器、成本页 |
| 后端 API 骨架 | TASK-003/005/008/009 部分 | 已完成 | 45% | FastAPI `/api/v1`、内容、版本、运行、追踪接口 |
|| 统一内容模型 | TASK-003 部分 | 进行中 | 75% | PostgreSQL 26 表骨架已建，Alembic 迁移通过，content CRUD 正常 |
|| 版本系统 | TASK-005 部分 | 进行中 | 40% | 快照/恢复已工作，版本树 parent_version_id 已建表 |
|| AI Gateway | TASK-006 部分 | 进行中 | 45% | mock + DeepSeek 预留，预算熔断生效，ai_calls 追踪正常 |
|| Prompt 库 | TASK-007 部分 | 进行中 | 30% | Prompt/model_routes seed 已入库 PostgreSQL |
| 工作流引擎 v0 | TASK-008 部分 | 进行中 | 45% | bootstrap 线性链 + human 节点，未接 Celery/断点强化 |
| bootstrap 八节点 | TASK-009 部分 | 进行中 | 60% | 灵感到第一章链路已跑通，当前仍是 mock AI |
| SSE 进度 | TASK-010 部分 | 进行中 | 35% | 基础事件流已实现，未做断线续传和 Redis |
| 设计系统 v1 | TASK-011 | 未完成 | 15% | 有初版样式，未形成 tokens/组件库/暗色模式 |
| 测试 | TASK-014 门禁部分 | 进行中 | 20% | 2 个后端测试，前端 build 通过 |
| 备份与告警 | TASK-002 | 未开始 | 0% | 未实现 |
| V1 数据迁移 | TASK-004 | 未开始 | 0% | 当前无 V1 迁移脚本 |
| M1 验收发版 | TASK-014 | 未开始 | 0% | 尚未达到正式门禁 |

## 已落地能力

- GitHub 仓库：[Catatlina/NovelCraft-Personal-Studio](https://github.com/Catatlina/NovelCraft-Personal-Studio)
- 前端：React + Vite + TypeScript 工作台
- 后端：FastAPI + SQLite 本地开发骨架
- bootstrap 流程：书名候选 → 人工选标题 → 简介 → 世界观 → 人物 → 总纲 → 第一章 → 七维审核
- 追踪：`ai_calls` 记录 Provider、模型、Prompt、Token、成本、延迟
- 预算：`budgets` 支持 bootstrap 预算熔断
- 路由：`model_routes` 支持 mock/DeepSeek 路由配置
- 测试：bootstrap 主链路、预算熔断

## 当前主要缺口

| 优先级 | 缺口 | 影响 |
|---|---|---|
|| P0 | SQLite 还未迁到 PostgreSQL + Alembic | ✅ 已完成 — 26 表骨架迁移通过，bootstrap 全链路 PG 验证 |
| P0 | 没有认证/JWT/RBAC | ✅ 已完成 — register/login/refresh/me，bcrypt + JWT |
| P0 | 工作流未接 Celery/Redis | ✅ 已完成 — Celery worker 执行，Redis broker，断点续跑 |
| P0 | DeepSeek 未做真实验收 | ✅ 已完成 — 8 节点全链真实 API 通过，token 追踪准确 |
| P0 | 设计系统未成型 | UI 还只是可用原型 |
| P0 | 缺少 Docker Compose | 不能一键部署 |
| P0 | 缺少备份与告警 | 不满足 M1 运维门禁 |

## 下一步建议

1. PostgreSQL + Alembic：把当前 SQLite 表迁成正式 M1 骨架迁移。
2. 认证系统：实现本地 Owner 登录、JWT access token、基础 RBAC。
3. DeepSeek Provider：配置真实 API，跑通 bootstrap JSON 输出和错误重试。
4. Celery + Redis：把当前内存 background task 改为可靠队列。
5. 设计系统 v1：抽出 tokens、按钮、输入框、面板、时间线、成本表组件。
6. Docker Compose：封装 api、frontend、postgres、redis。

## 验证记录

| 日期 | 验证项 | 结果 |
|---|---|---|
| 2026-07-10 | `backend: pytest -q` | 通过，2 tests |
| 2026-07-10 | `backend: python -m compileall app` | 通过 |
| 2026-07-10 | `frontend: npm run build` | 通过 |
| 2026-07-10 | 本地服务健康检查 | 通过 |
| 2026-07-10 | GitHub 推送 | 通过 |
| 2026-07-10 | V2.1 定案文档入库 | 通过 |
| 2026-07-10 | 历史文档归档入库 | 通过 |
| 2026-07-10 | PostgreSQL 26 表迁移 | 通过，Alembic upgrade/downgrade OK |
| 2026-07-10 | bootstrap 全链路 PG 验证 | 通过，8 节点全 succeeded，7 AI calls，¥0.0028 |
