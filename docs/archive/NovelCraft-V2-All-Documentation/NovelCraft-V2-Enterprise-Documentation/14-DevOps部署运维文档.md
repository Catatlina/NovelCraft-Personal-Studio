# DevOps 部署运维文档 (Enterprise Edition)

## 部署架构

单 VPS（4C8G+）+ Docker Compose 全栈部署。

## 服务拓扑

| 服务 | 镜像 | 数量 | 职责 |
|---|---|---|---|
| nginx | nginx:1.27-alpine | 1 | TLS 终止 · 反代 · SSE · 静态 |
| api | novelcraft/api | 1 | FastAPI uvicorn×2 |
| worker-plan/generate/review/publish/system | novelcraft/worker | 5 | Celery 五队列 |
| beat | novelcraft/worker | 1 | 定时调度 |
| postgres | pgvector/pgvector:pg16 | 1 | 唯一事实源 |
| redis | redis:7-alpine | 1 | broker·限流·预算·缓存·SSE |

## CI/CD Pipeline

```yaml
# GitHub Actions
name: CI/CD
on: [push, pull_request]
jobs:
  lint:      # ruff + mypy + eslint
  test:      # pytest + golden cases
  build:     # docker build
  deploy:    # 手动触发 → SSH → docker compose up -d
```

## 备份恢复

- 每日 02:00 pg_dump | age 加密 → rclone 异地
- RPO ≤ 24h / RTO ≤ 1h
- 每月恢复演练

## 监控告警

- /healthz 聚合检查（DB/Redis/队列/磁盘/Provider）
- 异常 → Telegram Bot
- 日志：structlog JSON → 本地滚动

## 升级流程

```bash
make deploy
# 备份 → pull → migrate → up → healthcheck → 失败回滚
```
