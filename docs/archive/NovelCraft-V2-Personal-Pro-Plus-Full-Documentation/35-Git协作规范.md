# Git 协作规范

## 分支策略

```
main ─────●──────────●──────────●────── (tag: v2.0.0-m1, v2.0.0-m2...)
           \        / \        /
develop ───●──●──●──●──●──●──●──●─────
            \  /    \  /
feature/xxx─●──●    feature/yyy─●──●
```

- **main**：生产就绪，只接受 develop 的合并
- **develop**：开发主线
- **feature/***：新功能分支（从 develop 切出，合并回 develop）
- **fix/***：Bug 修复
- **chore/***：工具/配置/文档

## Commit 规范

Conventional Commits：
```
feat(workflow): 支持 human 节点挂起 24h 后继续
fix(version): 修复版本恢复时 parent_id 丢失
docs(api): 补充 SSE 端点文档
chore(deps): 升级 FastAPI 到 0.115
test(gateway): 新增预算熔断单元测试
```

## PR 流程

1. 从 develop 切出 feature 分支
2. 开发 + 本地测试通过
3. 推送 + 创建 PR（带描述 + 截图/录屏）
4. CI 自动运行：lint + type-check + unit tests + golden cases
5. CI 全绿 + 人工 review 后合入
6. 合入后删除 feature 分支

## CI Pipeline

```yaml
# .github/workflows/ci.yml
jobs:
  lint:        # ruff + mypy + eslint
  type-check:  # tsc --noEmit + mypy --strict
  test:        # pytest (单元 + 集成) + golden cases
  build:       # docker build (确保镜像可构建)
  security:    # bandit + npm audit
```

## 文档纪律

- 代码 PR 与文档 PR 同评审
- 功能变更必须同步更新对应文档
- 禁止只有标题的空壳文档
- 架构决策必须写 ADR（见 18-架构决策记录 ADR）

## 发布流程

```bash
# 1. develop → main
git checkout main && git merge develop

# 2. 打 tag
git tag -a v2.0.0-m1 -m "M1 MVP: 灵感→第一章闭环"

# 3. 推送 tag
git push origin main --tags

# 4. 部署（自动或手动）
make deploy
```
