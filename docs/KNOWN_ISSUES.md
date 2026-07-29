# Starlume AI 当前已知问题

> 更新时间：2026-07-29。按阻断程度排序；解决后必须保留验证证据并从本表移除或标注历史。

## 阻断生产验收

### KI-001 新 UI 真实 AI 全链 -- ✅ 已验收(2026-07-28)

- 状态:**已验收**(本地真实 Key 全链通过 + 生产已部署,KI-002 收口完成)。
- 解决过程(2026-07-28,注入真实 `DEEPSEEK_API_KEY` 后连续定位并修复 3 个真实阻断):
  1. **Wizard 表单校验 bug**:`Wizard.tsx` 字数输入 `min={5000} step={10000}` 与全部预设值(100000/300000/...)不满足 HTML5 step 约束 → 浏览器静默拒绝提交,工作流从未启动。修复为 `min={10000}` 且 JS 校验同步 `targetWords < 10000`。
  2. **E2E 编排缺 Celery worker**:`scripts/e2e-backend.sh` 只起 uvicorn,`execute_bootstrap` 入队后无消费者。修复为 worker(concurrency=2)+uvicorn 双进程并带退出清理。
  3. **dev 库迁移落后**:`novelcraft_dev` 停在 `nc_versions_reason_text`,`ai_calls` 缺 `user_id` 列 → 网关预算断言 `UndefinedColumn`,节点重试 4 次后 run failed。执行 `alembic upgrade head`(补 6 个迁移至 `f932f2b0b3bb`)。
- 通过证据(全部真实,无 mock):
  - E2E:`npx playwright test e2e/main-chain.spec.ts --grep "protected"` → **1 passed (13.2m)**。
  - Celery 日志:`execute_bootstrap` 两段任务分别 254.4s(→ `waiting_human`,人工定名断点真实出现)与 527.7s(→ `succeeded`)。
  - run ID:`8f1fd62b-5ad8-4208-8fd8-887f33425631`,status=succeeded。
  - `ai_calls`:本次 run 窗口 **19 条**真实 DeepSeek 调用,合计 ¥0.1889(重节点实测 write_polish 95.6s / write_length_check 94.9s)。
  - 产物:小说《午夜头条》+ 第一章「午夜浮现」(body 2350 chars),由测试在真实候选书名中点选定名。
  - 截图:`frontend/artifacts/screenshots/protected-02..06.png`(人工定名/完成/书库/编辑器/审阅,5 张)。
- 保留约束:`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除;无 Key 环境仍真实跳过,CI 门禁不受影响。

### KI-002 历史新 UI 版本已部署生产 -- 已验收(2026-07-28)

- 状态:**已验收**。
- 部署过程(2026-07-28):
  1. 只读扫描 43.156.17.78:确认拓扑为 nginx 443→docker frontend:8090, Compose 项目在 `/opt/NovelCraft-Personal-Studio/`,运行旧 commit `bf1a377`;无 schema 迁移;`.env` 含全部密钥。
  2. 处理分叉:`origin/main` 已含另一工作副本推送的 E2E 修复;本副本仅把文档提交 rebase 到 `origin/main` 后首次部署至 `f2e2bde`。
  3. 全量重建并启动 api/worker/beat/migrate/frontend,healthz 返回 `ai_key_configured:true`、`worker:ok: 1 online`、DB/redis ok。
- 生产验证:`https://novel.xyjin.xyz/` → 200;`/api/v1/healthz` 全绿;部署 commit 随后续修复推进到 `91bcf9b`。
- 关联收口:KI-001/KI-003 由"可用"提升为**已验收**。
- 边界：该证据只覆盖部署到 `91bcf9b` 的历史版本，不覆盖当前 `main @ f8e343c` 或 2026-07-29 修复批次；当前版本部署见 KI-009。

### KI-003 AI 编辑与版本恢复真实浏览器闭环 -- ✅ 已验收(2026-07-28)

- 状态:**已验收**(真实 `DEEPSEEK_API_KEY` 下 E2E 全链通过 + 生产已部署,KI-002 收口完成)。
- 修复(2026-07-28):E2E 选中错误版本导致恢复后正文变空。根因为测试用脆弱的 `nth(index)` 点击,在版本历史 UI 列表尚未刷新时点到 `body={}` 的 `offline_save` 版本;应用恢复逻辑本身正确(`restore_version` 写回目标快照 body)。修复:恢复按钮加 `data-version-id={v.id}`(`frontend/src/components/Editor.tsx`),测试按真实版本 id 点击并 `waitFor` 按钮可见。
- 通过证据(全部真实,无 mock):
  - E2E:`npx playwright test e2e/main-chain.spec.ts --grep "小说主线6"` → **1 passed (29.2s)**。
  - 真实 AI:run9 两次 `editor.continue` 真实 DeepSeek 调用(deepseek-v4-pro,succeeded,含 prompt/completion tokens 与成本)。
  - 闭环:续写→预览可见且正文不变→放弃后原文不变→再次续写→应用到草稿正文含 AI 建议→按版本 id 恢复后原文 A 回归、AI 建议消失。
  - 截图:`frontend/artifacts/screenshots/protected-07..09.png`(AI 预览 / 应用后 / 版本恢复后)。
  - 取证:`restore->content.body` 恢复后确为 `{content:[{text:"档案室..."}]}`,编辑器 DOM `<p>档案室...</p>`。
- 保留约束:`test.skip(!process.env.DEEPSEEK_API_KEY)` 未删除;无 Key 环境仍真实跳过。

## 文档和门禁问题

### KI-004 README 仍描述旧产品入口 —— ✅ 已修复（2026-07-28）

- README 已更新为描述当前八项小说页面入口（含扫榜选书），与代码一致。

### KI-005 真实性门禁存在宽泛告警

- `bash scripts/ai_development_gate.sh` 的 AST 真实性与 whitespace 已通过。
- suspicion scan 会命中测试 mock、输入 placeholder、历史非小说 fallback 字段和自然空集合,默认返回 3。
- 必须逐条阅读输出;只有确认不是生产假实现后,才可按规范用
  `GATE_ALLOW_WARNINGS=1` 复验并记录解释。
- 允许告警不等于修复告警,也不能据此宣称全项目完成。
- 接手逐条解释(2026-07-28,全部非业务伪实现):脚本三类扫描命中均属《23》§10 允许的良性命中--
  1. **mock/fallback/placeholder/deprecated/空返回** 命中约 120 行,均为以下之一:测试代码 `vi.fn().mock*`/`vi.stubGlobal('fetch',...)`(api.test.ts、ThemeProvider.test.tsx、Progress.test.tsx、WorkspaceDashboard.test.tsx)--单元测试对网络/timer 的 monkeypatch,符合《23》§10 规则 1,非产品 mock provider;前端 `placeholder=` HTML 属性(LoginPage/Wizard/Settings/BookLibrary 等输入框)--UI 占位符,非生成结果;反伪实现注释(`never fake success`、`暂无数据 placeholder`、`report real numbers instead of 0/0 placeholder`)--显式拒绝伪造;合法空态 `return []`/`return {}`(db.py、各 service 无数据分支、circuit_breaker、hotspot 采集失败态)--有错误语义/空态文案,非静默成功;`hotspot_collector.py` 的 `fallback_url`--平台官网兜底链接(用户手动访问),非 AI 生成兜底,采集失败仍按源返回状态/502;`gateway.py`/`config.py` 的 `fallback_json`--仅为 model_routes 表列名,`config.py` 已 `max_length=0` 禁止业务 fallback,网关注释明确 "No mock or fallback generation";`ranking_adapter.py:197` `return [("261","都市日常","1")]  # fallback`--历史非小说榜单解析兜底默认分类,不在小说产品路径,保留但不得计入小说主线完成;`core/security.py:25` `JWT_SECRET="dev-secret-change-in-production"`--开发默认密钥,仅当未设环境变量时生效,E2E/生产必须用 ≥32 字节密钥(E2E 已用 32 字节 secret);`platform/modules/manager.py:96` `# TODO: clone repo...`--插件市场未接入口,非完成声明。
  2. **固定模板/伪造输出措辞** 仅 `gateway.py:791`、`config.py:24` 两条注释,说明已移除硬编码预算常量,非生成模板。
  3. **硬编码 active/wired 自报告** 仅 `api/v1/billing.py:82` `UPDATE ... status='active'`--订阅付费成功后的真实状态写库,由真实支付/更新驱动,非能力自报告。
  - 结论:全部命中为非业务伪实现;按《23》§10 用 `GATE_ALLOW_WARNINGS=1` 复验仅表示"已确认良性",不等于修复告警,也不能据此外推全项目完成。

### KI-006 全页面视觉证据 -- 可用(2026-07-29)

- 状态：**可用**（`visual.spec.ts` 已包含八页面，但历史截图证据仍是七页面口径；本批已把用例名改为八页面，待显式开启截图门禁并检查新产物。富状态全链 `write_polish` 修复待真实 Provider 重跑，见 KI-007）。
- 证据:
  - `STARLUME_CAPTURE_VISUAL=1 npx playwright test --grep "七页面"` → **passed (9.1s)**，生成 15 张截图（七页面 1280/390 + 404）。注意：此截图集不含扫榜选书页面，需更新 visual.spec.ts 并重跑。
  - `npx playwright test --grep-invert "小说主线5"` → **6 passed, 1 skipped**;含 3-progress `protected-01-progress-running.png`(真实运行中节点)+ 6 版本恢复闭环 `protected-07/08/09.png`。
  - 小说主线5(人工定名→完成→书库→编辑器→审阅富状态)连续两次因 `write_polish` 节点返回 `invalid_output` 失败,已停止重试;该问题已单独记录为 KI-007。

## 新发现的线上/生产稳定性问题

### KI-007 `write_polish` 节点对 `deepseek-chat` 输出格式与保真不稳定

- 状态：**可用**（真实 Provider 本地全链已通过；尚未部署生产）。
- 现象:真实 AI 全链 E2E(小说主线5)连续两次在 `write_polish` 节点返回 `invalid_output`,导致 run failed;切换模型前旧链路上也曾出现相同问题。
- 根因(已校正):失败发生在 `gateway.validate_task_output` 的 Pydantic 契约校验(`_WritePolishOutput` 要求 `polished.body: list[str]` 且 `changes_summary: str`),而非 `_persist_chapter_polish`。`deepseek-chat` 在此节点返回了**结构松散但内容有效**的载荷:裸 `body`(无 `polished` 包裹)、`body` 为字符串而非段落列表、或缺失 `changes_summary`。重试循环只是对同一种漂移重新采样 3 次后放弃。
- 修复(commit 见下方部署记录):在 `gateway.validate_task_output` 前增加 `_normalize_bootstrap_output` 输出修复层(V3 Repair Engine 思路):
  1. 无 `polished` 包裹时,从裸 `body` / `chapter.body` / `text` 自动包装;
  2. `body` 为字符串时按换行 + 分句兜底切分为段落列表;`body` 为 dict 列表时抽取 `text`;
  3. 缺失 `changes_summary` 时由 `changes` 列表派生或填空;
  4. `_split_into_paragraphs` 对单块长文本按句分组,保证段落数门槛不误伤真实长文。
  修复后契约不被削弱--真正空 / 非叙事输出仍会被下游闸门拒绝。
- 证据:
  - `tests/test_write_polish_repair.py` **8 passed**(canonical / 裸 body / 字符串 body / 单块长文 / 缺 changes_summary / changes 列表 / dict 列表 / 空输出仍拒)。
- 追加真实根因与修复：
  1. `generate_story_arc` 的提示输出契约使用 `arc_name/arc_type`，与 Gateway 的 `name/goal/...` schema 冲突，已统一；
  2. `chapter_text` 未列入长上下文字段，真实润色提示只收到约 1500 字符，已提高到 12000；
  3. 润色改为最多 3 次真实质量采样并回传明确段落/字数差距；内容保留不足 75% 时禁止继续；
  4. 仅当文本保留至少 75% 且段落不足 60% 时，允许按句末标点做不改字的确定性重新分段；
  5. Bootstrap 首章装配器此前把字符串当字典并静默吞错，现已真实注入装配文本，缺创意/创作圣经/当前章细纲直接失败。
- 真实证据：protected “小说主线⑤” **1 passed (3.3m)**；run `a416b8a8-2bcb-4ad1-8f3d-d50c0956ba4d` 为 20/20 succeeded、20 条真实 succeeded `ai_calls`，最终正文 35 段/4581 非空白字符；首章初稿请求记录含 1451 字符装配上下文。
- 下一步:
  1. 提交 `391ef3b` / Actions `30443223990` 已全绿。
  2. 最终生产部署后重跑小说主线⑤ smoke，再提升为已验收。

### KI-008 `f8e343c` 的 GitHub Actions 后端失败（历史，已解决）

- 状态：**已验收**。
- 失败 run：`30425548279`，commit `f8e343c`；backend 为 `10 failed, 750 passed, 9 skipped, 1 xpassed`，其余 frontend、frontend-test、e2e、security 通过。
- 根因与修复：
  1. 新增 `generate_story_arc` 后，19 节点断言与完整流程 Provider 夹具未更新；
  2. 同步调度测试未接受新的 `api_key_ref`；
  3. 质量证据无条件声称 pacing/story-arc 来源，现改为只记录实际采样来源；
  4. Costs/预算 UI 已按小说优先退役，但两条静态源码测试仍要求恢复旧入口；
  5. `PROJECT_PROGRESS.md` 的历史措辞触发交付声明校验。
- 本地证据：后端 `761 passed, 9 skipped, 1 xpassed`；前端 `12 passed`；构建通过；E2E `4 passed, 4 skipped`；交付声明、AI 真实性、前后端契约、`git diff --check` 通过。
- CI 证据：修复提交 `07a8c0f` 的 Actions run `30439322188` 五项全绿（backend、e2e、frontend、frontend-test、security）。

### KI-009 当前 V3 代码尚未部署生产

- 状态：**已接线**。
- 本轮接手远端基线为 `f8e343c`；文档可确认的生产 commit 仍为 `91bcf9b`，当前最新提交以实时 Git 为准。
- 升级门禁：CI 同版本全绿后按部署手册发布，并完成 healthz、登录、八页面、切书、建书/保存、V3 真实 AI 20 节点主链 smoke。

### KI-010 V3 12 项存在“代码已建但产品闭环不完整”

- 状态：**已接线**。
- 已经通过真实调用复核的项：Chapter Function、Novel DNA、Story Arc、策略库/Prompt Compiler、人物认知分层、时间线锚点、读者体验、Pacing、Author Style Card、Scene Director。详细 run、调用和持久化证据见 `AI_HANDOFF.md` 1.4 与 `V3-FUSION-TRACEABILITY.md`。
- 同提交门禁：`5c544ff` / Actions `30445384633` 五项全绿。
- 本轮修复的伪接线：
  1. Prompt Compiler 已导入却无产品调用者，现进入 Writer 真实请求；
  2. Bootstrap 最终一致性未产出读者体验，现改为必填并持久化；
  3. Author Style 信号和卡片写入均未提交事务，且保存后不触发 Learning Agent，现已修复；
  4. Scene Director 场景写入未提交事务，前端轮询使用旧闭包状态，现已修复；
  5. 人物提取提示未要求 `known_info`，五层认知全空；现增加强契约，并修复 `get_states` 跨书查询。
- 产品入口已补：三档修复统一执行“签名预览 → 用户确认应用”，并具备旧预览冲突与防篡改门禁；本地 781 后端测试、14 前端测试、构建和确定性 E2E 通过。
- Repair 产品接线提交 `6f7184c` / Actions `30447533339` 五项全绿。
- 仍未闭环：当前环境未配置 Provider 密钥，真实 AI 正向预览/应用场景尚未复验。因此 Repair Engine 与 V3 12 项整体仍只能标记为已接线。

### KI-011 多书选择回弹、内容不刷新与跨账号缓存污染

- 状态：**可用**。
- 根因：`projects` / `currentNovel` 使用全局离线缓存键；run 恢复异步响应可覆盖人工选择；人工选择后章节加载 effect 被永久禁用；快速切换没有请求代次校验；Layout 的本地选择值未随真实 `currentNovelId` 同步。
- 修复：缓存按登录账号隔离；登录/退出清理工作区；选择 epoch 使旧详情/run/章节响应失效；选书后重新加载章节；Layout 同步受控值。
- 产品范围：选择器只在进度、编辑器、审阅三个公共页出现。
- 本地证据：前端 `14 passed`、构建通过；新增真库 Playwright 竞态用例通过；完整确定性 E2E `5 passed, 4 skipped`。E2E 后端启动前会升级 Alembic，旧库缺 `scenes` 表不再被静默容错。
- 升级门禁：本批同提交 CI 全绿、生产切书 smoke 后提升为已验收。

## 非本轮目标但必须如实保留

- 百章真实 Provider 长跑尚未验收。
- 真实内容平台发布回执尚未验收。
- 外部热点源七天连续稳定性尚未验收。
- 这些模块目前从小说 UI 隐藏,不得因"看不见"就删除历史数据或把它们写成已完成。
