# NovelCraft Personal Studio — 项目进度

> 最后更新：2026-07-10 · 口径：商业SaaS标准 · 11 tests pass

## 诚实进度

| 阶段 | 完成度 | 核心交付 |
|---|---|---|
| M1 地基+MVP | ~88% | Auth+PG+Celery+RateLimit+Pool+12comp+11tests+ErrorBoundary |
| M2 小说引擎 | ~65% | 摘要+上下文+伏笔+auto-rewrite+lock+prompt版本 |
| M3 内容工作室 | ~40% | 短篇API+fanout AI生成+知识库+视频脚本+热点 |
| M4 发布出海 | ~25% | Adapter框架15平台+敏感词+Medium/WordPress+海外翻译 |
| M5 协作多端 | ~25% | 团队UI+邀请+日志+PWA+移动端+登出 |

```
M1 ██████████████████████████░ 88%
M2 ████████████████████░░░░░ 65%
M3 ████████████░░░░░░░░░░░░ 40%
M4 ████████░░░░░░░░░░░░░░░░ 25%
M5 ████████░░░░░░░░░░░░░░░░ 25%
───────────────────────────────
总体 ███████████████░░░░░░░░ ~55%
```

## 已验证 (11/11 tests)
- ✅ Auth全流程 + 跨用户隔离(403) + 速率限制(429)
- ✅ 项目创建/成员隔离
- ✅ PG 28表 + 连接池 + Alembic
- ✅ 12组件 + 10Tab + ErrorBoundary + LoginPage + ⌘K
- ✅ PWA注册 + 移动端CSS
- ✅ 日志 + 限流 + 鉴权

## 缺API Key无法e2e验证
- ⚠️ Bootstrap 8节点 + 连续章节 + 自动重写
- ⚠️ 上下文装配 + 伏笔/实体/时间线追踪
- ⚠️ 短篇AI生成 + fan-out内容改写
- ⚠️ 多模型路由(deepseek/claude/openai/gemini)

## 需外部服务
- ❌ Docker compose 全链路
- ❌ CI/CD (GitHub Actions)
- ❌ 真实发布adapter(需各平台API Key)
- ❌ 向量搜索/RAG
