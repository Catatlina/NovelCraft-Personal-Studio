# NovelCraft Personal Studio — 进度

> 2026-07-11 core-hardening + offline sync · 101 tests · 21 components · 10 Celery tasks

```
M1 ███████████████████████████ 97% ✅ v2.0.0-m1
M2 ██████████████████████████ 95% ✅ v2.0.0-m2
M3 █████████████████████████ 82% ✅ v2.0.0-m3
M4 █████████████████████░░░░ 75% ✅ v2.0.0-m4
M5 ███████████████████░░░░░░ 75% ✅ v2.0.0-m5
───────────────────────────────
总体 ██████████████████████████ 86%
```

| ✅ 达标 | ⚠️ 部分 | ❌ 硬阻 |
|---|---|---|
| 32 | 16 | 3 |

剩余外部验收项：TASK-004 迁移工具已完成 dry-run 与回滚验证，仍需提供真实 V1 数据库执行生产迁移。

## 2026-07-11 核心加固

- refresh token 改为 HttpOnly Cookie，加入 CSRF、JTI、Redis 吊销和一次一用轮换；
- access/refresh 加入 `token_version`，禁用用户或版本变更后拒绝旧令牌；
- 前端加入 401 单飞刷新与请求重放；
- 章节字数统一为去空白字符统计；新增 1–50 章批次、持久进度与协作式取消；
- Knowledge Hub 加入可重复构建的 1536 维本地向量、HNSW 索引和重建去重；
- Flower 仅绑定本机并强制 Basic Auth；生产环境强制安全 Cookie 与 JWT Secret；
- 验证：后端 94 项测试、前端生产构建、Docker Compose 配置检查。

## 2026-07-11 Offline L2/L3

- IndexedDB outbox 按创建顺序重放内容保存和 AI 操作，不存储 API Key/JWT；
- 内容保存携带 `base_updated_at` 与 `client_mutation_id`，服务端乐观锁冲突生成版本树分支；
- 编辑器提供本地稿/服务器稿/合并稿三方对比，冲突解决后保留完整版本历史；
- AI outbox 使用数据库唯一幂等键，网络抖动重放直接返回已生成结果，不重复调用和计费；
- 无法安全自动替换的 AI 结果保留在编辑器侧队列，由用户点击应用；
- V1→V2 迁移重构为幂等迁移，补 owner membership、稳定版本 ID、源表预检、dry-run 全事务回滚和结果报告；
- 验证：后端 97 项测试、迁移 migration 往返、临时 V1 数据库 dry-run 且 V2 写入为 0。

## 2026-07-11 M3/M4 验收补强

- Knowledge 导入强制项目 Editor 权限、20 MB/300 页/200 万字符上限，支持 TXT/Markdown/JSON/JSONL/PDF/DOCX，并自动切片向量化；
- 登录失败按账号哈希计数，5 次失败锁定 15 分钟，成功登录清零并支持 Telegram 告警；
- 补齐 `publish_records` 实际被代码使用的 result/meta/updated_at 字段与调度索引；
- 定时发布列表、ROI 成本和内容统计全部按项目成员隔离；
- 禁止无 API 平台强行 auto 模式，Worker 再次执行内容安全检查，WordPress 发布目标限制为公网 HTTPS；
- 验证：后端 101 项测试，新增 Knowledge 权限/解析、登录锁定、发布隔离与 SSRF 回归。
