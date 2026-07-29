import React, { useCallback, useEffect, useState } from "react";
import { Film } from "lucide-react";
import { api } from "../lib/api";

type Scene = {
  scene_index: number;
  title: string;
  beat: string;
  goal: string;
  setting: string;
  pov: string;
};

const BEAT_COLOR: Record<string, string> = {
  起势: "#6ea8fe",
  发展: "#63d2a4",
  转折: "#ffb454",
  高潮: "#ff6b6b",
  落幕: "#b794f6",
};

export function SceneBoard({ chapterId, projectId }: { chapterId: string; projectId: string }) {
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!chapterId) return [];
    try {
      const res = await api<{ scenes: Scene[] }>(`/api/v1/chapters/${chapterId}/scenes`);
      const nextScenes = res.scenes || [];
      setScenes(nextScenes);
      return nextScenes;
    } catch {
      /* 读取失败静默，不阻塞编辑器 */
      return [];
    }
  }, [chapterId]);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    if (!chapterId || busy) return;
    setBusy(true);
    setError("");
    try {
      await api(`/api/v1/chapters/${chapterId}/scene-direct`, { method: "POST", body: "{}" });
      // 异步任务，轮询最多 ~12s
      for (let i = 0; i < 12; i++) {
        await new Promise(r => setTimeout(r, 1000));
        const nextScenes = await load();
        if (nextScenes.length > 0) break;
      }
    } catch (e: any) {
      setError(e?.message || "生成失败");
    } finally {
      setBusy(false);
    }
  }

  if (!chapterId) return null;

  return (
    <details style={{ marginTop: 12 }} open>
      <summary style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontWeight: 600, fontSize: 13 }}>
        <Film size={15} /> 场景分镜
      </summary>
      <div style={{ marginTop: 8 }}>
        <button type="button" disabled={busy} onClick={generate} className="form-input" style={{ width: "100%", cursor: busy ? "wait" : "pointer" }}>
          {busy ? "场景导演规划中…" : "生成场景分镜"}
        </button>
        {error ? <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>{error}</div> : null}
        {scenes.length === 0 && !busy ? (
          <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 6 }}>暂无分镜，点击上方按钮由 Scene Director 规划。</p>
        ) : (
          <ol style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 12 }}>
            {scenes.map(s => (
              <li key={s.scene_index} style={{ marginBottom: 6 }}>
                <span style={{ color: BEAT_COLOR[s.beat] || "var(--text-2)", fontWeight: 600 }}>【{s.beat}】</span>
                {s.title} <span style={{ color: "var(--text-2)" }}>({s.pov || "—"})</span>
                {s.goal ? <div style={{ color: "var(--text-2)" }}>目标：{s.goal}</div> : null}
                {s.setting ? <div style={{ color: "var(--text-2)" }}>场景：{s.setting}</div> : null}
              </li>
            ))}
          </ol>
        )}
      </div>
    </details>
  );
}
