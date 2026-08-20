# Starlume AI Agent Operating Contract

This file is mandatory for every AI agent, coding agent, automation tool, and
human developer working in this repository.

Before changing code, reviewing progress, claiming completion, committing, or
pushing, you must read and follow:

1. `docs/AI_HANDOFF.md`
2. `docs/REQUIREMENTS_TRACEABILITY.md`
3. `docs/KNOWN_ISSUES.md`
4. `docs/Starlume-AI-开发文档/05-AI遵从与开发真实性规范.md`
5. `PROJECT_PROGRESS.md`
6. The active task document, currently `docs/Starlume-AI-开发文档/03-开发路径与里程碑.md`
7. The latest audit report provided by the user, if any

If work stops before the active objective is accepted, update
`docs/AI_HANDOFF.md`, `docs/REQUIREMENTS_TRACEABILITY.md`, and
`docs/KNOWN_ISSUES.md` with the exact Git state, executed gates, remaining
work, and blockers. Never leave the only copy of project state in chat history.

Mandatory gate:

```bash
bash scripts/ai_development_gate.sh
```

Rules that override any optimistic wording in other docs:

- Never claim "complete", "fully fused", "usable", "accepted", or "all done"
  unless the evidence gates in the Starlume AI document 05 are satisfied.
- Reuse the current editor, Gateway, V7 control plane, persistence and publishing
  path before adding a new module. Implement the smallest vertical slice that
  produces the requested user result; do not build the target architecture all
  at once.
- AI output is always a candidate until a human explicitly applies or confirms
  it. The canonical chapter body remains in `contents`.
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
