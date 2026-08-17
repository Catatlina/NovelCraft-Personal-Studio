import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PublishingPreparation } from "./PublishingPreparation";

const apiMock = vi.fn();
vi.mock("../lib/api", () => ({ api: (...args: unknown[]) => apiMock(...args) }));

const chapter = {
  id: "chapter-1",
  title: "第一章",
  body: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "主角拿到证据。" }] }] },
  meta: { seq: 1 },
};

function seedApi() {
  apiMock.mockImplementation((path: string) => {
    if (path.includes("platform-profiles")) return Promise.resolve({ profiles: [{ id: "profile-1", platform: "fanqie", profile_name: "番茄", policy_status: "confirmed", policy_version: "2026", ai_usage_policy: "required_disclosure" }] });
    if (path.includes("variants/novel")) return Promise.resolve({ variants: [{ id: "variant-1", novel_id: "novel-1", platform: "fanqie", variant_name: "番茄版", publication_status: "quality_candidate", ai_disclosure_status: "generated", ai_disclosure_text: "草稿文案" }] });
    if (path.includes("publish-readiness")) return Promise.resolve({ publication_status: "quality_candidate", publish_ready: false, blocking_failures: ["payoff_density"], ai_disclosure_status: "generated", platform_policy_confirmed: true, gate_summary: { gate_scores: { payoff_density: { passed: false, score: 0 } } } });
    if (path.includes("disclosures/variant")) return Promise.resolve({ disclosure_id: "disclosure-1", disclosure_status: "generated", disclosure_text: "草稿文案" });
    return Promise.resolve({});
  });
}

describe("PublishingPreparation", () => {
  beforeEach(() => {
    apiMock.mockReset();
    seedApi();
  });
  afterEach(() => cleanup());

  it("loads real publishing state and exposes the blocked gate", async () => {
    render(<PublishingPreparation projectId="project-1" novelId="novel-1" novelTitle="测试作品" chapters={[chapter]} />);

    expect(await screen.findByText("语义爽点")).toBeTruthy();
    expect(await screen.findByText(/未通过/)).toBeTruthy();
    expect(screen.getByText("草稿文案")).toBeTruthy();
  });

  it("sends selected chapter text to the gate API", async () => {
    render(<PublishingPreparation projectId="project-1" novelId="novel-1" novelTitle="测试作品" chapters={[chapter]} />);
    await screen.findByText("语义爽点");
    fireEvent.click(screen.getByRole("button", { name: "运行七道门禁" }));

    await waitFor(() => expect(apiMock).toHaveBeenCalledWith("/api/v1/publishing/gates/run", expect.objectContaining({ method: "POST" })));
    const call = apiMock.mock.calls.find(([path]) => path === "/api/v1/publishing/gates/run");
    expect(call).toBeTruthy();
    if (!call) return;
    expect(JSON.parse(call[1].body)).toMatchObject({ chapter_id: "chapter-1", variant_id: "variant-1", project_id: "project-1", platform: "fanqie", text: "主角拿到证据。" });
  });

  it("shows provider failure instead of claiming success", async () => {
    apiMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.includes("platform-profiles")) return Promise.resolve({ profiles: [] });
      if (path.includes("variants/novel")) return Promise.resolve({ variants: [{ id: "variant-1", novel_id: "novel-1", platform: "fanqie", variant_name: "番茄版", publication_status: "draft", ai_disclosure_status: "pending" }] });
      if (path.includes("publish-readiness")) return Promise.resolve({ publication_status: "draft", publish_ready: false, blocking_failures: [], ai_disclosure_status: "pending", platform_policy_confirmed: false });
      if (path.includes("disclosures/variant")) return Promise.resolve({});
      if (path === "/api/v1/publishing/gates/run") return Promise.reject(new Error("Provider不可用，门禁未完成"));
      return Promise.resolve({});
    });
    render(<PublishingPreparation projectId="project-1" novelId="novel-1" chapters={[chapter]} />);
    await screen.findAllByText("发布变体");
    fireEvent.click(screen.getByRole("button", { name: "运行七道门禁" }));
    expect(await screen.findByText("Provider不可用，门禁未完成")).toBeTruthy();
  });
});
