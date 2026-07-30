/**
 * §7 #4 完整浏览器验收：八页面可达性烟雾测试（KI-006）。
 *
 * 遍历左侧主导航全部八个入口，断言每个页面都渲染了真实的标题/空状态，
 * 而非白屏或崩溃。空态文案与 nav 标签不同，断言使用页面真实 h1/h2/空态文本。
 * 无需 Provider Key，CI 确定性通过。
 */
import { expect, type Page, test } from "@playwright/test";

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
  const email = `starlume-pages-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
}

for (const tab of TABS) {
  test(`八页面可达性：${tab.label}`, async ({ page }) => {
    await registerFreshUser(page);
    const nav = page.getByRole("navigation", { name: "小说创作主导航" });
    await nav.getByRole("button", { name: tab.label, exact: true }).click();
    await expect(page.getByText(tab.expectText, { exact: true })).toBeVisible({ timeout: 10_000 });
  });
}
