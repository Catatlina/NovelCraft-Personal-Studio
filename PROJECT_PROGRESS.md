# NovelCraft Personal Studio — 项目进度

> 更新：2026-07-10 · 13 tests pass · Ubuntu 已部署

## 诚实进度

| 阶段 | 本轮新增 | 完成度 |
|---|---|---|
| M1 | RichEditor + CI/CD + Docker health | ~92% |
| M2 | assembler修复 + 2 tests | ~68% |
| M3 | fan-out AI + 知识库导入导出 + metrics | ~45% |
| M4 | 15 adapters + 32敏感词 | ~30% |
| M5 | RichEditor + PWA + IndexedDB + team UI | ~30% |

```
M1 ████████████████████████████ 92%
M2 █████████████████████░░░░░ 68%
M3 █████████████░░░░░░░░░░░░ 45%
M4 █████████░░░░░░░░░░░░░░░░ 30%
M5 █████████░░░░░░░░░░░░░░░░ 30%
───────────────────────────────
总体 ██████████████████░░░░░ ~60%
```

## Ubuntu 部署 ✅
- API: `http://192.168.5.56:8000` (healthz=ok)
- 前端: `http://192.168.5.56:5173`
- PostgreSQL 16 + Redis 7 + Celery
- 缺 DeepSeek API Key
