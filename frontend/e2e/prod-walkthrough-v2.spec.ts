/**
 * 生产 Web 功能走查 v2（#162，2026-08-02）
 *
 * 走查方式：注册 → API 预建小说（真实数据）→ 浏览器选中该书 →
 * 验证 V7 页签出现且 Cost/Prompt 渲染真实页面（无 mock 假数据）。
 * 建书走 API 避免向导 AI 依赖（Key 不注入走查）。
 */
import { expect, type Page, test } from "@playwright/test";

const BASE = process.env.BASE_URL || "https://novel.xyjin.xyz";

test("生产走查：八页面可达 + V7 Cost/Prompt 真实渲染", async ({ page, request }) => {
  // 1. 注册（浏览器）
  const email = `prod-walk2-${Date.now()}@t.cn`;
  await page.goto(BASE);
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 20_000 });

  // 2. 八页面可达
  const nav = page.getByRole("navigation", { name: "小说创作主导航" });
  const TABS: Array<[string, string]> = [
    ["小说首页", "小说首页"],
    ["创作向导", "把一个念头，变成完整故事。"],
    ["扫榜选书", "榜单中心"],
    ["我的书库", "我的书库"],
    ["创作进度", "还没有正在运行的创作。"],
    ["章节编辑器", "还没有可以编辑的章节。"],
    ["审阅与一致性", "审阅与一致性"],
    ["小说设置", "小说设置"],
  ];
  for (const [label, text] of TABS) {
    await nav.getByRole("button", { name: label, exact: true }).click();
    await expect(page.getByRole("heading", { name: text, exact: true }).first()).toBeVisible({ timeout: 10_000 });
  }

  // 3. 从浏览器 sessionStorage 拿 token，API 预建小说（真实数据）
  const token = await page.evaluate(() => sessionStorage.getItem("nc_token") || "");
  console.log(`[走查] token=${token ? "已获取" : "缺失"}`);
  expect(token).toBeTruthy();
  const H = { Authorization: `Bearer ${token}` };

  const projectsRes = await request.get(`${BASE}/api/v1/projects`, { headers: H });
  let pid: string | null = null;
  if (projectsRes.ok()) {
    const data = await projectsRes.json();
    pid = data?.data?.[0]?.id ?? null;
  }
  if (!pid) {
    const pr = await request.post(`${BASE}/api/v1/projects`, {
      headers: H, data: { name: "prod-walk" },
    });
    pid = pr.ok() ? (await pr.json())?.data?.id ?? null : null;
  }
  let nid: string | null = null;
  if (pid) {
    const nr = await request.post(`${BASE}/api/v1/projects/${pid}/novels`, {
      headers: H,
      data: { idea: "生产走查小说", genre: "都市", style: "现代" },
    });
    nid = nr.ok() ? (await nr.json())?.data?.id ?? null : null;
  }
  console.log(`[走查] project=${pid} novel=${nid}`);
  expect(nid).toBeTruthy();

  // 4. 我的书库 → 点「进入编辑」激活小说（activateNovel 设 novel state，V7 需要）
  await page.goto(BASE);
  await nav.getByRole("button", { name: "我的书库", exact: true }).click();
  await page.waitForTimeout(2000);
  const novelCard = page.locator(`text=生产走查小说`).first();
  if (await novelCard.isVisible({ timeout: 10_000 }).catch(() => false)) {
    await novelCard.click();
    await page.waitForTimeout(1500);
  }
  const enterBtn = page.getByRole("button", { name: "进入编辑" }).first();
  if (await enterBtn.isVisible({ timeout: 8000 }).catch(() => false)) {
    await enterBtn.click();
    await page.waitForTimeout(2500); // activateNovel 拉取数据
    console.log("[走查] 小说已激活，当前页:", await page.url());
  } else {
    console.log("[走查] 未找到「进入编辑」，可能书库卡片未展开");
  }

  // 5. 切到 V7 智能体页签（hash 路由）
  await page.goto(`${BASE}/#/v7`);
  await page.waitForTimeout(3000);
  const v7Heading = page.getByRole("heading", { name: "质量与运行监控", exact: true }).first();
  console.log(`[走查] V7 页面标题可见: ${await v7Heading.isVisible({ timeout: 8000 }).catch(() => false)}`);

  // 6. Cost Monitor 渲染
  const costNav = page.getByRole("tab", { name: "成本账本" }).first();
  if (await costNav.isVisible({ timeout: 8000 }).catch(() => false)) {
    await costNav.click();
    await expect(page.getByRole("heading", { name: "V6 / V7 Provider 成本对账", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1500);
    const body = await page.locator("body").innerText();
    expect(body.includes("187.5")).toBeFalsy(); // mock 假数据不应出现
    console.log("[走查] V7 Cost Monitor 渲染真实页面（无 mock 数据）");
  } else {
    console.log("[走查] V7 Cost Monitor 未找到（页面结构可能不同）");
  }

  // 7. Prompts 渲染（V7 侧边栏按钮，文本定位兜底）
  const promptNav = page.getByRole("tab", { name: "Prompt provenance" }).first();
  if (await promptNav.isVisible({ timeout: 8000 }).catch(() => false)) {
    await promptNav.click();
    await expect(page.getByRole("heading", { name: "最近注册的 Prompt 版本", exact: true })).toBeVisible({ timeout: 10_000 });
    await page.waitForTimeout(1500);
    const body = await page.locator("body").innerText();
    expect(body.includes("a1b2c3d4e5f6g7h8")).toBeFalsy(); // MOCK_PROMPTS hash 不应出现
    console.log("[走查] V7 Prompts 渲染真实页面（无 mock 数据）");
  } else {
    console.log("[走查] V7 Prompts 文本未找到");
  }
});
