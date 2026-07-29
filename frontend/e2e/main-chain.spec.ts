/**
 * Starlume AI 小说主线 T4：
 * 注册 → 小说首页 → 创作向导/书库 → 章节编辑与保存 → 审阅/设置。
 * 真实 AI 全链用例受 DEEPSEEK_API_KEY 保护；无 Key 时只跳过该用例，
 * 其余确定性真库链路必须全部通过。
 */
import { expect, Page, test } from "@playwright/test";

async function registerFreshUser(page: Page, attempt = 0): Promise<string> {
  const email = `starlume-e2e-${Date.now()}-${Math.floor(Math.random() * 1e4)}@example.com`;
  await page.goto("/");
  await page.getByRole("button", { name: "没有账号？注册" }).click();
  await page.getByPlaceholder("name@example.com").fill(email);
  await page.getByPlaceholder("至少 8 位").fill("Starlume-e2e-1234");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  try {
    await expect(page.getByRole("heading", { name: "小说首页", exact: true })).toBeVisible({ timeout: 15_000 });
  } catch (e) {
    if (attempt >= 3) throw e;
    // 注册限流 5 次/分钟：等待限流窗口过去后用新邮箱重试
    console.warn(`[registerFreshUser] 注册后未出现首页（可能触发限流 429），第 ${attempt + 1} 次退避重试`);
    await page.waitForTimeout(65_000);
    return registerFreshUser(page, attempt + 1);
  }
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

async function createBookWithChapter(page: Page, titleSeed: string, chapterTitle = "第1章 雨夜来客") {
  const { headers, projectId } = await authContext(page);
  const createResponse = await page.request.post(`/api/v1/projects/${projectId}/novels`, {
    headers,
    data: { idea: titleSeed, genre: "悬疑", style: "克制、强画面感", target_words: 100000 },
  });
  expect(createResponse.ok()).toBeTruthy();
  const novelId = (await createResponse.json()).data.id as string;
  const importResponse = await page.request.post(`/api/v1/novels/${novelId}/import-chapters`, {
    headers,
    data: { text: chapterTitle },
  });
  expect(importResponse.ok()).toBeTruthy();
  expect((await importResponse.json()).data.imported).toBe(1);
  return novelId;
}

test("小说主线①：注册后只展示八个小说入口与真实空状态", async ({ page }) => {
  await registerFreshUser(page);

  const navigation = page.getByRole("navigation", { name: "小说创作主导航" });
  for (const label of ["小说首页", "创作向导", "扫榜选书", "我的书库", "创作进度", "章节编辑器", "审阅与一致性", "小说设置"]) {
    await expect(navigation.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  await expect(page.getByText("书架还是空的")).toBeVisible();
  await expect(page.getByText("当前没有阻塞项")).toBeVisible();
});

test("小说主线②：扫榜选书入口有效、未知入口 404、移动端底栏", async ({ page }) => {
  await registerFreshUser(page);

  // 扫榜选书现在是有效入口，不再重定向
  await page.goto("/#/ranking");
  await expect(page).toHaveURL(/#\/ranking$/);
  await expect(page.getByRole("heading", { name: "扫榜选书" })).toBeVisible({ timeout: 10000 });

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

test("小说主线⑤：公共页快速切书后作品、章节与审阅保持同一本", async ({ page }) => {
  await registerFreshUser(page);
  const firstTitle = `切书甲-${Date.now()}`;
  const secondTitle = `切书乙-${Date.now()}`;
  const firstId = await createBookWithChapter(page, firstTitle, "第1章 甲书专属章节");
  const secondId = await createBookWithChapter(page, secondTitle, "第1章 乙书专属章节");

  // 让第一次选择的详情请求故意晚返回，验证旧响应不能覆盖最后一次选择。
  await page.route(`**/api/v1/contents/${secondId}`, async route => {
    await new Promise(resolve => setTimeout(resolve, 700));
    await route.continue();
  });
  await page.reload();
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "章节编辑器", exact: true }).click();

  const selector = page.getByRole("combobox", { name: "切换作品" });
  await expect(selector).toBeVisible({ timeout: 10_000 });
  await selector.selectOption(secondId);
  await selector.selectOption(firstId);

  await expect(selector).toHaveValue(firstId);
  await expect(page.getByText("第1章 甲书专属章节", { exact: true }).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("第1章 乙书专属章节", { exact: true })).toHaveCount(0);
  await page.waitForTimeout(900);
  await expect(selector).toHaveValue(firstId);
  await expect(page.getByText("第1章 甲书专属章节", { exact: true }).first()).toBeVisible();

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "审阅与一致性", exact: true }).click();
  await expect(selector).toHaveValue(firstId);
  await expect(page.getByText("正在查看《第1章 甲书专属章节》的真实审阅证据。", { exact: true })).toBeVisible();

  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "我的书库", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "切换作品" })).toHaveCount(0);
});

test("小说主线⑦：真实 AI 编辑 生成→预览→放弃/应用→版本恢复（protected）", async ({ page }) => {
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

test("小说主线③：创作进度运行中真实节点浏览器证据（protected）", async ({ page }) => {
  test.skip(!process.env.DEEPSEEK_API_KEY, "需要 DEEPSEEK_API_KEY");
  test.setTimeout(240_000);

  await registerFreshUser(page);
  await page.getByRole("navigation", { name: "小说创作主导航" })
    .getByRole("button", { name: "创作向导", exact: true }).click();
  await page.getByRole("textbox", { name: /用几句话描述你的故事/ }).fill(
    "一位城市档案修复师发现，被删除的旧报纸会在午夜预告第二天的失踪案。",
  );
  await page.getByRole("combobox", { name: "小说题材" }).selectOption("悬疑");
  await page.getByRole("button", { name: /短篇/ }).click();
  await page.getByRole("button", { name: "开始生成小说" }).click();

  // 进度页自动出现；轮询直到至少有一个节点处于「生成中」或整体状态为创作中
  await expect(page.locator(".node-list")).toBeVisible({ timeout: 120_000 });
  const runningDeadline = Date.now() + 120_000;
  let sawRunning = false;
  while (Date.now() < runningDeadline) {
    if (await page.locator(".node-list button.running").count() > 0) { sawRunning = true; break; }
    const runState = page.locator(".progress-run-state").first();
    if (await runState.count() > 0 && (await runState.textContent())?.includes("创作中")) { sawRunning = true; break; }
    await page.waitForTimeout(1000);
  }
  expect(sawRunning, "应出现至少一个生成中节点或创作中状态").toBe(true);
  // 进度页渲染真实节点标题与完成度文案
  await expect(page.getByText(/\d+ 个真实节点/)).toBeVisible();
  await expect(page.locator(".progress-overview")).toBeVisible();
  await page.screenshot({ path: "artifacts/screenshots/protected-01-progress-running.png" });
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

test("小说主线⑥：拒绝重写后真实任务失败、原文未被覆盖（NOV-E-003 失败注入）", async ({ page }) => {
  // 失败注入用例：需要“无 Provider 密钥”以让真实 Celery worker 自然失败。
  // 有密钥环境下重写会成功并替换为新稿，与本用例要验证的“失败不覆盖原文”无关，故跳过。
  test.skip(!!process.env.DEEPSEEK_API_KEY, "NOV-E-003 需要无 Provider 密钥以注入任务失败；有密钥时任务成功重写，本用例跳过");
  test.setTimeout(180_000);

  await registerFreshUser(page);
  const titleSeed = `失败注入验收-${Date.now()}`;
  await createBookWithChapter(page, titleSeed, "第1章 雨夜来客");

  const openDetail = async () => {
    await page.getByRole("navigation", { name: "小说创作主导航" })
      .getByRole("button", { name: "我的书库", exact: true }).click();
    const bookCard = page.locator(".library-page .card").filter({ hasText: titleSeed });
    await bookCard.getByRole("button", { name: "查看详情" }).click();
  };

  const originalText = "档案室的灯在午夜第三次闪烁，她终于看清了报纸上自己的名字。";

  // 打开该章编辑器，写入确定性的原文 A 并保存
  await openDetail();
  const chapterRow = page.locator(".chapter-review-row").filter({ hasText: /第1章/ }).first();
  await chapterRow.getByRole("button", { name: /第1章/ }).click();
  const editor = page.locator(".ProseMirror");
  await expect(editor).toBeVisible({ timeout: 10_000 });
  await editor.fill(originalText);
  const saveResponse = page.waitForResponse(
    r => r.url().includes("/api/v1/contents/") && r.request().method() === "PUT" && r.ok(),
  );
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await saveResponse;
  await expect(editor).toHaveText(originalText, { timeout: 10_000 });

  // 回到详情，拒绝重写
  await openDetail();
  const row2 = page.locator(".chapter-review-row").filter({ hasText: /第1章/ }).first();
  await row2.getByRole("button", { name: "拒绝重写" }).click();
  // 确认按钮位于 .review-reject-form（.chapter-review-row 的兄弟节点），按页面作用域定位
  await page.getByRole("button", { name: "确认拒绝并重写" }).click();

  // UI 立即进入“重写中”
  await expect(row2.locator(".pill.running")).toBeVisible({ timeout: 10_000 });

  // 真实 Celery worker 因缺 Provider 密钥失败 → UI 显示“重写失败”
  await expect(row2.locator(".pill.failed")).toBeVisible({ timeout: 150_000 });

  // 页面应明确告知原文未被覆盖（仍在详情视图时断言）
  await expect(page.getByText(/未覆盖|未被覆盖/)).toBeVisible({ timeout: 10_000 });

  // 失败不应覆盖原文：重新打开编辑器，正文与基线一致
  await row2.getByRole("button", { name: /第1章/ }).click();
  const editorAfter = page.locator(".ProseMirror");
  await expect(editorAfter).toBeVisible({ timeout: 10_000 });
  await expect(editorAfter).toHaveText(originalText, { timeout: 10_000 });
});
