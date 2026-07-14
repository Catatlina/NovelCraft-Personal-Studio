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
  await page.getByPlaceholder("邮箱").fill(email);
  await page.getByPlaceholder("密码").fill("e2e-test-1234");
  await page.getByRole("button", { name: "注册", exact: false }).first().click();
  // 注册成功后进入应用外壳，默认落在扫榜中心
  await expect(page.getByRole("button", { name: "书库" })).toBeVisible({ timeout: 15_000 });
  return email;
}

async function importRankingCsv(page: Page) {
  await page.getByRole("button", { name: "扫榜中心" }).click();
  await page.getByLabel("选择榜单文件").setInputFiles(FIXTURE);
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
  await page.getByRole("button", { name: "扫榜中心" }).click();
  await expect(
    page.locator("table tbody tr").filter({ hasText: "manual" }).first()
  ).toContainText("成功", { timeout: 15_000 });

  // 新项目书库为空态，而非报错或崩溃
  await page.getByRole("button", { name: "书库" }).click();
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

  await page.getByRole("button", { name: "书库" }).click();
  const firstBook = page.locator(".book-row").first();
  await expect(firstBook).toBeVisible({ timeout: 10_000 });
  await firstBook.getByRole("button", { name: "查看详情" }).click({ force: true });
  await expect(page.getByRole("heading", { name: "简介" })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("heading", { name: "最新章节" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "全部章节" })).toBeVisible();
});

test("主链①c：平台连接可视化填写并保存（无 AI，确定性）", async ({ page }) => {
  await registerFreshUser(page);
  await page.getByRole("button", { name: "设置" }).click();
  await page.getByRole("button", { name: "平台连接" }).click();
  await page.getByRole("button", { name: "发布平台" }).click();
  await page.getByLabel("平台").selectOption({ label: "WordPress" });
  await page.getByLabel("账号/连接名").fill("e2e-blog");
  await page.getByLabel("站点 URL *").fill("https://example.com");
  await page.getByLabel("用户名 *").fill("admin");
  await page.getByLabel("应用密码 *").fill("app-password");
  await page.getByRole("button", { name: "保存连接" }).click();
  await expect(page.getByText("平台连接已保存")).toBeVisible({ timeout: 10_000 });
  await expect(page.locator("table").filter({ hasText: "WordPress" })).toContainText("已配置");
});

test("主链②：AI 分析→原创选题→建书入库（protected，真实 Provider）", async ({ page }) => {
  test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY（repo secret / 本地 env）");
  test.setTimeout(240_000);

  await registerFreshUser(page);
  await importRankingCsv(page);

  await page.getByRole("button", { name: "生成分析与选题" }).click();
  // 真实模型分析约 10-30s；候选出现在原创选题池
  const createButton = page
    .getByRole("button", { name: "创建作品并生成策划+首章" })
    .first();
  await expect(createButton).toBeVisible({ timeout: 90_000 });

  await createButton.click();
  // 建书先落库再派发；无论跳到生成进度还是书库，书都必须已在书库
  await page.getByRole("button", { name: "书库" }).click();
  await expect(page.locator(".book-row").first()).toBeVisible({ timeout: 30_000 });
});
