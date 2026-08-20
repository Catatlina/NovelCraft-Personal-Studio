# AI 额度耗尽时的连续接手机制

## 目标

把项目状态放进 Git，而不是放在某个 AI 的聊天记忆里。任何 AI 只要拿到仓库，就能恢复“目标、当前状态、证据、未完成项和下一步”。

## 每个工作批次的强制闭环

1. 开始前读取 `AGENTS.md` 和交接五件套。
2. 开始前记录 `git status`、分支和最近提交。
3. 一次只做一个可验收批次。
4. 修改后运行与风险相称的测试。
5. 更新：
   - `docs/AI_HANDOFF.md`
   - `docs/REQUIREMENTS_TRACEABILITY.md`
   - `docs/KNOWN_ISSUES.md`
6. 创建小而准确、可回滚的 Git 提交。
7. 推送远端；不要让唯一 checkpoint 留在本机。
8. 未完成时必须写“下一条可执行命令”和阻断条件。

## 建议的额度预警规则

- 剩余约 30%：停止扩张范围，完成当前小批次测试。
- 剩余约 20%：更新交接文档和需求矩阵。
- 剩余约 10%：只做 checkpoint、推送和状态汇报，不再开启重构。
- 工具即将中断：至少保存 `git diff`，不要清理或回滚未完成改动。

## 给下一位 AI 的直接指令

```text
你正在接手 Starlume AI 的未完成开发。

唯一工作目录：
/Users/genius/Documents/Codex/2026-07-23/https-github-com-tradecatlabs-vibe-coding/work/NovelCraft-Personal-Studio

第一阶段只恢复真实状态，不重写项目：
1. 完整读取 AGENTS.md、docs/AI_HANDOFF.md、
   docs/REQUIREMENTS_TRACEABILITY.md、docs/KNOWN_ISSUES.md、
   docs/ACCEPTANCE_CRITERIA.md、docs/AI_CONTINUITY.md、
   docs/Starlume-AI-开发文档/README.md、
   docs/Starlume-AI-开发文档/03-开发路径与里程碑.md、
   docs/Starlume-AI-开发文档/05-AI遵从与开发真实性规范.md、
   PROJECT_PROGRESS.md。
2. 执行 git status、git branch --show-current、
   git log --oneline --decorate -12、git diff --check。
3. 复跑交接文档中的单元、构建和 E2E 门禁。
4. 对照需求矩阵和已知问题，先确认文档与代码一致。
5. 从 AI_HANDOFF.md “当前未完成顺序”的第一项继续。

开发规则：
- 使用 Vibe Coding 的任务契约、分批实现、证据门禁逻辑。
- 优先复用现有编辑器、Gateway、V7、持久化和发布准备能力；只做当前闭环所需的最小新增。
- 不制作新 Demo，不恢复非小说入口，不删除旧数据。
- 不使用 Mock、固定 JSON、定时器或 Toast 冒充成功。
- AI 失败必须失败；AI 编辑必须预览后由用户应用。
- 每个批次独立测试、更新交接文档、提交并推送。
- 状态只使用：未开始、已接线、可用、已验收。
- 最终按 AGENTS.md 的“已完成 / 未完成 / 不能宣称完成的项”汇报。
```

## 跨工具落地

- Claude Code / Gemini CLI / OpenCode：在仓库根目录启动，直接粘贴上面的接手指令。
- Cursor / Windsurf：把上面的指令加入项目规则，同时仍以 `AGENTS.md` 为最高项目入口。
- 网页版模型：必须连接完整 GitHub 仓库；只上传几个文件无法安全接手。
- 所有工具：不得把真实密钥写入提示词或文档，只通过本地 `.env`、CI Secret 或部署环境注入。

## 为什么这比聊天交接可靠

- Git 提交能精确区分每位 AI 的改动并支持回滚。
- 需求矩阵防止“读过需求但遗漏实现”。
- 已知问题表防止把跳过项或失败项包装成完成。
- 验收标准防止只看页面、HTTP 200 或单测就误判。
- `AGENTS.md` 强制所有后续代理先读交接状态，并在中断前把状态写回仓库。
