import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Wizard } from "./Wizard";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  apiRaw: vi.fn().mockResolvedValue({ data: { ai_key_configured: true } }),
  getApiKey: vi.fn().mockReturnValue("test-key"),
}));

afterEach(() => cleanup());

describe("创作向导写作风格", () => {
  it("默认使用网文风格预设，也保留高级自定义入口", () => {
    const setStyle = vi.fn();
    render(
      <Wizard
        idea="一个人在旧城发现一封寄给未来的信"
        setIdea={vi.fn()}
        genre="都市"
        setGenre={vi.fn()}
        platform="fanqie"
        setPlatform={vi.fn()}
        subgenre=""
        setSubgenre={vi.fn()}
        stylePlugin=""
        setStylePlugin={vi.fn()}
        style="第三人称、克制、悬疑、强画面感"
        setStyle={setStyle}
        targetWords={100000}
        setTargetWords={vi.fn()}
        busy={false}
        startBootstrap={vi.fn()}
      />,
    );

    const select = screen.getByLabelText("写作风格预设") as HTMLSelectElement;
    expect(select.value).toContain("第三人称、克制、悬疑、强画面感");
    fireEvent.change(select, { target: { value: "__custom__" } });
    expect(screen.getByLabelText("自定义写作风格")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("自定义写作风格"), { target: { value: "第三人称、短句、强冲突" } });
    expect(setStyle).toHaveBeenCalledWith("第三人称、短句、强冲突");
  });
});
