# NovelCraft Personal Studio — 项目进度

> 最后更新：2026-07-10
> 口径：按商业 SaaS 标准评估，非 Demo 标准。只有端到端验证通过的才算"完成"。

## 诚实进度

| 阶段 | 完成度 | 说明 |
|---|---|---|
| M1 地基+MVP | ~75% | +登录页 +创建项目 +Docker修复 +分页 +日志 |
| M2 小说引擎 | ~55% | 代码完整，缺 API Key 端到端验证 |
| M3 内容工作室 | ~25% | 后端骨架，热点是 LLM 幻觉 |
| M4 发布出海 | ~15% | 发布网关只写 DB |
| M5 协作多端 | ~15% | +PWA sw.js +移动端CSS +登出按钮 |

```
M1 ███████████████████████░░░ 75%
M2 █████████████████░░░░░░░░ 55%
M3 ████████░░░░░░░░░░░░░░░░ 25%
M4 ████░░░░░░░░░░░░░░░░░░░░ 15%
M5 █████░░░░░░░░░░░░░░░░░░░ 15%
───────────────────────────────
总体 ████████████░░░░░░░░░░░░ ~42%
```

## 已验证通过（有测试/手动验证）

- ✅ 健康检查 /healthz
- ✅ Auth：注册+登录+JWT（5/5 tests pass）
- ✅ 项目列表需要 token（test verified）
- ✅ 内容列表验证项目成员资格
- ✅ PostgreSQL 28 表 + Alembic 迁移
- ✅ 前端 10 tab 构建通过
- ✅ Prompt registry 加载（30 prompts）
- ✅ 日志系统配置
- ✅ 分页（contents 端点 limit/offset）

## 代码存在但未端到端验证（缺 API Key 或其他条件）

- ⚠️ Bootstrap 8 节点工作流（Celery task）
- ⚠️ 7 层上下文装配器（已修 novel_id 过滤）
- ⚠️ 实体追踪 / 伏笔系统
- ⚠️ 短篇生成（已修 NameError import）
- ⚠️ 连续章节生成
- ⚠️ 大纲展开
- ⚠️ Celery 重试机制
- ⚠️ SSE 事件流（已修连接关闭）
- ⚠️ 多模型路由（claude/openai/gemini 路径存在）

## 脚手架/占位（不可用于生产）

- ❌ 热点系统 — LLM 凭空编造热搜
- ❌ 每日晨报 — 同上
- ❌ 发布网关 — 只写 DB，无真实发布
- ❌ 出海翻译 — 未验证
- ❌ 自媒体 fan-out — 只插记录
- ❌ DAG 编辑器 — 纯展示，不保存/执行
- ❌ PWA — 只有 manifest.json
- ❌ 知识库检索 — ILIKE，无向量搜索

## 已修复的 Bug（本轮）

| 问题 | 状态 |
|---|---|
| P0-1 API Key 硬编码泄露 | ✅ 已删除默认值 |
| P0-2 鉴权后门（dev mode bypass） | ✅ 删除，强制要求 token |
| P0-3 权限逻辑写反（非成员放行） | ✅ 修复 |
| P0-4 AI 静默降级 mock | ✅ 生产抛错误 |
| P0-5 operation_logs 缺表 / joined_at 错列 | ✅ 补迁移+修正 |
| P0-6 row_to_dict NameError | ✅ 补 import |
| P0-7 Redis 地址硬编码 | ✅ 环境变量化 |
| P0-8 Celery retry 被吞 / SSE 假实现 | ✅ 修复 |
| P0-4 多模型路由不生效 | ✅ 添加 claude/openai/gemini |
| P1-1 跨小说数据泄漏 | ✅ novel_id 过滤 |
| P1 连接泄漏 x3 | ✅ 修复 |
| P1 缺失 prompt 种子 x2 | ✅ 补充 |
| P1 双转义 \\n | ✅ 修复 |
| P1 死代码 workflow.py | ✅ 删除 |
| P1 无分页 | ✅ 添加 |
| P1 无日志 | ✅ 添加 |
| P1 测试全灭 | ✅ 恢复 5/5 |
| P1 SQL 注入（versioned_repo）| ✅ 白名单 |
| P1 重复 admin 端点 | ✅ 删除 76 行 |
| P1 Docker REDIS_URL | ✅ 添加 |

## 仍需要做的事

- [ ] **轮换 DeepSeek API Key**（去控制台作废旧 Key）
- [ ] 用新 Key 做一次完整 Bootstrap 端到端验证
- [ ] Docker compose 全链路验证
- [ ] 前端登录页面
- [ ] CI/CD（GitHub Actions）
- [ ] 限流（slowapi）
- [ ] 连接池（替换裸 psycopg2 connect）
- [ ] 向量搜索实现
- [ ] 真实发布网关（从 1 个平台开始）
- [ ] 热点接入真实数据源
- [ ] 30 万字连载稳定性测试
