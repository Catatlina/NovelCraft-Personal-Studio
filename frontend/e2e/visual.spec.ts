/**
 * Starlume AI 七页面桌面/手机截图集（KI-006 视觉证据）。
 *
 * 默认 `npm run test:e2e` 不会执行本文件：必须用环境变量显式开启，
 * 以免改变已验收的 "4 passed, 1 skipped" 门禁语义。
 *
 *    STARLUME_CAPTURE_VISUAL=1 npx playwright test e2e/visual.spec.ts
 *
 * 截图输出到 frontend/artifacts/screenshots/（仓库已 gitignore），
 * 由本提交中的脚本可复现。需要真实后端 + Vite（由 playwright.config webServer 启动）。
 */
import { expect, type Page, test } from "@playwright/test";

const TABS = [
  "小说首页",
  "创作向导",
  "我的书库",
  "创作进度",
  "章节编辑器",
  "审阅与一致性",
  "小说设置",
] as const;

async function registerFreshUser(page: Page): Promise<void> {
  const email = `starlume-visual-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-visual-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
}

test("七页面桌面/手机截图集", async ({ page }) => {
  test.skip(!process.env.STARLUME_CAPTURE_VISUAL, "visual capture is opt-in");

  await registerFreshUser(page);
  const nav = page.getByRole("navigation", { name: "小说创作主导航" });

  for (const width of [1280, 390] as const) {
    const height = width === 1280 ? 800 : 844;
    await page.setViewportSize({ width, height });
    for (const label of TABS) {
      await nav.getByRole("button", { name: label, exact: true }).click();
      // 等待对应页面标题或主区域可见，避免截到过渡态
      await page.waitForTimeout(400);
      const safe = label.replace(/[^一-龥a-zA-Z]/g, "");
      await page.screenshot({
        path: `artifacts/screenshots/${width}-${safe}.png`,
        fullPage: false,
      });
    }
  }

  // 未知入口 404 状态
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/#/this-route-does-not-exist");
  await page.waitForTimeout(400);
  await page.screenshot({ path: "artifacts/screenshots/1280-404.png" });
});
