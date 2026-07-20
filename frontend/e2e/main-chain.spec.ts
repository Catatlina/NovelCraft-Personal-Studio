/**
 * P0-2 主链 E2E（T4）：注册 → 扫榜中心导入榜单 → 快照落库 → 书库。
 * 用例 2（AI 分析→建书）需要 DEEPSEEK_API_KEY，无 key 自动跳过 —
 * 与 backend/tests/test_real_provider_t3.py 的 protected 语义一致。
 */
import { expect, Page, test } from "@playwright/test";
import { fileURLToPath } from "url";

const FIXTURE = fileURLToPath(new URL("./fixtures/ranking.csv", import.meta.url));

async function registerFreshUser(page: Page): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@nc.dev`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("输入密码").fill("e2e-test-1234");
  await page.getByRole("button", { name: "注册", exact: false }).first().click();
  // 注册成功后进入应用外壳，默认落在工作台
  await expect(page.getByRole("heading", { name: "NovelCraft Real Studio" })).toBeVisible({ timeout: 15_000 });
  return email;
}

async function clickNav(page: Page, label: string) {
  const alias: Record<string, string> = {
    灵感创作: "创作主链",
    扫榜选书: "扫榜书库",
    书库管理: "书库编辑",
    编辑器: "编辑审阅",
    设置: "配置运维",
    成本追踪: "配置运维",
    知识库: "知识协作",
    发布看板: "发布回流",
    热点追踪: "热点内容",
  };
  const navItem = page.locator(".sidebar .nav-item").filter({ hasText: alias[label] || label });
  await expect(navItem).toHaveCount(1, { timeout: 10_000 });
  await navItem.click();
}

async function importRankingCsv(page: Page) {
  await clickNav(page, "扫榜选书");
  await page.getByLabel(/选择榜单/).setInputFiles(FIXTURE);
  const importButton = page.getByRole("button", { name: "导入榜单" });
  await expect(importButton).toBeEnabled({ timeout: 10_000 });
  await importButton.click();
  // 快照表出现 manual 来源、成功、20 条
  const row = page.locator("table tbody tr").filter({ hasText: "manual" }).first();
  await expect(row).toContainText("成功", { timeout: 20_000 });
  await expect(row).toContainText("20");
  return row;
}

test("主链①：注册→导入榜单→快照落库→书库空态（无 AI，确定性）", async ({ page }) => {
  await registerFreshUser(page);
  await importRankingCsv(page);

  // 刷新后快照仍在（持久化，不是前端内存）
  await page.reload();
  await clickNav(page, "扫榜选书");
  await expect(
    page.locator("table tbody tr").filter({ hasText: "manual" }).first()
  ).toContainText("成功", { timeout: 15_000 });

  // 新项目书库为空态，而非报错或崩溃
  await clickNav(page, "书库管理");
  await expect(page.getByText("书库为空")).toBeVisible({ timeout: 10_000 });
});

test("主链①b：书库详情页可进入并展示核心区块（无 AI，确定性）", async ({ page }) => {
  await registerFreshUser(page);
  const token = await page.evaluate(() => sessionStorage.getItem("nc_token"));
  expect(token).toBeTruthy();
  const projects = await page.request.get("/api/v1/projects", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const projectId = (await projects.json()).data[0].id;
  await page.request.post(`/api/v1/projects/${projectId}/novels`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { idea: "书库详情页确定性验收", genre: "科幻", style: "克制", target_words: 10000 },
  });

  await clickNav(page, "书库管理");
  const firstBook = page.locator(".book-row").first();
  await expect(firstBook).toBeVisible({ timeout: 10_000 });
  await firstBook.getByRole("button", { name: "查看详情" }).click({ force: true });
  await expect(page.getByRole("heading", { name: "编辑审阅" })).toBeVisible({ timeout: 10_000 });
  await expect(page.locator("textarea").first()).toBeVisible();
});

test("主链①c：平台连接可视化填写并保存（无 AI，确定性）", async ({ page }) => {
  await registerFreshUser(page);
  await clickNav(page, "设置");
  await page.getByLabel("平台").selectOption({ label: "WordPress" });
  await page.getByLabel("账号/连接名").fill("e2e-blog");
  await page.getByLabel("站点 URL *").fill("https://example.com");
  await page.getByLabel("用户名 *").fill("admin");
  await page.getByLabel("应用密码 *").fill("app-password");
  await page.getByRole("button", { name: "保存连接" }).click();
  await expect(page.getByText("平台连接已保存").first()).toBeVisible({ timeout: 10_000 });
  await expect(page.locator("table").filter({ hasText: "WordPress" })).toContainText("已配置");
});

test("主链①d：成本追踪页无白屏并展示预算与模型路由（无 AI，确定性）", async ({ page }) => {
  await registerFreshUser(page);
  await clickNav(page, "成本追踪");
  await expect(page.getByRole("heading", { name: "预算" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: "模型路由" })).toBeVisible();
  await expect(page.locator("body")).not.toContainText("TypeError");
});

test("主链②：AI 分析→原创选题→建书入库（protected，真实 Provider）", async ({ page }) => {
  test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY（repo secret / 本地 env）");
  test.setTimeout(420_000);

  await registerFreshUser(page);
  await importRankingCsv(page);

  await page.getByRole("button", { name: "生成分析与选题" }).click();
  // 真实模型分析会串联十层分析 + 市场选题生成，网络波动时可能超过 90s。
  const createButton = page
    .getByRole("button", { name: "创建作品并生成策划+首章" })
    .first();
  await expect(createButton).toBeVisible({ timeout: 210_000 });

  await createButton.click();
  // 建书先落库再派发；无论跳到编辑页还是书库，书都必须已在书库
  await expect(page.getByRole("heading", { name: /编辑审阅|书库编辑/ })).toBeVisible({ timeout: 120_000 });
  await clickNav(page, "书库管理");
  await expect(page.locator(".book-row").first()).toBeVisible({ timeout: 30_000 });
});
