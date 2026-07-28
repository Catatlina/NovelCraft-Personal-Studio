import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Progress } from "./Progress";

vi.mock("../lib/api", () => ({
  ApiError: class extends Error {},
  apiRaw: vi.fn().mockResolvedValue(undefined),
}));

describe("创作进度门禁", () => {
  it("没有运行时展示真实空状态", () => {
    render(<Progress run={null} novel={null} onConfirm={vi.fn()} onRegenerateTitles={vi.fn()} />);

    expect(screen.getByText("还没有正在运行的创作。")).toBeTruthy();
    expect(screen.queryByText("预计完成")).toBeNull();
  });

  it("人工节点等待时必须由用户确认书名", async () => {
    const confirm = vi.fn().mockResolvedValue(undefined);
    render(
      <Progress
        run={{
          id: "run-1",
          status: "waiting_human",
          current_node_key: "human_confirm_title",
          context: { title_candidates: ["星潮未眠", "长夜有光"] },
          nodes: [{
            node_key: "human_confirm_title",
            kind: "human",
            agent: null,
            title: "选定书名",
            status: "waiting_human",
          }],
        }}
        novel={null}
        onConfirm={confirm}
        onRegenerateTitles={vi.fn()}
      />,
    );

    expect(screen.getByText("确认前流程会停在这里，不会替你擅自决定。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "星潮未眠" }));
    await waitFor(() => expect(confirm).toHaveBeenCalledWith("星潮未眠"));
  });

  it("失败节点显示失败原因与重试按钮，且重试打到正确端点", async () => {
    const { apiRaw } = await import("../lib/api");
    render(
      <Progress
        run={{
          id: "run-2",
          status: "failed",
          current_node_key: "plan_idea",
          context: {},
          nodes: [{
            node_key: "plan_idea",
            kind: "agent",
            agent: "deepseek",
            title: "创意策划",
            status: "failed",
            error: "模型超时",
            attempt: 1,
          }],
        }}
        novel={null}
        onConfirm={vi.fn()}
        onRegenerateTitles={vi.fn()}
      />,
    );

    expect(screen.getByText("执行失败")).toBeTruthy();
    expect(screen.getByText("模型超时")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /重试此步骤/ }));
    await waitFor(() =>
      expect(apiRaw).toHaveBeenCalledWith(
        "/api/v1/runs/run-2/nodes/plan_idea/retry",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});
