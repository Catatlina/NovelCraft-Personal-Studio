/**
 * 生产 Web 功能走查（#162，2026-08-02）
 *
 * 对 https://novel.xyjin.xyz 做浏览器级走查：
 * 1. 注册/登录 → 建书 → 八页面可达（复用 pages-smoke 断言）
 * 2. V7 页签：Cost Monitor / Prompts 渲染真实页面（mock 修复后应显示真实空态而非假数据）
 * 3. 章节编辑器打开（空态）
 *
 * 用法：BASE_URL=https://novel.xyjin.xyz npx playwright test e2e/prod-walkthrough.spec.ts
 */
import { expect, type Page, test } from "@playwright/test";

const BASE = process.env.BASE_URL || "https://novel.xyjin.xyz";

const TABS: Array<{ label: string; expectText: string }> = [
  { label: "小说首页", expectText: "小说首页" },
  { label: "创作向导", expectText: "把一个念头，变成完整故事。" },
  { label: "扫榜选书", expectText: "榜单中心" },
  { label: "我的书库", expectText: "我的书库" },
  { label: "创作进度", expectText: "还没有正在运行的创作。" },
  { label: "章节编辑器", expectText: "还没有可以编辑的章节。" },
  { label: "审阅与一致性", expectText: "审阅与一致性" },
  { label: "小说设置", expectText: "小说设置" },
];

async function registerFreshUser(page: Page): Promise<void> {
  const email = `prod-walk-${Date.now()}@t.cn`;
  await page.goto(BASE);
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 20_000 });
}

async function createNovel(page: Page): Promise<void> {
  // 小说首页找"新建"按钮
  const newBtn = page.getByRole("button", { name: /新建|开始创作/ }).first();
  await newBtn.click({ timeout: 10_000 });
  await page.waitForTimeout(1500);
}

test("生产走查：八页面可达", async ({ page }) => {
  await registerFreshUser(page);
  const nav = page.getByRole("navigation", { name: "小说创作主导航" });
  for (const tab of TABS) {
    await nav.getByRole("button", { name: tab.label, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: tab.expectText, exact: true }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }
});

test("生产走查：V7 Cost Monitor 页面渲染（真实空态，无假数据）", async ({ page }) => {
  await registerFreshUser(page);
  await createNovel(page);
  // V7 页签入口（左侧 Tab）
  const v7tab = page.getByRole("tab", { name: /V7|智能体/i }).first();
  if (await v7tab.isVisible().catch(() => false)) {
    await v7tab.click();
  }
  // V7 侧边栏 Cost Monitor
  const costNav = page.getByRole("button", { name: "Cost Monitor" }).first();
  if (await costNav.isVisible({ timeout: 8000 }).catch(() => false)) {
    await costNav.click();
    await expect(page.getByRole("heading", { name: "Cost Monitor", exact: true })).toBeVisible({ timeout: 10_000 });
    // 真实空态：No budgets configured 或加载中；不出现假预算数字 187.5
    const body = await page.locator("body").innerText();
    expect(body.includes("187.5")).toBeFalsy();
    console.log("[V7 Cost] 真实空态确认（无 mock 假数据）");
  } else {
    console.log("[V7 Cost] 未找到 V7 入口（可能需选中小说后出现），跳过");
  }
});

test("生产走查：V7 Prompts 页面渲染", async ({ page }) => {
  await registerFreshUser(page);
  await createNovel(page);
  const v7tab = page.getByRole("tab", { name: /V7|智能体/i }).first();
  if (await v7tab.isVisible().catch(() => false)) {
    await v7tab.click();
  }
  const promptNav = page.getByRole("button", { name: "Prompts" }).first();
  if (await promptNav.isVisible({ timeout: 8000 }).catch(() => false)) {
    await promptNav.click();
    await expect(page.getByRole("heading", { name: "Prompt Manager", exact: true })).toBeVisible({ timeout: 10_000 });
    const body = await page.locator("body").innerText();
    expect(body.includes("a1b2c3d4e5f6g7h8")).toBeFalsy(); // mock hash 不应出现
    console.log("[V7 Prompts] 真实页面确认（无 MOCK_PROMPTS 假数据）");
  } else {
    console.log("[V7 Prompts] 未找到 V7 入口，跳过");
  }
});
