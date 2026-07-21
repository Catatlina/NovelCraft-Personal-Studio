# 星禾 AI 工作台 · Starlume AI v4

> Apple 极简风格 · 纯 HTML/CSS/JS 前端 + FastAPI 后端原型

## 项目概述

星禾 AI 工作台是全自动 AI 内容生产系统的管理界面。本版本采用 **Apple 官网式极简设计语言**，纯 HTML/CSS/JS 单页应用，零构建依赖，开箱即用。

### 设计哲学

- 🎨 **Apple 极简** — 大量留白、克制配色、Inter 字体、零发光、细描边
- 🌗 **深色/浅色** — 一键切换，纯黑 & Apple 阶灰
- 📱 **响应式** — 桌面 + 平板 + 手机全适配
- ⚡ **零依赖** — 单文件 HTML，内联 CSS/JS，无 npm/node 依赖
- 🔌 **API 驱动** — 通过 FastAPI 后端提供数据

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | HTML5 + CSS3 + Vanilla JS（单文件） |
| 后端 | Python FastAPI |
| 容器化 | Docker + Docker Compose |
| 部署 | Nginx 反向代理 |

## 快速开始

### 本地开发

```bash
# 1. 安装依赖
cd backend && pip install -r requirements.txt

# 2. 启动后端（自动托管前端静态文件）
python server.py

# 3. 浏览器访问
open http://localhost:8000
```

### Docker 部署

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f

# 验证
curl http://localhost:8000/api/v1/healthz
```

### VPS 一键部署

```bash
# 在 VPS 上执行
curl -sSL https://raw.githubusercontent.com/Catatlina/NovelCraft-Personal-Studio/starlume-v2/scripts/remote-deploy.sh | bash
```

## 页面结构

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录/注册 | `/` | JWT 邮箱认证 |
| 控制台 | `/console` | 统计概览、模块健康度、项目列表 |
| 小说工作台 | `/novel/dashboard` | 创作全景 |
| 扫榜中心 | `/novel/ranking` | 多平台榜单 |
| 三栏编辑器 | `/novel/editor` | AI 辅助写作 |
| 热点中心 | `/hotspot` | 实时热点追踪 |
| 版本管理 | `/versions` | 版本树与回溯 |
| Agent 中心 | `/agent` | AI Agent 管理 |
| Skill 中心 | `/skill` | 技能插件管理 |
| App Center | `/appcenter` | 应用模块市场 |
| AI 助手 | `/copilot` | 智能对话 |
| 设置 | `/settings` | 系统配置 |

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/v1/auth/register` | 注册 |
| `POST /api/v1/auth/login` | 登录 |
| `GET /api/v1/healthz` | 健康检查 |
| `GET /api/v1/stats/overview` | 统计数据 |
| `GET /api/v1/projects` | 项目列表 |
| `POST /api/v1/projects` | 创建项目 |
| `GET /api/v1/agents` | Agent 列表 |
| `GET /api/v1/skills` | Skill 列表 |
| `GET /api/v1/hotspots` | 热点列表 |
| `GET /api/v1/modules/health` | 模块健康度 |

## 设计令牌

- **品牌色**: 靛蓝 `#5B66DB`
- **背景**: 浅色 `#F5F5F7` / 暗色 `#000000`
- **字体**: Inter + PingFang SC
- **圆角**: 8px / 12px / 16px
- **间距**: 4px 基准递增

## License

MIT
