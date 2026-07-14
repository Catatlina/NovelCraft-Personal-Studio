# NovelCraft Personal Studio — 开发文档总索引

> 最后更新：2026-07-14
> 需求基线：V2.2 ｜ 应用版本：2.2.0（与需求基线对齐；真实进度见 `PROJECT_PROGRESS.md`）

## 项目概述

NovelCraft Personal Studio 是以“扫榜成书”为主轴的全自动 AI 内容生产系统：扫描小说榜单、提取市场结构、生成原创选题并自动完成整书，所有生成结果统一进入书库。自媒体生产以热点扫描为主轴；灵感生成保留为次要入口。

- **仓库**: [Catatlina/NovelCraft-Personal-Studio](https://github.com/Catatlina/NovelCraft-Personal-Studio)
- **技术栈**: FastAPI + PostgreSQL + Celery + Redis + React + TypeScript + Vite
- **AI Provider**: 当前本地真实验收以 DeepSeek 为准；Claude / OpenAI / Gemini 保留 BYOK/环境变量配置入口，未配置对应 key 时不纳入本轮阻塞。业务运行时不使用 mock，不做伪降级，Provider 失败必须明确报错。

## 当前交付状态

旧版“总体 86%”按功能数量统计，无法代表 V2.2 主流程是否可用，现已废止。已有认证、AI Gateway、章节生成、上下文、伏笔、工作流骨架、发布与离线能力可以复用；当前 Playwright 主链已覆盖“CSV 榜单导入→市场分析→原创选题→建书→书库”和平台连接/成本页，真实 DeepSeek key 存在时会执行 protected AI 成书用例。热点→自媒体矩阵已有后端真实网关回归与 Dashboard 入口，并支持配置真实历史归档 URL 后回填近 7 天热点快照；没有授权历史源时接口明确返回 unsupported/502，不伪造历史数据。成稿质量人工验收、真实平台发布回执仍未完成。分项状态见 `PROJECT_PROGRESS.md`。

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
| Knowledge | /knowledge, /knowledge/search, /daily-briefing | 知识库；daily briefing 仅使用真实采集/已采集热点，不由 AI 编造热点 |
| Social | /hotspots, /hotspots/history, /hotspots/history/backfill, /contents/{id}/fanout, /video-script | 热点采集、历史归档回填、自媒体发布 |
| Publish | /publish, /publish/records | 发布网关 |
| Overseas | /overseas/translate | 出海翻译 |
| Admin | /admin/providers, /model-routes, /budgets, /prompts | AI 配置、预算 |
| Platform Connections | /platform-connections/* | 热点源、发布平台、告警等真实账号/API 可视化配置 |
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

## 前端页面（19 Tab）

当前默认入口为「扫榜中心」。页面包括：扫榜中心、书库、创作向导、生成进度、审阅、编辑器、成本追踪、Prompt、工作流、设置、工作室、发布、热点、知识库、分发、版本树、伏笔、协作、智能体。

边界说明：工作流 DAG 页面当前是“项目级设计稿”保存入口，只有系统 Bootstrap 工作流可执行；页面已显式标注，不将自定义 DAG 冒充为可执行工作流。

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

交互请求可在前端「系统设置 → 全局配置」填写 BYOK，密钥仅保存在当前浏览器 `sessionStorage`，关闭会话后清除，并通过 `X-Api-Key` / `X-Api-Base-Url` / `X-Model` 传给本次请求。DeepSeek、Claude、OpenAI、Gemini 的交互式调用均支持该方式；Worker、定时任务及服务端默认配置只读取环境变量，并在服务重启后生效：

| 配置项 | 说明 | 存储位置 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 环境变量 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | 环境变量，默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | DeepSeek 默认模型 | 环境变量，默认 `deepseek-chat` |
| `CLAUDE_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 其他真实 Provider Key | 环境变量或浏览器 BYOK |
| `NOVELCRAFT_CREDENTIALS_KEY` | 平台连接凭据 Fernet 加密密钥 | 环境变量；生产必填 |
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
