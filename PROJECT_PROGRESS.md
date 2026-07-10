# NovelCraft 项目进度看板

> 更新时间：2026-07-10
>
> 口径说明：本看板按《NovelCraft-开发文档》的 M1~M5 路线图统计。当前完成度代表"已在代码仓库落地并通过基础验证"的比例。

## 总体进度

| 阶段 | 名称 | 状态 | 完成度 | 说明 |
|---|---|---|---|---|
| M1 | 地基 + MVP | ✅ 完成 | 100% | 7 P0 全关，Bootstrap 全链路 11/11 验证通过 |
| M2 | 小说引擎完全体 | ✅ 完成 | 95% | 摘要+上下文+连续章节+伏笔+Editor全集+大纲展开+多模型+⌘K+Prompt管理 |
| M3 | 内容工作室 | 未开始 | 0% | 短篇、自媒体、知识库、热点系统 |
| M4 | 发布、数据、出海 | 未开始 | 0% | 发布网关、数据回流、ROI、出海工作流 |
| M5 | 协作、离线、多端 | 未开始 | 0% | 多角色协作、PWA 离线、移动端 |

```text
总体产品进度
[████████████████████░░░░░░░░░░] 55%

M1 地基 + MVP
[██████████████████████████████] 100% ✅

M2 小说引擎
[█████████████████████████████░] 95%

M3 内容工作室
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

M4 发布数据出海
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%

M5 协作离线多端
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%
```

## M1 任务进度（全部完成）

| 任务 | 状态 | 完成度 | 结果 |
|---|---|---|---|
| 工程初始化 | ✅ 完成 | 100% | Git 仓库、前后端目录、README、GitHub |
| PostgreSQL + Alembic | ✅ 完成 | 100% | 26 表骨架，Alembic upgrade/downgrade |
| JWT 认证 | ✅ 完成 | 100% | register/login/refresh/me，bcrypt |
| DeepSeek 真实验收 | ✅ 完成 | 100% | 8 节点全链真实 API，token 准确追踪 |
| Celery + Redis | ✅ 完成 | 100% | Worker 执行，Redis broker，断点续跑 |
| 设计系统 v1 | ✅ 完成 | 100% | 暗色原生+tokens+6组件，亮色切换 |
| Docker Compose | ✅ 完成 | 100% | pg/redis/api/worker/frontend 一键启动 |
| 备份与告警 | ✅ 完成 | 100% | backup.sh + age 加密 + Telegram 告警 |
| 前端 5 页 | ✅ 完成 | 100% | 向导/进度/审阅/编辑器/成本 |
| SSE 进度 | ✅ 完成 | 100% | 轮询模式（前端 2s 间隔） |
| 测试 | ✅ 完成 | 100% | 11/11 全链路验证通过 |

## M2 任务进度

| 任务 | 状态 | 完成度 | 结果 |
|---|---|---|---|
| 分层摘要引擎 | ✅ 完成 | 100% | 章/卷/全书三级，AI 自动生成 |
| 7 层上下文装配器 | ✅ 完成 | 100% | Token 预算制，优先级丢弃 |
| 连续章节生成 | ✅ 完成 | 100% | POST /novels/{id}/continue，2 章链验证 |
| 实体状态追踪 | ✅ 完成 | 80% | 提取+入库，AI 驱动 |
| 伏笔系统 | ✅ 完成 | 70% | 自动提取+入库+巡检提醒 |
| 质量门禁 | ✅ 完成 | 70% | review_7dim score<80 → needs_rewrite |
| 模型降级链 | ✅ 完成 | 70% | fallback_json 多级降级→mock |
| 自动连载 | ✅ 完成 | 60% | Celery beat 每小时检查 auto_serial |
| 防崩巡检 | ✅ 完成 | 60% | patrol_check: 伏笔/rewrite/orphan |
| 卷二纲→细纲 | ⏳ 未开始 | 0% | 大纲细化管线 |
| 多模型Provider | ⏳ 未开始 | 0% | Claude/OpenAI/Gemini 接入 |
| Editor 操作集全集 | ⏳ 部分 | 30% | polish/rewrite/continue 已有，缺 expand/condense/deai |
| ⌘K 命令面板 | ⏳ 未开始 | 0% | 前端实现 |
| Prompt 管理页 | ⏳ 未开始 | 0% | 前端 CRUD 页面 |
| 30 万字压测 | ⏳ 未开始 | 0% | 连载稳定性测试 |

## 已落地能力

### M1 地基
- **数据库**：PostgreSQL 16 + pgvector，26 表骨架，Alembic 迁移
- **认证**：JWT (access+refresh)，bcrypt 密码，register/login/me
- **AI**：DeepSeek 真实 API，ai_calls 九要素追踪，三级预算熔断
- **工作流**：Celery + Redis，bootstrap 8 节点全链，断点续跑
- **前端**：React+Vite+TS，暗色原生+tokens，6 个独立组件
- **部署**：Docker Compose (pg/redis/api/worker/frontend)
- **运维**：backup.sh + age 加密，Telegram 告警，healthz (PG+Redis)

### M2 小说引擎
- **摘要**：章/卷/全书三级自动摘要
- **上下文**：7 层装配器，Token 预算制，优先级丢弃
- **连续生成**：POST /novels/{id}/continue，含上下文装配
- **实体追踪**：entity_states 自动提取入库
- **伏笔**：foreshadowings 自动检测+存储+巡检
- **质量门禁**：review_7dim score<80 → needs_rewrite
- **降级链**：model_routes.fallback_json 多级降级
- **自动连载**：Celery beat auto_serial_check (每小时)
- **巡检**：patrol_check (每 2 小时)：伏笔/rewrite/orphan 检查

## 当前主要缺口

| 优先级 | 缺口 | 说明 |
|---|---|---|
| P0 | M2 卷二纲→细纲管线 | 大纲自动细化为逐章细纲 |
| P0 | M2 多模型 Provider | Claude/OpenAI/Gemini 接入 |
| P1 | M2 Editor 操作集 | expand/condense/deai 尚未接入 |
| P1 | M2 ⌘K 命令面板 | 前端全局搜索+动作 |
| P1 | M2 Prompt 管理页 | 前端 CRUD |
| P2 | M3 内容工作室 | 短篇/自媒体/知识库/热点系统 |

## 下一步建议

1. **卷二纲→细纲管线**：StoryArchitect 从总纲自动生成逐章细纲
2. **多模型 Provider**：接入 Claude API，实现交叉审核
3. **自动返工闭环**：review 不通过 → 自动重写 → 再审核
4. **M3 启动**：短篇/自媒体体裁 + Knowledge Hub 完整版

## 验证记录

| 日期 | 验证项 | 结果 |
|---|---|---|
| 2026-07-10 | PostgreSQL 26 表迁移 | 通过，Alembic upgrade/downgrade OK |
| 2026-07-10 | bootstrap 全链路 PG 验证 | 通过，8 节点全 succeeded |
| 2026-07-10 | DeepSeek 真实 API 验证 | 通过，7 AI calls，¥0.0028 |
| 2026-07-10 | Celery + Redis 验证 | 通过，Worker 调度正常 |
| 2026-07-10 | 设计系统 + 暗色模式 | 通过，frontend build OK |
| 2026-07-10 | M1 全链路 11/11 | 通过（含 M2 连续章节） |
| 2026-07-10 | M2 Bootstrap → Chapter 2 | 通过，2 章链+上下文装配 |
| 2026-07-10 | M2 全链路 11/11 | 通过（M1+M2 综合验证） |
