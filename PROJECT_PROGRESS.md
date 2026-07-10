# NovelCraft Personal Studio — 项目进度

> 最后更新：2026-07-10
> 口径：按商业 SaaS 标准，只有端到端验证通过的才算"完成"。

## 诚实进度

| 阶段 | 完成度 | 核心交付 | 剩余 |
|---|---|---|---|
| M1 地基+MVP | ~88% | Auth+DB+Gateway+Celery+12组件+11tests+RateLimit+Pool | Tiptap编辑器, CI/CD |
| M2 小说引擎 | ~63% | 摘要+上下文+伏笔+auto-rewrite+lock+prompt版本 | 需API Key e2e验证 |
| M3 内容工作室 | ~30% | 短篇API+模板+自媒体+知识库+热点骨架 | 真实数据源, e2e测试 |
| M4 发布出海 | ~15% | 发布网关+敏感词+海外翻译骨架 | 真实平台adapter |
| M5 协作多端 | ~20% | 协作+登出+PWA sw+manifest+移动端CSS | 离线编辑, 冲突解决 |

```
M1 ██████████████████████████░ 88%
M2 ███████████████████░░░░░░ 63%
M3 █████████░░░░░░░░░░░░░░░ 30%
M4 ████░░░░░░░░░░░░░░░░░░░░ 15%
M5 ██████░░░░░░░░░░░░░░░░░░ 20%
───────────────────────────────
总体 ██████████████░░░░░░░░░ ~50%
```

## 已验证（11 tests pass）

- ✅ Auth register/login + JWT + 鉴权拒绝
- ✅ 项目创建 + 用户隔离
- ✅ 跨用户访问拒绝(403)
- ✅ 速率限制触发(429)
- ✅ PostgreSQL 28表 + Alembic + 连接池
- ✅ 前端12组件 + 10 Tab页面 + ErrorBoundary
- ✅ PWA manifest + sw.js + 注册
- ✅ 移动端响应式CSS
- ✅ 日志系统 + 结构化输出

## 代码存在但缺API Key端到端验证

- ⚠️ Bootstrap 8节点 Celery任务
- ⚠️ 7层上下文装配器 + novel_id隔离
- ⚠️ 伏笔/实体/时间线追踪
- ⚠️ 自动重写(≤2轮)
- ⚠️ 短篇生成(5模板)
- ⚠️ 连续章节(分布式锁)
- ⚠️ 大纲展开
- ⚠️ 多模型路由(deepseek/claude/openai/gemini)

## 脚手架(不可用于生产)

- ❌ 热点系统(LLM幻觉)
- ❌ 发布网关(只写DB)
- ❌ 出海翻译(未验证)
- ❌ DAG编辑器(需保存/执行)
- ❌ 知识库矢量搜索(table存在, 未实现)

## 下一步

1. **轮换DeepSeek API Key** + 配置环境变量
2. Bootstrap端到端验证
3. Docker compose全链路测试
4. Tiptap编辑器替换textarea
5. CI/CD (GitHub Actions)
6. 真实发布平台adapter(Medium先行)
