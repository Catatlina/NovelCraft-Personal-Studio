/**
 * Starlume AI 小说主线 T4：
 * 注册 → 小说首页 → 创作向导/书库 → 章节编辑与保存 → 审阅/设置。
 * 真实 AI 全链用例受 DEEPSEEK_API_KEY 保护；无 Key 时只跳过该用例，
 * 其余确定性真库链路必须全部通过。
 */
import { expect, Page, test } from "@playwright/test";

async function registerFreshUser(page: Page): Promise<string> {
  const email = `starlume-e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
  return email;
}

async function authContext(page: Page) {
  const token = await page.evaluate(() => sessionStorage.getItem("nc_token"));
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  const projectsResponse = await page.request.get("/api/v1/projects", { headers });
  expect(projectsResponse.ok()).toBeTruthy();
  const projects = (await projectsResponse.json()).data;
  return { token: token!, headers, projectId: projects[0].id as string };
}

async function createBookWithChapter(page: Page, titleSeed: string) {
  const { headers, projectId } = await authContext(page);
  const createResponse = await page.request.post(`/api/v1/projects/${projectId}/novels`, {
    headers,
    data: { idea: titleSeed, genre: "悬疑", style: "克制、强画面感", target_words: 100000 },
  });
  expect(createResponse.ok()).toBeTruthy();
  const novelId = (await createResponse.json()).data.id as string;
  const importResponse = await page.request.post(`/api/v1/novels/${novelId}/import-chapters`, {
    headers,
    data: { text: "第1章 雨夜来客" },
  });
  expect(importResponse.ok()).toBeTruthy();
  expect((await importResponse.json()).data.imported).toBe(1);
  return novelId;
}

test("小说主线①：注册后只展示七个小说入口与真实空状态", async ({ page }) => {
  await registerFreshUser(page);

  const navigation = page.getByRole("navigation", { name: "小说创作主导航" });
  for (const label of ["小说首页", "创作向导", "我的书库", "创作进度", "章节编辑器", "审阅与一致性", "小说设置"]) {
    await expect(navigation.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  await expect(navigation.getByRole("button", { name: "扫榜选书", exact: true })).toHaveCount(0);
  await expect(page.getByText("书架还是空的")).toBeVisible();
  await expect(page.getByText("当前没有阻塞项")).toBeVisible();
});

test("小说主线②：旧入口迁移、未知入口 404、移动端底栏", async ({ page }) => {
  await registerFreshUser(page);

  await page.goto("/#/ranking");
  await expect(page).toHaveURL(/#\/wizard$/);
  await expect(page.getByRole("heading", { name: "把一个念头，变成完整故事。" })).toBeVisible();

  await page.goto("/#/missing-page");
  await expect(page.getByRole("heading", { name: "这一页没有写进故事里。" })).toBeVisible();
  await page.locator(".not-found-page").getByRole("button", { name: "返回小说首页" }).click();

  await page.setViewportSize({ width: 390, height: 844 });
  const mobileNavigation = page.getByRole("navigation", { name: "移动端小说创作主导航" });
  await expect(mobileNavigation).toBeVisible();
  await expect(mobileNavigation.getByRole("button", { name: "章节编辑器", exact: true })).toBeVisible();
});

test("小说主线③：建书→详情→导入章节→编辑→保存→重载持久化", async ({ page }) => {
  await registerFreshUser(page);
  const titleSeed = `章节保存验收-${Date.now()}`;
  await createBookWithChapter(page, titleSeed);

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "我的书库", exact: true }).click();
  const bookCard = page.locator(".library-page .card").filter({ hasText: titleSeed });
  await expect(bookCard).toBeVisible({ timeout: 10_000 });
  await bookCard.getByRole("button", { name: "查看详情" }).click();
  await expect(page.getByRole("heading", { name: "简介" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "全部章节" })).toBeVisible();
  await page.getByRole("button", { name: "返回书库" }).click();

  const reopenedCard = page.locator(".library-page .card").filter({ hasText: titleSeed });
  await reopenedCard.getByRole("button", { name: "进入编辑" }).click();
  await expect(page.getByText("第1章 雨夜来客", { exact: true }).first()).toBeVisible({ timeout: 10_000 });

  const editor = page.locator(".ProseMirror");
  await editor.fill("雨落在旧车站。门外的人敲了三下。");
  const saveResponse = page.waitForResponse(response =>
    response.url().includes("/api/v1/contents/") &&
    response.request().method() === "PUT" &&
    response.ok(),
  );
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await saveResponse;

  await page.reload();
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "我的书库", exact: true }).click();
  const persistedCard = page.locator(".library-page .card").filter({ hasText: titleSeed });
  await persistedCard.getByRole("button", { name: "进入编辑" }).click();
  await expect(page.locator(".ProseMirror")).toContainText("雨落在旧车站。门外的人敲了三下。", { timeout: 10_000 });
});

test("小说主线④：审阅不伪造分数，小说设置只保留创作相关入口", async ({ page }) => {
  await registerFreshUser(page);

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "审阅与一致性", exact: true }).click();
  await expect(page.getByText("还没有可用的审阅结果")).toBeVisible();
  await expect(page.getByText("/ 100")).toHaveCount(0);

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "小说设置", exact: true }).click();
  const settingsNavigation = page.getByRole("navigation", { name: "小说设置分类" });
  await expect(settingsNavigation.getByRole("button", { name: "AI 连接" })).toBeVisible();
  await expect(settingsNavigation.getByRole("button", { name: "创作数据" })).toBeVisible();
  await expect(settingsNavigation.getByRole("button", { name: "账号安全" })).toBeVisible();
  await expect(settingsNavigation.getByRole("button", { name: "平台连接" })).toHaveCount(0);

  await page.getByPlaceholder("例如 deepseek-chat").fill("deepseek-chat");
  await page.getByRole("button", { name: "保存 AI 配置" }).click();
  await expect(page.getByText("AI 配置已保存在当前浏览器会话")).toBeVisible();
  await expect.poll(() => page.evaluate(() => sessionStorage.getItem("nc_model"))).toBe("deepseek-chat");
});

test("小说主线⑥：真实 AI 编辑 生成→预览→放弃/应用→版本恢复（protected）", async ({ page }) => {
  test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY");
  test.setTimeout(480_000);

  await registerFreshUser(page);
  const titleSeed = `AI编辑闭环验收-${Date.now()}`;
  await createBookWithChapter(page, titleSeed);

  // 打开章节编辑器并写入确定性的原文 A
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "我的书库", exact: true }).click();
  const bookCard = page.locator(".library-page .card").filter({ hasText: titleSeed });
  await bookCard.getByRole("button", { name: "进入编辑" }).click();
  const editor = page.locator(".ProseMirror");
  await expect(editor).toBeVisible({ timeout: 10_000 });
  const originalText = "档案室的灯在午夜第三次闪烁，她终于看清了报纸上自己的名字。";
  await editor.fill(originalText);
  const firstSave = await page.waitForResponse(r => r.url().includes("/api/v1/contents/") && r.request().method() === "PUT" && r.ok());
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await firstSave;
  // 从保存响应 URL 取出 content id（/api/v1/contents/{id}）
  const contentId = new URL(firstSave.url()).pathname.split("/").filter(Boolean).pop()!;

  // ① 真实 AI 续写 → 预览出现，正文未变
  await page.getByRole("button", { name: "续写", exact: true }).click();
  const previewPane = page.locator(".ai-edit-preview");
  await expect(previewPane).toBeVisible({ timeout: 240_000 });
  const proposedText = await previewPane.locator(".ai-edit-compare textarea").nth(1).inputValue();
  expect(proposedText.trim().length).toBeGreaterThan(20);
  const proposalMark = proposedText.trim().slice(0, 15);
  await expect(editor).toHaveText(originalText); // 预览阶段正文不变
  await page.screenshot({ path: "artifacts/screenshots/protected-07-ai-preview.png" });

  // ② 放弃 → 预览关闭，原文保持不变
  await previewPane.getByRole("button", { name: "放弃建议" }).click();
  await expect(previewPane).toHaveCount(0);
  await expect(editor).toHaveText(originalText);

  // ③ 再次续写 → 应用到草稿 → 正文包含 AI 建议
  await page.getByRole("button", { name: "续写", exact: true }).click();
  await expect(previewPane).toBeVisible({ timeout: 240_000 });
  const proposedText2 = await previewPane.locator(".ai-edit-compare textarea").nth(1).inputValue();
  const proposalMark2 = proposedText2.trim().slice(0, 15);
  await previewPane.getByRole("button", { name: "应用到草稿" }).click();
  await expect(previewPane).toHaveCount(0);
  await expect(editor).toContainText(originalText.slice(0, 12));
  await expect(editor).toContainText(proposalMark2);
  await page.screenshot({ path: "artifacts/screenshots/protected-08-ai-applied.png" });

  // ④ 应用 AI 后轮询版本 API，直到出现「应用前正文 A」的可恢复版本（见下方）

  // ⑤ 恢复「应用前正文 A」对应的版本（快照=A）→ AI 建议消失，原文回归
  //    关键：applyPendingAiEdit 会立即触发一次 PUT（ai_edit 版本，只存算子元数据、无 body），
  //    可恢复的正文版本来自 ~3s 后的 debounced 自动保存（offline_save，快照=应用前正文 A）。
  //    因此轮询版本 API 直到出现快照正文等于 A 的版本，再按 DESC 顺序精确点击对应恢复按钮。
  const versionsCard = page.locator(".card").filter({ hasText: "版本历史" });
  await expect(versionsCard).toBeVisible();
  const token = await page.evaluate(() => sessionStorage.getItem("nc_token"));
  const bodyText = (body: any): string => {
    if (!body || !Array.isArray(body.content)) return "";
    return body.content.map((n: any) =>
      typeof n === "string" ? n :
      (n && typeof n.text === "string" ? n.text : (n && Array.isArray(n.content) ? bodyText({ content: n.content }) : ""))
    ).join("");
  };
  const listVersions = async (): Promise<Array<{ id: string; label: string; snapshot?: { body?: any } }>> => {
    const r = await page.request.get(`/api/v1/contents/${contentId}/versions`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok()) return [];
    return (await r.json()).data as Array<{ id: string; label: string; snapshot?: { body?: any } }>;
  };
  let targetIdx = -1;
  let versionsList: Array<{ id: string; label: string; snapshot?: { body?: any } }> = [];
  const pollDeadline = Date.now() + 40_000;
  while (Date.now() < pollDeadline) {
    versionsList = await listVersions();
    // 定位「label=offline_save 且快照正文等于原文 A」的版本（autosave）；
    // 跳过 ai_edit 版本（只存算子元数据、无 body）与步骤③显式保存（快照为空）。
    targetIdx = versionsList.findIndex(v => v.label === "offline_save" && bodyText(v.snapshot?.body) === originalText);
    if (targetIdx >= 0) break;
    await page.waitForTimeout(1000);
  }
  expect(targetIdx, "应存在快照等于原文 A 的可恢复版本").toBeGreaterThanOrEqual(0);
  // 按版本真实 id 点击恢复按钮，避免 UI 版本列表顺序/陈旧导致的错位
  // （autosave 创建 [A] 版本后 UI 可能尚未刷新，nth(index) 会点到错误版本）。
  const targetId = versionsList[targetIdx].id;
  const targetBtn = versionsCard.locator(`button[data-version-id="${targetId}"]`);
  await targetBtn.waitFor({ state: "visible", timeout: 15_000 });
  const restoreResponse = page.waitForResponse(r => r.url().includes("/versions/restore") && r.ok());
  await targetBtn.click();
  await restoreResponse;
  await expect(editor).toHaveText(originalText, { timeout: 15_000 });
  await expect(editor).not.toContainText(proposalMark2);
  await page.screenshot({ path: "artifacts/screenshots/protected-09-version-restored.png" });
  void proposalMark; // 首次建议仅用于放弃分支断言
});

test("小说主线⑤：真实 AI 向导→人工定名→首章→审阅→导出（protected）", async ({ page }) => {
  test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY");
  test.setTimeout(900_000);

  await registerFreshUser(page);
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "创作向导", exact: true }).click();
  await page.getByRole("textbox", { name: /用几句话描述你的故事/ }).fill(
    "一位城市档案修复师发现，被删除的旧报纸会在午夜预告第二天的失踪案。",
  );
  await page.getByRole("combobox", { name: "小说题材" }).selectOption("悬疑");
  await page.getByRole("button", { name: /短篇/ }).click();
  await page.getByRole("button", { name: "开始生成小说" }).click();

  await expect(page.getByText("需要你的决定")).toBeVisible({ timeout: 360_000 });
  const candidates = page.locator(".title-candidate-grid button");
  await expect(candidates).not.toHaveCount(0);
  await page.screenshot({ path: "artifacts/screenshots/protected-02-human-naming.png" });
  await candidates.first().click();

  await expect(page.getByText("创作完成", { exact: true })).toBeVisible({ timeout: 720_000 });
  await page.screenshot({ path: "artifacts/screenshots/protected-03-complete.png" });
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "我的书库", exact: true }).click();
  const firstBook = page.locator(".library-page .card").first();
  await expect(firstBook).toBeVisible();
  await expect(firstBook.getByRole("button", { name: "导出TXT" })).toBeEnabled();
  await page.screenshot({ path: "artifacts/screenshots/protected-04-library.png" });
  await firstBook.getByRole("button", { name: "进入编辑" }).click();
  await expect(page.locator(".ProseMirror")).not.toBeEmpty();
  await page.screenshot({ path: "artifacts/screenshots/protected-05-editor.png" });

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "审阅与一致性", exact: true }).click();
  await expect(page.getByText("还没有可用的审阅结果")).toHaveCount(0);
  await expect(page.getByText("一致性维度")).toBeVisible();
  await page.screenshot({ path: "artifacts/screenshots/protected-06-review.png" });
});
