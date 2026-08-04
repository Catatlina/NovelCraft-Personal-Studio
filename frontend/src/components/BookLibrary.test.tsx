import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BookLibrary } from "./BookLibrary";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: vi.fn() }));

const apiMock = vi.mocked(api);
const longIdea = "项目完整设定：".padEnd(900, "两界资源交换、人物目标、冲突升级与章节节拍。");

afterEach(() => {
  vi.clearAllMocks();
});

beforeEach(() => {
  apiMock.mockImplementation(async (path: string) => {
    if (path.startsWith("/api/v1/library/books?")) {
      return [{
        id: "book-1",
        title: "两界华夏",
        status: "draft",
        meta: { idea: longIdea, synopsis: "沈砚在一座即将停摆的旧城里接手一间无人问津的修理铺，却发现每一件送来的旧物都藏着一段未完的命运。为了查清父亲失踪的真相，他只能在修好城市之前，先找出藏在账本里的那个人。" },
        created_at: "2026-08-01T00:00:00Z",
        updated_at: "2026-08-01T00:00:00Z",
      }] as never;
    }
    if (path.endsWith("/completion")) {
      return {
        total_chapters: 0,
        reviewed_chapters: 0,
        total_words: 0,
        average_review_score: 0,
        review_percent: 0,
        exportable: false,
      } as never;
    }
    if (path.endsWith("/generation-batches")) return [] as never;
    throw new Error("unexpected api path: " + path);
  });
});

describe("书库紧凑列表", () => {
  it("长灵感默认折叠，展开后仍可查看全文且保留书籍操作", async () => {
    render(<BookLibrary projectId="project-1" onOpen={vi.fn()} />);

    await waitFor(() => expect(screen.getByText(/两界华夏/)).toBeTruthy());
    expect(screen.getByText(/沈砚在一座即将停摆的旧城里/)).toBeTruthy();
    const toggle = screen.getByRole("button", { name: "展开灵感" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("button", { name: "查看详情" })).toBeTruthy();

    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "收起灵感" }).getAttribute("aria-expanded")).toBe("true");
  });
});
