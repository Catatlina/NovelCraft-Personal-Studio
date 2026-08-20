# Starlume AI — 小说创作工作台

> 最后更新：2026-07-29
> 实时状态以 `docs/AI_HANDOFF.md`、`docs/REQUIREMENTS_TRACEABILITY.md` 和 `PROJECT_PROGRESS.md` 为准。

## 项目概述

Starlume AI 是人工主导、多 AI 协作、全过程可追溯的中文长篇小说创作工作台。当前代码已具备小说首页、创作向导、扫榜选书、书库、创作进度、章节编辑、审阅与一致性、发布准备和小说设置；产品正在按最小垂直切片从“AI 主生成”迁移为“人工创意 + AI 辅助扩写/建议 + 人工改写确认”。AI 创作必须走真实 Provider；失败必须明确失败，AI 编辑必须先预览再由用户应用。

历史自媒体、发布、协作等模块不再出现在当前产品 UI，但其旧数据、数据库迁移和仍被小说主线复用的后端源码暂不删除。

- **仓库**: [Catatlina/starlume-ai-studio](https://github.com/Catatlina/starlume-ai-studio)
- **技术栈**: FastAPI + PostgreSQL + Celery + Redis + React + TypeScript + Vite
- **AI Provider**: 当前本地真实验收以 DeepSeek 为准；Claude / OpenAI / Gemini 保留 BYOK/环境变量配置入口，未配置对应 key 时不纳入本轮阻塞。业务运行时不使用 mock，不做伪降级，Provider 失败必须明确报错。

## 当前交付状态

旧版按功能数量计算的百分比进度已废止。当前以需求追踪矩阵、确定性真库 E2E、真实 Provider 证据和生产部署证据判定状态。V3 Bootstrap 已扩展为 20 个节点（19 个 AI 节点 + 1 个人工定名门禁）；当前版本仍需完成真实 Provider 全链复验与生产部署，不能仅凭页面或单元测试宣称整条小说链已验收。

## 系统架构

```
frontend/          React 19 + TypeScript + Vite
backend/          
  app/
    api/v1/       auth, config (admin APIs)
    core/         security, alerts
    ai/           providers (deepseek/claude/openai/gemini)
    services/     15 service modules
    workers/      Celery tasks + beat schedule
  alembic/        PostgreSQL migrations
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

## 前端页面（八项小说页面）

当前默认入口为「小说首页」（Starlume AI 小说优先）。小说主线保留八项页面：小说首页、创作向导、扫榜选书、我的书库、创作进度、章节编辑器、审阅与一致性、小说设置。非小说模块（热点、发布、知识库、分发、协作、智能体等）已从产品 UI 隐藏——其历史数据与仍被后端主链使用的源码保留，不删除。详见 `docs/AI_HANDOFF.md` 与 `docs/KNOWN_ISSUES.md`。

边界说明：工作流 DAG 页面当前是“项目级设计稿”保存入口，只有系统 Bootstrap 工作流可执行；页面已显式标注，不将自定义 DAG 冒充为可执行工作流。

## 开发文档

现行需求、架构、开发路线、AI 门禁、AI 遵从、实施和交接文档位于 [`docs/Starlume-AI-开发文档/`](docs/Starlume-AI-开发文档/README.md)。`docs/NovelCraft-开发文档/` 只保留历史设计和迁移证据，不再作为新产品需求入口。

## AI 配置系统

交互请求可在前端「系统设置 → 全局配置」填写 BYOK，密钥仅保存在当前浏览器 `sessionStorage`，关闭会话后清除，并通过 `X-Api-Key` / `X-Api-Base-Url` / `X-Model` 传给本次请求。DeepSeek、Claude、OpenAI、Gemini 的交互式调用均支持该方式；Worker、定时任务及服务端默认配置只读取环境变量，并在服务重启后生效：

| 配置项 | 说明 | 存储位置 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 环境变量 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | 环境变量，默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | DeepSeek 默认模型 | 环境变量，默认 `deepseek-chat` |
| `TAVILY_API_KEY` | 服务端实时网感搜索 Key；开启作品的 `web_research_mode=required` 后必需 | 环境变量，不返回前端 |
| `TAVILY_BASE_URL` | Tavily 地址，生产必须为 `https://api.tavily.com` | 环境变量，默认官方地址 |
| `NOVELCRAFT_WEB_RESEARCH_PROVIDER` | 实时研究提供方 | 环境变量，默认 `tavily` |
| `NOVELCRAFT_WEB_RESEARCH_CACHE_TTL_SECONDS` | 网感研究缓存时长 | 环境变量，默认 `21600` |
| `CLAUDE_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 其他真实 Provider Key | 环境变量或浏览器 BYOK |
| `NOVELCRAFT_CREDENTIALS_KEY` | 平台连接凭据 Fernet 加密密钥 | 环境变量；生产必填 |
| `CLAUDE_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 各 Provider API Key | 环境变量 |
| `AI_PRICE_CNY_PER_MILLION` | 各 Provider 输入/输出每百万 token 单价 JSON | 环境变量 |

`NOVELCRAFT_*`、`novelcraft` 数据库名和旧事件名是历史兼容标识。对外产品名已经统一为 Starlume AI；这些技术标识只能在有迁移、回滚和部署验证的独立批次中修改。

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
