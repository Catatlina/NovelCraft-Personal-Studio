# NovelCraft Personal Studio — 开发文档总索引

> 最后更新：2026-07-12
> 需求基线：V2.2 ｜ 应用版本：2.2.0（与需求基线对齐；真实进度见 `PROJECT_PROGRESS.md`，最新审计见《27-全仓库审计报告》）

## 项目概述

NovelCraft Personal Studio 是以“扫榜成书”为主轴的全自动 AI 内容生产系统：扫描小说榜单、提取市场结构、生成原创选题并自动完成整书，所有生成结果统一进入书库。自媒体生产以热点扫描为主轴；灵感生成保留为次要入口。

- **仓库**: [Catatlina/NovelCraft-Personal-Studio](https://github.com/Catatlina/NovelCraft-Personal-Studio)
- **技术栈**: FastAPI + PostgreSQL + Celery + Redis + React + TypeScript + Vite
- **AI Provider**: DeepSeek (主), Claude/OpenAI/Gemini (降级链)

## 当前交付状态

旧版“总体 86%”按功能数量统计，无法代表 V2.2 主流程是否可用，现已废止。已有认证、AI Gateway、章节生成、上下文、伏笔、工作流骨架、发布与离线能力可以复用；但“真实榜单扫描 → 市场分析 → 原创选题 → 全自动整书 → 统一书库”和“热点 → 自媒体矩阵”的端到端验收尚未完成。分项状态见 `PROJECT_PROGRESS.md`。

## 系统架构

```
frontend/          React 19 + TypeScript + Vite（29 组件，129 条后端路由）
backend/          
  app/
    api/v1/       auth, config (admin APIs)
    core/         security, alerts
    ai/           providers (deepseek/claude/openai/gemini)
    services/     15 service modules
    workers/      Celery tasks + beat schedule
  alembic/        PostgreSQL migrations（17 个迁移，26+ 张表，单头线性）
scripts/          backup.sh, migrate_v1_to_v2.py, stress_test.py
nginx/            novelcraft.conf (SSE optimization)
docker-compose.yml
```

## API 端点一览

| 类别 | 端点 | 说明 |
|---|---|---|
| Auth | /auth/register, /login, /refresh, /me | JWT 认证 |
| Projects | /projects, /projects/{id}/novels, /short-stories | 项目管理 |
| Ranking（规划） | /ranking/sources/{source}/scan, /ranking/snapshots/{id}/analyze | 扫榜与市场分析 |
| Library（规划） | /library/books | 统一书库 |
| Bootstrap | /novels/{id}/bootstrap, /continue | 小说生成兼容入口 |
| Content | /contents, /contents/{id}/ai/{op} | 内容 CRUD + AI 操作 |
| Runs | /runs/{id}, /runs/{id}/events | 工作流运行 |
| Knowledge | /knowledge, /knowledge/search, /daily-briefing | 知识库 |
| Social | /contents/{id}/fanout, /video-script | 自媒体发布 |
| Publish | /publish, /publish/records | 发布网关 |
| Overseas | /overseas/translate | 出海翻译 |
| Admin | /admin/providers, /model-routes, /budgets, /prompts | AI 配置 |
| Collab | /collaboration/invite, /members, /logs | 协作 |
| Style | /knowledge/style-learn, /check-similarity | 风格仿写 |
| Prompts | /prompts/lab | Prompt 实验室 |
| Health | /healthz | 健康检查 |

## 服务模块

| 模块 | 说明 |
|---|---|
| summarizer | 分层摘要（章/卷/全书） |
| assembler | 7 层上下文装配器 |
| entity_tracker | 实体状态追踪 |
| foreshadowing | 伏笔系统 |
| timeline | 时间线 + 人物弧线 |
| short_story | 短篇生成（5 模板） |
| social_media | 自媒体 10 平台 + 视频脚本 |
| knowledge_hub | 知识库检索 + 入库 |
| hotspot | 热点采集 + 每日晨报 |
| style_learn | 风格学习 + 相似度检查 |
| publish_gateway | 发布网关 15 平台 |
| overseas | 出海翻译管线 |
| collaboration | 协作（角色/日志） |

## 前端页面（10 Tab）

1. 扫榜中心（目标主入口，待实现）
2. 进度（Bootstrap 工作流）
3. 审阅（7 维质量雷达）
4. 编辑器（6 种 AI 操作）
5. 成本追踪（ai_calls 明细）
6. Prompt 管理
7. 工作流编排（DAG 编辑器）
8. 系统设置（Providers/模型/预算/Prompts 可视化配置）
9. 内容工作室（热点驱动自媒体/短篇/知识库）
10. 发布看板（发布/出海/数据）

现有前端仍以创作向导为入口，尚未达到上述 V2.2 信息架构，不能视为主流程验收通过。

## 开发文档

详细开发文档位于 `docs/NovelCraft-开发文档/`：
- 01-项目全局分析报告.md
- 02-架构评审报告.md
- 03-开发路线图.md
- 04-MVP方案.md
- 05-技术实施方案.md
- 06-开发任务清单.md
- 07-工程协作规范.md
- 08-需求规格说明书PRD.md
- 09-数据库设计文档.md
- 10-API接口规范.md
- 11-Prompt工程规范.md
- 12-设计系统规范.md
- 13-测试计划与用例.md
- 14-部署与运维手册.md
- 15-开发环境搭建指南.md
- 16-编码规范.md
- 17-安全设计文档.md
- 18-架构决策记录ADR.md
- 19-开源项目融合基线.md

## AI 配置系统

交互请求可在前端「系统设置 → 全局配置」填写 BYOK，密钥仅保存在当前浏览器 `sessionStorage`，关闭会话后清除。Worker、定时任务及服务端默认配置只读取环境变量，并在服务重启后生效：

| 配置项 | 说明 | 存储位置 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 环境变量 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | 环境变量，默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | DeepSeek 默认模型 | 环境变量，默认 `deepseek-chat` |
| `CLAUDE_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 各 Provider API Key | 环境变量 |
| `AI_PRICE_CNY_PER_MILLION` | 各 Provider 输入/输出每百万 token 单价 JSON | 环境变量 |

**配置优先级**：当前请求的 BYOK Header > 服务环境变量。数据库 `settings` 表中的历史 Provider 值不再作为运行时密钥来源。
**API Key 安全**：前端 BYOK 字段为密码输入框且不落库；生产/定时任务密钥由部署环境注入，不通过管理 API 返回。

## 启动命令

```bash
# 后端
cd backend && source .venv/bin/activate
uvicorn app.main:app --port 8000
celery -A app.workers.celery_app worker --loglevel=info

# Celery Beat (定时任务)
celery -A app.workers.celery_app beat --loglevel=info

# 前端
cd frontend && npm run dev

# Docker 一键部署
docker compose up -d
```
