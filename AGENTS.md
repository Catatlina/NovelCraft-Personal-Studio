# NovelCraft Agent Operating Contract

This file is mandatory for every AI agent, coding agent, automation tool, and
human developer working in this repository.

Before changing code, reviewing progress, claiming completion, committing, or
pushing, you must read and follow:

1. `docs/NovelCraft-开发文档/23-AI开发边界与交付真实性规范.md`
2. `PROJECT_PROGRESS.md`
3. The active task document, currently `docs/NovelCraft-开发文档/37-新增需求任务分解-20260713.md`
4. The latest audit report provided by the user, if any

Mandatory gate:

```bash
bash scripts/ai_development_gate.sh
```

Rules that override any optimistic wording in other docs:

- Never claim "complete", "fully fused", "usable", "accepted", or "all done"
  unless the evidence gates in document 23 are satisfied.
- Code existence, route existence, import success, a skeleton function, or a
  deprecated module is not completion.
- AI features must use a real provider path and must not return mock, fallback,
  static-template, heuristic, or degraded-success results.
- External-account/platform/API features are only "configuration ready" until
  valid credentials and real platform receipts prove them.
- Monkeypatched tests may verify protocol, rollback, permissions, and failure
  paths, but cannot prove real AI capability completion.
- Fusion status must be evidence-driven. Deprecated modules, upstream files,
  or helpers with no active product caller must not be reported as integrated.
- If a required gate cannot be run, say exactly which gate was not run and why;
  downgrade the claim.

Required final report format:

```text
已完成：
- 功能：
- 文件：
- 验证命令：
- 验证结果：
- 证据等级：

未完成：
- 项目：
- 原因：
- 阻断条件：
- 下一步：

不能宣称完成的项：
- 项目：
- 原因：
- 当前只能标记为：
```

