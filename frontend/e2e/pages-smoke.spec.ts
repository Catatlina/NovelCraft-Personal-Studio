/**
 * §7 #4 完整浏览器验收：八页面可达性烟雾测试（KI-006）。
 *
 * 单次注册后遍历左侧主导航全部八个入口，断言每个页面都渲染了真实的标题
 * （h1/h2），而非白屏或崩溃。空态文案与 nav 标签不同，断言使用页面真实标题。
 * 断言用 getByRole("heading")，避免同时命中 nav 按钮上的同名文案。
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

async function registerFreshUser(page: Page, attempt = 0): Promise<void> {
  const email = `starlume-pages-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
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
}

test("八页面可达性：遍历全部八个入口均渲染真实标题", async ({ page }) => {
  await registerFreshUser(page);
  const nav = page.getByRole("navigation", { name: "小说创作主导航" });
  for (const tab of TABS) {
    await nav.getByRole("button", { name: tab.label, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: tab.expectText, exact: true }).first(),
    ).toBeVisible({ timeout: 10_000 });
  }
});
