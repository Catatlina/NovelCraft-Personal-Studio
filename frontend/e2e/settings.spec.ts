/**
 * §7 #4 真库设置正负例（KI-006 浏览器验收）。
 *
 * 覆盖两类真实后端/会话链路，无需 Provider Key，可在 CI 确定性通过：
 *  - AI 连接（BYOK）保存正例 + 会话持久化；未改动时保存按钮禁用（守卫）。
 *  - 密码修改（真实 DB）正例（旧密码正确）/ 负例（旧密码错误）。
 *
 * 注册密码与 main-chain 保持一致：Starlume-e2e-1234。registerFreshUser 带
 * 429 退避重试，规避后端 5/min 注册限流。
 */
import { expect, type Page, test } from "@playwright/test";

const REG_PASSWORD = "Starlume-e2e-1234";

async function registerFreshUser(page: Page, attempt = 0): Promise<void> {
  const email = `starlume-settings-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill(REG_PASSWORD);
  await page.getByRole("button", { name: "注册", exact: true }).click();
  try {
    await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
  } catch (e) {
    if (attempt >= 3) throw e;
    console.warn(`[registerFreshUser] 注册后未出现首页（可能触发限流 429），第 ${attempt + 1} 次退避重试`);
    await page.waitForTimeout(65_000);
    return registerFreshUser(page, attempt + 1);
  }
}

async function openSettings(page: Page): Promise<void> {
  const nav = page.getByRole("navigation", { name: "小说创作主导航" });
  await nav.getByRole("button", { name: "小说设置", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说设置", exact: true }).first()).toBeVisible({ timeout: 10_000 });
}

const KEY_INPUT = "输入 DeepSeek / OpenAI / Claude / Gemini Key";
const URL_INPUT = "例如 https://api.deepseek.com/v1";
const MODEL_INPUT = "例如 deepseek-chat";

test("设置-AI配置未改动时保存按钮禁用（负例守卫）", async ({ page }) => {
  await registerFreshUser(page);
  await openSettings(page);
  const saveBtn = page.getByRole("button", { name: /保存 AI 配置|配置已保存/ });
  await expect(saveBtn).toBeDisabled();
  await expect(saveBtn).toHaveText("配置已保存");
});

test("设置-AI配置保存正例并会话持久化（重载后保留）", async ({ page }) => {
  await registerFreshUser(page);
  await openSettings(page);

  await page.getByPlaceholder(KEY_INPUT).fill("sk-test-local-0123456789");
  await page.getByPlaceholder(URL_INPUT).fill("https://api.deepseek.com/v1");
  await page.getByPlaceholder(MODEL_INPUT).fill("deepseek-chat");

  const saveBtn = page.getByRole("button", { name: "保存 AI 配置" });
  await expect(saveBtn).toBeEnabled();
  await saveBtn.click();

  await expect(
    page.getByText("AI 配置已保存在当前浏览器会话，后续创作请求会立即使用。"),
  ).toBeVisible({ timeout: 10_000 });

  // 重载后配置仍在（sessionStorage 持久化，非伪造）
  await page.reload();
  await openSettings(page);
  await expect(page.getByPlaceholder(KEY_INPUT)).toHaveValue("sk-test-local-0123456789");
  await expect(page.getByPlaceholder(URL_INPUT)).toHaveValue("https://api.deepseek.com/v1");
  await expect(page.getByPlaceholder(MODEL_INPUT)).toHaveValue("deepseek-chat");
});

test("设置-密码修改真实 DB 正例（旧密码正确）", async ({ page }) => {
  await registerFreshUser(page);
  await openSettings(page);

  await page.locator("label.settings-field", { hasText: "当前密码" }).locator("input").fill(REG_PASSWORD);
  await page.locator("label.settings-field", { hasText: "新密码" }).locator("input").fill("Starlume-new-5678");
  await page.getByRole("button", { name: /更新密码|正在更新/ }).click();

  await expect(page.getByText("密码已修改，其他设备上的旧会话将失效。")).toBeVisible({ timeout: 10_000 });
});

test("设置-密码修改真实 DB 负例（旧密码错误被拒）", async ({ page }) => {
  await registerFreshUser(page);
  await openSettings(page);

  await page.locator("label.settings-field", { hasText: "当前密码" }).locator("input").fill("wrong-password-0000");
  await page.locator("label.settings-field", { hasText: "新密码" }).locator("input").fill("Starlume-new-5678");
  await page.getByRole("button", { name: /更新密码|正在更新/ }).click();

  await expect(page.getByText(/修改失败：/)).toBeVisible({ timeout: 10_000 });
  // 失败时不应出现成功提示
  await expect(page.getByText("密码已修改，其他设备上的旧会话将失效。")).toHaveCount(0);
});
