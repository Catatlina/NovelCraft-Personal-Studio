import { afterEach, describe, expect, it, vi } from "vitest";
import { api, apiEnvelope, apiStream, ApiError } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("API response contract", () => {
  it("unwraps successful response data exactly once", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ code: 0, message: "ok", data: [{ id: "project-1" }] }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )));

    await expect(api<Array<{ id: string }>>("/api/v1/projects"))
      .resolves.toEqual([{ id: "project-1" }]);
  });

  it("keeps the envelope only through the explicit low-level API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ code: 0, message: "ok", data: { id: "book-1" } }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )));

    await expect(apiEnvelope<{ id: string }>("/api/v1/library/books/book-1"))
      .resolves.toEqual({ code: 0, message: "ok", data: { id: "book-1" } });
  });

  it("preserves the backend error payload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ code: 403, message: "forbidden", data: null }),
      { status: 403, headers: { "Content-Type": "application/json" } },
    )));

    const failure = api("/api/v1/projects");
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({
      status: 403,
      payload: { code: 403, message: "forbidden", data: null },
    });
  });

  it("normalizes non-string SSE text instead of breaking the editor preview", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      'data: {"delta":123}\n\ndata: {"done":true,"text":456}\n\n',
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    )));

    const deltas: string[] = [];
    await expect(apiStream("/api/v1/contents/chapter-1/ai/continue/stream", { method: "POST" }, delta => deltas.push(delta)))
      .resolves.toEqual({ text: "456" });
    expect(deltas).toEqual(["123"]);
  });
});
