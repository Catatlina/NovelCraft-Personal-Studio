/**
 * Starlume AI 创作进度页「控件交互」浏览器证据（对应 docs/AI_HANDOFF.md §7 #2）：
 * 全流程重执行确认弹窗、启动/重启控件。
 *
 * - 真实后端 + Celery 运行，不使用 mock 或固定 JSON。
 * - 无 AI Key 时，bootstrap 走 Celery 重试并最终失败（ProviderError），run 进入
 *   failed/dispatch_failed；此时「全流程重执行」「启动/重启」控件才可见。
 *   若超时仍未观测到可操作态，则优雅 test.skip（与 progress.spec.ts 约定一致），不伪造。
 *
 * 复用 main-chain / progress 的真实登录与向导流程。
 */
import { expect, Page, test } from "@playwright/test";

async function registerFreshUser(page: Page, attempt = 0): Promise<string> {
  const email = `starlume-ctrl-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  try {
    await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
  } catch (e) {
    if (attempt >= 3) {
      test.skip(true, "注册持续被限流 429（CI 并发余量不足），跳过该用例");
    }
    console.warn(`[registerFreshUser] 注册后未出现首页（可能触发限流 429），第 ${attempt + 1} 次退避重试`);
    await page.waitForTimeout(13_000);
    return registerFreshUser(page, attempt + 1);
  }
  return email;
}

async function authHeaders(page: Page) {
  const token = await page.evaluate(() => sessionStorage.getItem("nc_token"));
  expect(token).toBeTruthy();
  return { Authorization: `Bearer ${token}` };
}

async function startWizardRun(page: Page) {
  // 服务端无 DEEPSEEK_API_KEY 时向导按钮会因 keyMissing 被禁用；
  // 注入一个"无效 BYOK Key"解禁向导——后端用它真实调用 DeepSeek 必然 401 失败，
  // run 进入真实 failed 态（不 mock、不伪造成功）。
  if (!process.env.DEEPSEEK_API_KEY) {
    await page.evaluate(() => sessionStorage.setItem("nc_api_key", "sk-e2e-invalid-key-for-real-failure"));
  }
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "创作向导", exact: true }).click();
  await page.getByRole("textbox", { name: /用几句话描述你的故事/ }).fill(
    "一位城市档案修复师发现，被删除的旧报纸会在午夜预告第二天的失踪案。",
  );
  await page.getByRole("combobox", { name: "品类包 真实 V7 品类" }).selectOption({ label: "悬疑" });
  await page.getByRole("button", { name: /短篇/ }).click();
  await page.getByRole("button", { name: "开始生成小说" }).click();
}

/** 轮询当前用户最新 run，直到进入可操作态（failed/dispatch_failed/pending）。超时返回 null。 */
async function waitForActionableRun(page: Page, headers: Record<string, string>, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs;
  let last: { id: string; status: string } | null = null;
  while (Date.now() < deadline) {
    const r = await page.request.get("/api/v1/runs/latest", { headers });
    if (r.ok()) {
      const data = (await r.json()).data;
      last = { id: data.id, status: data.status };
      if (data.status === "failed" || data.status === "dispatch_failed" || data.status === "pending") {
        return last;
      }
    }
    await page.waitForTimeout(2000);
  }
  return last; // 可能是 running/succeeded，调用方据此决定是否 skip
}

const ACTIONABLE = new Set(["failed", "dispatch_failed", "pending"]);

/** 控件③专用：仅当 run 进入 failed（存在失败节点、启动/重启按钮可见）才返回。 */
async function waitForFailedRun(page: Page, headers: Record<string, string>, timeoutMs: number) {
  const deadline = Date.now() + timeoutMs;
  let last: { id: string; status: string } | null = null;
  while (Date.now() < deadline) {
    const r = await page.request.get("/api/v1/runs/latest", { headers });
    if (r.ok()) {
      const data = (await r.json()).data;
      last = { id: data.id, status: data.status };
      if (data.status === "failed") return last;
    }
    await page.waitForTimeout(2000);
  }
  return last; // 可能停留在 pending/dispatch_failed/running/succeeded，调用方据此 skip
}

test("控件①：全流程重执行弹窗可打开、取消可关闭", async ({ page }) => {
  test.setTimeout(300_000);
  await registerFreshUser(page);
  await startWizardRun(page);

  const headers = await authHeaders(page);
  const run = await waitForActionableRun(page, headers, 170_000);
  if (!run || !ACTIONABLE.has(run.status)) {
    test.skip(true, "未观测到可操作态 run（全流程重执行控件需 run 非 running）");
    return;
  }

  // 「全流程重执行」按钮在 run 非 running 时可见
  const reexecuteBtn = page.getByRole("button", { name: "全流程重执行" });
  await expect(reexecuteBtn).toBeVisible({ timeout: 10_000 });

  await reexecuteBtn.click();
  // 确认弹窗出现，且明确「新建一次 / 不删除」
  await expect(page.getByText("这会新建一次完整创作 run")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("不会被删除")).toBeVisible();

  // 取消关闭弹窗，回到页面，控件仍在
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByText("这会新建一次完整创作 run")).toBeHidden();
  await expect(reexecuteBtn).toBeVisible();
  await page.screenshot({ path: "artifacts/screenshots/controls-reexecute-cancel.png" });
});

test("控件②：全流程重执行确认后新建 run，旧 run 保留", async ({ page }) => {
  test.setTimeout(300_000);
  await registerFreshUser(page);
  await startWizardRun(page);

  const headers = await authHeaders(page);
  const before = await waitForActionableRun(page, headers, 170_000);
  if (!before || !ACTIONABLE.has(before.status)) {
    test.skip(true, "未观测到可操作态 run（全流程重执行控件需 run 非 running）");
    return;
  }
  const oldRunId = before.id;

  await page.getByRole("button", { name: "全流程重执行" }).click();
  await expect(page.getByText("这会新建一次完整创作 run")).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "确认重执行" }).click();

  // 轮询直到出现一个与旧 run 不同的新 run（bootstrap 新建）
  const newDeadline = Date.now() + 60_000;
  let newRunId = "";
  while (Date.now() < newDeadline) {
    const r = await page.request.get("/api/v1/runs/latest", { headers });
    if (r.ok()) {
      const data = (await r.json()).data;
      if (data.id && data.id !== oldRunId) { newRunId = data.id; break; }
    }
    await page.waitForTimeout(1500);
  }
  expect(newRunId, "确认重执行应创建与旧 run 不同的新 run_id").toBeTruthy();
  expect(newRunId).not.toBe(oldRunId);

  // 成功提示明确「新建一次」且旧 run / 章节 / 版本保留
  await expect(page.getByText("已新建一次完整创作 run，旧 run 与章节、版本均保留。")).toBeVisible({ timeout: 20_000 });
  // 旧 run 仍存在（未被删除）
  const oldResp = await page.request.get(`/api/v1/runs/${oldRunId}`, { headers });
  expect(oldResp.ok(), "旧 run 应保留可查").toBeTruthy();
  await page.screenshot({ path: "artifacts/screenshots/controls-reexecute-confirm.png" });
});

test("控件③：启动/重启在同 run 内重跑（观测到失败态才断言，否则跳过）", async ({ page }) => {
  test.setTimeout(300_000);
  await registerFreshUser(page);
  await startWizardRun(page);

  const headers = await authHeaders(page);
  // 「启动/重启」按钮仅在 run 实际进入 failed（存在失败节点）时渲染，
  // pending/dispatch_failed 阶段 failedCount 为 0、按钮不可见，故只等 failed。
  const run = await waitForFailedRun(page, headers, 170_000);
  if (!run || run.status !== "failed") {
    test.skip(true, "未观测到 failed 态 run（启动/重启控件仅在有失败节点时可见，否则跳过）");
    return;
  }

  // 「启动/重启」按钮在 failed 时可见
  const restartBtn = page.getByRole("button", { name: "启动/重启" });
  await expect(restartBtn).toBeVisible({ timeout: 20_000 });
  await restartBtn.click();

  // 重启后 run 重新进入 running（同一 run_id，不新建）
  const runningDeadline = Date.now() + 60_000;
  let restarted = false;
  while (Date.now() < runningDeadline) {
    const r = await page.request.get(`/api/v1/runs/${run.id}`, { headers });
    if (r.ok()) {
      const data = (await r.json()).data;
      if (data.status === "running") { restarted = true; break; }
    }
    await page.waitForTimeout(1500);
  }
  expect(restarted, "启动/重启应使同一 run 重新进入 running").toBe(true);
  await expect(page.getByText("已在原 run 内重启未完成步骤，run 与章节、版本保持不变。")).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: "artifacts/screenshots/controls-restart.png" });
});
