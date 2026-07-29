/**
 * Starlume AI 扫榜中心「折叠 UI」浏览器回归（对应 docs/AI_HANDOFF.md §7 #3）：
 * 榜单源 / 榜单快照 两主区默认折叠、可展开/收起（统一折叠行为）。
 *
 * 真实后端（不需要 AI Key）。不 mock。
 */
import { expect, Page, test } from "@playwright/test";

async function registerFreshUser(page: Page, attempt = 0): Promise<void> {
  const email = `starlume-fold-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  try {
    await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
  } catch (e) {
    if (attempt >= 3) throw e;
    await page.waitForTimeout(65_000);
    return registerFreshUser(page, attempt + 1);
  }
}

test("扫榜折叠 UI：榜单源与榜单快照默认折叠且可展开", async ({ page }) => {
  await registerFreshUser(page);
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "扫榜选书", exact: true }).click();
  await expect(page.getByRole("heading", { name: "榜单中心" })).toBeVisible({ timeout: 15_000 });

  const sourceSection = page.locator("details.card", { hasText: "榜单源" });
  const snapshotSection = page.locator("details.card", { hasText: "榜单快照" });

  // 两主区默认折叠（与收口后的统一折叠行为一致）
  await expect(sourceSection).toBeVisible();
  await expect(snapshotSection).toBeVisible();
  await expect(sourceSection).not.toHaveAttribute("open");
  await expect(snapshotSection).not.toHaveAttribute("open");

  // 展开榜单源：出现平台计数与扫榜操作
  await sourceSection.locator("summary").click();
  await expect(sourceSection).toHaveAttribute("open");
  await expect(sourceSection.getByText(/个平台/)).toBeVisible();

  // 收起榜单源
  await sourceSection.locator("summary").click();
  await expect(sourceSection).not.toHaveAttribute("open");

  // 展开榜单快照：出现快照表或空态
  await snapshotSection.locator("summary").click();
  await expect(snapshotSection).toHaveAttribute("open");
  await expect(snapshotSection.getByText(/条记录|暂无快照记录/)).toBeVisible();

  await page.screenshot({ path: "artifacts/screenshots/ranking-fold.png" });
});
