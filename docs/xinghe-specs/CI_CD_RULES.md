# 星禾AI工作台 · CI/CD规则

> 版本：V1.0 | 日期：2026-07-20 | 角色：DevOps工程师

---

## 一、分支策略

```
main          ← 生产分支（禁止直接提交）
  ↑
develop       ← 开发分支
  ↑
feature/xxx   ← 功能分支
fix/xxx       ← 修复分支
refactor/xxx  ← 重构分支
docs/xxx      ← 文档分支
```

---

## 二、CI流水线

### 触发条件

| 事件 | 触发 |
|------|------|
| PR → develop | 全量CI |
| PR → main | 全量CI + E2E |
| Push → develop | 快速CI（lint+test） |
| Push → main | 全量CI + E2E + 部署Staging |

### 流水线步骤

```
1. Checkout
2. Setup (Node/Python)
3. Install Dependencies
4. Lint & Format
   ├── Frontend: ESLint + Prettier + tsc
   └── Backend: ruff + black + mypy
5. Unit Tests
   ├── Frontend: vitest
   └── Backend: pytest (with PostgreSQL)
6. Security Scan
   ├── gitleaks
   ├── npm audit
   └── pip-audit
7. Build
   ├── Frontend: vite build
   └── Backend: Docker build
8. E2E Tests (PR → main only)
   └── Playwright
9. Deploy Staging (main only)
```

---

## 三、质量门禁

| 门禁 | 标准 | 不通过后果 |
|------|------|-----------|
| Lint | 0 Error | ❌ Block |
| TypeScript | `tsc --noEmit` 0 Error | ❌ Block |
| 单元测试 | 全部通过 | ❌ Block |
| 测试覆盖率 | 不下降 | ⚠️ Warning |
| Secret扫描 | 0 Finding | ❌ Block |
| 依赖审计 | 无Critical/High | ❌ Block |
| E2E | 核心链路通过 | ❌ Block |
| Build | 成功 | ❌ Block |

---

## 四、发布流程

```
开发 → 测试 → Staging → 灰度 → 生产

1. Develop分支
   └── Feature开发完成，PR审查通过

2. 合并到main
   └── CI全量通过

3. Staging部署
   └── 自动部署到Staging环境

4. 灰度发布（可选）
   └── Feature Flag控制
   └── 10% → 50% → 100%

5. 生产部署
   └── Docker Compose更新
   └── 数据库迁移（自动）
   └── 健康检查

6. 回滚方案
   └── Docker镜像版本回退
   └── 数据库迁移回滚（如可逆）
```

---

## 五、环境配置

| 环境 | 用途 | 数据库 | 自动部署 |
|------|------|--------|----------|
| **Development** | 本地开发 | 本地PG | ❌ |
| **Staging** | 预发布验证 | 独立PG，脱敏数据 | ✅ main合并后 |
| **Production** | 生产环境 | 生产PG | ✅ 手动触发 |

---

## 六、监控与告警

| 指标 | 工具 | 告警阈值 |
|------|------|----------|
| API响应时间 | — | P95 > 2s |
| 错误率 | — | > 1% |
| AI调用失败率 | — | > 5% |
| 数据库连接池 | — | > 80% |
| Worker队列深度 | — | > 100 |
| 磁盘使用率 | — | > 85% |

---

## 七、备份策略

| 备份 | 频率 | 保留 |
|------|------|------|
| 数据库 | 每日3:00 | 7天 |
| 文件 | 每日3:30 | 7天 |
| 配置 | 每次变更 | 永久 |
