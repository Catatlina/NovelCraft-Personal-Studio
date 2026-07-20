# 星禾AI工作台 · 代码审查规范

> 版本：V1.0 | 日期：2026-07-20 | 角色：质量负责人

---

## 一、审查流程

```
PR提交 → CI自动检查 → AI审查 → 人工审查 → 修改 → 批准 → 合并
```

---

## 二、CI自动检查（必须通过）

| 检查项 | 工具 | 标准 |
|--------|------|------|
| 类型检查 | `tsc --noEmit` | 0 Error |
| 代码风格 | ESLint + Prettier | 0 Error |
| 后端风格 | ruff + black | 0 Error |
| 类型标注 | mypy | 0 Error |
| 单元测试 | vitest / pytest | 全部通过 |
| E2E测试 | Playwright | 核心链路通过 |
| Secret扫描 | gitleaks | 0 Finding |
| 依赖审计 | npm audit / pip-audit | 无严重漏洞 |

---

## 三、AI代码审查要点

### 前端审查

| 检查项 | 说明 |
|--------|------|
| 组件复用 | 是否有重复造轮子？检查 COMPONENT_SPEC.md |
| Design Token | 是否用了裸色值/裸字号？ |
| 状态覆盖 | loading/empty/error/success 四态是否齐全？ |
| 性能 | 是否有不必要的re-render？useMemo/useCallback使用 |
| 可访问性 | 焦点环、ARIA、键盘导航 |
| 错误边界 | 异常是否有ErrorBoundary包裹？ |

### 后端审查

| 检查项 | 说明 |
|--------|------|
| AI调用 | 是否经过AI Engine？不直接调Provider |
| 权限 | 是否通过authz.py鉴权？ |
| 异常处理 | 是否有全局异常处理？不静默吞错误 |
| SQL | 是否参数化查询？无SQL注入风险 |
| 迁移 | 数据库变更是否有Alembic迁移？ |
| 性能 | 是否有N+1查询？是否需要索引？ |

---

## 四、审查标准

| 级别 | 说明 | 处理 |
|------|------|------|
| **Blocker** | 安全问题、破坏兼容、假功能 | 必须修复才能合并 |
| **Major** | 架构问题、性能严重问题 | 建议修复 |
| **Minor** | 代码风格、命名不规范 | 建议优化 |
| **Info** | 建议性意见 | 可选采纳 |

---

## 五、PR规范

### PR标题

```
<type>(<scope>): <description>

类型：
feat: 新功能
fix: 修复
refactor: 重构
docs: 文档
test: 测试
style: 样式
chore: 杂项

范围：
novel, engine, ui, api, db, security, agent, skill

示例：
feat(novel): 新增爆款标题Skill
fix(engine): 修复SSE流式断连重试问题
refactor(ui): 全组件对齐Design Token
```

### PR描述模板

```markdown
## 变更说明
- 简述做了什么

## 影响分析
- 涉及模块
- 数据影响
- API影响

## 测试
- [ ] 单元测试通过
- [ ] E2E测试通过
- [ ] 手动验证

## 截图
- 暗色模式 / 亮色模式（如涉及UI）

## 关联文档
- 关联的Issue/文档
```

---

## 六、禁止事项

| ❌ 禁止 | 说明 |
|--------|------|
| AI直接提交main | 必须走PR流程 |
| 跳过CI检查 | CI失败不允许合并 |
| Review未通过就合并 | 必须至少1人Approve |
| 大PR（>500行） | 拆分为小PR |
| PR无描述 | 必须写变更说明和影响分析 |
