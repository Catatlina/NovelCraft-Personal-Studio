# NovelCraft Personal Studio — 开发文档总索引

> 最后更新：2026-07-10
> 版本：v2.0.0-m5 + core-hardening（持续开发，真实进度见 `PROJECT_PROGRESS.md`）

## 项目概述

NovelCraft Personal Studio 是一站式 AI 内容工厂，覆盖长篇小说、短篇、自媒体、短视频脚本、出海翻译的完整创作→发布管线。

- **仓库**: [Catatlina/NovelCraft-Personal-Studio](https://github.com/Catatlina/NovelCraft-Personal-Studio)
- **技术栈**: FastAPI + PostgreSQL + Celery + Redis + React + TypeScript + Vite
- **AI Provider**: DeepSeek (主), Claude/OpenAI/Gemini (降级链)

## 里程碑进度

| 阶段 | 进度 | 任务完成 | 核心交付 |
|---|---|---|---|
| M1 地基+MVP | 97% | 部分验收 | PG 骨架 + JWT 会话加固 + DeepSeek + Celery + Docker |
| M2 小说引擎 | 95% | 部分验收 | 摘要 + 上下文 + 连续/批量章节 + 伏笔 + 质量门禁 |
| M3 内容工作室 | 75% | 持续开发 | 短篇 + 自媒体 + 本地向量知识库 + 热点 + 风格 |
| M4 发布出海 | 65% | 持续开发 | 发布网关 + 敏感词检查 + 出海翻译管线 |
| M5 协作多端 | 75% | 部分验收 | 协作三角色 + PWA + 离线编辑冲突树 + AI 出站队列 |

```text
M1 ███████████████████████████████░ 97%
M2 ██████████████████████████████░░ 95%
M3 ████████████████████████░░░░░░░░ 75%
M4 █████████████████████░░░░░░░░░░░ 65%
M5 ████████████████████████░░░░░░░░ 75%
───────────────────────────────────────
总体 ███████████████████████████░░░░░ 84%
```

## 系统架构

```
frontend/          React 18 + TypeScript + Vite (10 component pages)
backend/          
  app/
    api/v1/       auth, config (admin APIs)
    core/         security, alerts
    ai/           providers (deepseek/claude/openai/gemini)
    services/     15 service modules
    workers/      Celery tasks + beat schedule
  alembic/        PostgreSQL migrations (26 tables)
scripts/          backup.sh, migrate_v1_to_v2.py, stress_test.py
nginx/            novelcraft.conf (SSE optimization)
docker-compose.yml
```

## API 端点一览

| 类别 | 端点 | 说明 |
|---|---|---|
| Auth | /auth/register, /login, /refresh, /me | JWT 认证 |
| Projects | /projects, /projects/{id}/novels, /short-stories | 项目管理 |
| Bootstrap | /novels/{id}/bootstrap, /continue | 小说生成 |
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

1. 创作向导（灵感到第一章）
2. 进度（Bootstrap 工作流）
3. 审阅（7 维质量雷达）
4. 编辑器（6 种 AI 操作）
5. 成本追踪（ai_calls 明细）
6. Prompt 管理
7. 工作流编排（DAG 编辑器）
8. 系统设置（Providers/模型/预算/Prompts 可视化配置）
9. 内容工作室（短篇/自媒体/知识库/热点）
10. 发布看板（发布/出海/数据）

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

## AI 配置系统

所有 AI 配置均可在前端「系统设置 → 全局配置」页面可视化编辑，即时生效：

| 配置项 | 说明 | 存储位置 |
|---|---|---|
| `deepseek_api_key` | DeepSeek API Key | DB (settings 表) |
| `deepseek_base_url` | DeepSeek API 地址 | DB，默认 `https://api.deepseek.com` |
| `deepseek_model` | DeepSeek 默认模型 | DB，默认 `deepseek-chat` |
| `claude_api_key` / `openai_api_key` / `gemini_api_key` | 各 Provider API Key | DB |
| `claude_base_url` / `openai_base_url` / `gemini_base_url` | 各 Provider API 地址 | DB |
| `bootstrap_budget_cny` | Bootstrap 预算上限(¥) | DB，默认 2.0 |
| `request_timeout_seconds` | AI 请求超时 | DB，默认 45 |

**配置优先级**: 环境变量 > 数据库设置。修改后无需重启，即时生效。
**API Key 安全**: API Key 字段在前端为密码输入框，API 返回时自动脱敏（仅显示前8后4字符）。

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
