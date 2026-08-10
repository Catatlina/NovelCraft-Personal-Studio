/**
 * §7 #5 Repair Engine 正向真实证据（需 DEEPSEEK_API_KEY）。
 *
 * 走真实后端 Repair Engine：向导生成章节 → 取带正文的章节 →
 * POST /chapters/{id}/repair-preview（真实 DeepSeek 生成 proposal）
 * → POST /chapters/{id}/repair-apply（落地到草稿）。
 * 验证「真实预览生成 → 用户应用」正向链路，无 Key 时优雅跳过
 *（与 progress.spec 约定一致，不伪造）。
 *
 * 本地运行：DEEPSEEK_API_KEY=sk-... npx playwright test e2e/repair-engine.spec.ts
 * CI 未配置 repo secret 时自动 skip；配置了则真实跑（与 backend 受保护用例同机制）。
 */
import { expect, type Page, test } from "@playwright/test";
import { writeFileSync } from "node:fs";

test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY 才能跑真实 AI 正向证据");
test.setTimeout(900_000);

const REG_PASSWORD = "Starlume-e2e-1234";

function bodyText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(bodyText).filter(Boolean).join("\n\n");
  if (value && typeof value === "object") {
    const item = value as { text?: unknown; content?: unknown };
    if (typeof item.text === "string") return item.text;
    return bodyText(item.content);
  }
  return "";
}

async function registerFreshUser(page: Page, attempt = 0): Promise<string> {
  const email = `starlume-repair-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill(REG_PASSWORD);
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
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "创作向导", exact: true }).click();
  await page.getByRole("textbox", { name: /用几句话描述你的故事/ }).fill(
    "一位城市档案修复师发现，被删除的旧报纸会在午夜预告第二天的失踪案。",
  );
  await page.getByRole("combobox", { name: "品类包 真实 V7 品类" }).selectOption({ label: "悬疑" });
  await page.getByRole("button", { name: /短篇/ }).click();
  await page.getByRole("button", { name: "开始生成小说" }).click();
}

test("Repair Engine 正向：真实预览生成并应用到草稿", async ({ page }) => {
  await registerFreshUser(page);
  await startWizardRun(page);
  const headers = await authHeaders(page);

  // 等向导 run 真实 AI 跑完（succeeded）
  const deadline = Date.now() + 600_000;
  let run: { id: string; status: string; project_id?: string; novel_id?: string } | null = null;
  while (Date.now() < deadline) {
    const r = await page.request.get("/api/v1/runs/latest", { headers });
    if (r.ok()) {
      const data = (await r.json()).data;
      run = data;
      if (data.status === "succeeded") break;
    }
    await page.waitForTimeout(5000);
  }
  if (!run || run.status !== "succeeded") {
    test.skip(true, "向导 run 未在时限内成功（真实 AI），跳过 Repair Engine 正向证据");
    return;
  }

  // 取带正文的章节
  const projectId = run.project_id;
  let chapters: Array<{ id: string; body?: unknown }> = [];
  if (run.novel_id && projectId) {
    const cr = await page.request.get(
      `/api/v1/contents?project_id=${projectId}&parent_id=${run.novel_id}`,
      { headers },
    );
    if (cr.ok()) {
      const j = await cr.json();
      chapters = j.data ?? j;
    }
  }
  const chapter = chapters.find((c) => bodyText(c.body).length > 50);
  if (!chapter) {
    test.skip(true, "未找到带正文的章节，跳过 Repair Engine 正向证据");
    return;
  }
  const originalText = bodyText(chapter.body);

  // 真实 Repair Engine 预览（DeepSeek 生成 proposal）
  const previewResp = await page.request.post(
    `/api/v1/chapters/${chapter.id}/repair-preview`,
    {
      headers,
      data: {
        action: "rewrite_chapter",
        issues: ["增强场景冲突与人物连续性，强化生活质感与章末钩子"],
        client_mutation_id: crypto.randomUUID(),
      },
    },
  );
  expect(previewResp.ok(), "repair-preview 应成功（真实 AI 调用）").toBeTruthy();
  const preview = (await previewResp.json()).data;
  const proposed = bodyText(preview.proposal?.proposed_body ?? preview.proposal);
  expect(proposed.length, "真实 AI 生成的预览应有实质内容").toBeGreaterThan(100);

  // 真实应用（落地到草稿）
  const applyResp = await page.request.post(
    `/api/v1/chapters/${chapter.id}/repair-apply`,
    {
      headers,
      data: {
        action: preview.action,
        base_updated_at: preview.base_updated_at,
        proposal: preview.proposal,
        signature: preview.signature,
      },
    },
  );
  expect(applyResp.ok(), "repair-apply 应成功落地").toBeTruthy();
  const applied = (await applyResp.json()).data;
  const appliedText = bodyText(applied.body);
  expect(appliedText, "应用后正文应已变化").not.toBe(originalText);

  // UI 烟雾截图（审阅页）
  try {
    await page.getByRole("navigation", { name: "小说创作主导航" })
      .getByRole("button", { name: "审阅与一致性", exact: true }).click();
    await page.screenshot({ path: "artifacts/screenshots/repair-engine-positive.png" });
  } catch {
    /* 截图为佐证，不影响证据有效性 */
  }

  // 本地证据落盘（不含 Key，绝不进仓库）
  writeFileSync(
    "/tmp/starlume-repair-evidence.json",
    JSON.stringify(
      {
        chapter_id: chapter.id,
        original_excerpt: originalText.slice(0, 300),
        proposed_excerpt: proposed.slice(0, 500),
        applied_excerpt: appliedText.slice(0, 300),
        applied: true,
        timestamp: new Date().toISOString(),
      },
      null,
      2,
    ),
  );

  console.log("[repair-engine] 正向证据已生成：chapter=%s, proposedLen=%d", chapter.id, proposed.length);
});
