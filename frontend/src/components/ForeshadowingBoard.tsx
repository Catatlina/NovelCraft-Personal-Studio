import React, { useEffect, useState } from "react";
import { Lightbulb, CheckCircle, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../lib/api";
import { Pagination } from "./ui";
import { usePagination } from "../hooks/usePagination";

type Foreshadowing = {
  id: string; content: string; status: string;
  planned_resolve_chapter: number; chapter_id: string;
};

// ── In-page Banner (loading / error), per-page pattern reused from Plugins/Overview ──
function Banner({
  tone,
  children,
  action,
}: {
  tone: "info" | "error";
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  const isError = tone === "error";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "12px 16px",
        borderRadius: "var(--r-md)",
        marginBottom: 16,
        border: `1px solid ${isError ? "var(--red)" : "var(--border-subtle)"}`,
        background: isError ? "var(--danger-bg)" : "var(--bg-base)",
        color: isError ? "var(--red)" : "var(--text-2)",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{children}</div>
      {action}
    </div>
  );
}

export function ForeshadowingBoard({ novelId }: { novelId: string }) {
  const [items, setItems] = useState<Foreshadowing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = (): void => {
    setLoading(true);
    setError(null);
    api<Foreshadowing[]>(`/api/v1/novels/${novelId}/foreshadowings`)
      .then((resp: any) => setItems(resp.data || []))
      .catch((e: unknown) => setError(String((e as { message?: string })?.message ?? e) || "加载伏笔失败"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [novelId]);

  const planted = items.filter(i => i.status === "planted");
  const resolved = items.filter(i => i.status === "resolved");

  const plantedPager = usePagination({ items: planted, pageSize: 10, mode: "client" });
  const resolvedPager = usePagination({ items: resolved, pageSize: 10, mode: "client" });

  return (
    <>
      {loading && (
        <Banner tone="info">
          <Loader2 size={16} />
          正在加载伏笔…
        </Banner>
      )}
      {!loading && error && (
        <Banner
          tone="error"
          action={
            <button className="btn-sm btn-ghost" onClick={load}>
              重试
            </button>
          }
        >
          <AlertTriangle size={16} />
          {error}
        </Banner>
      )}
      <div className="grid grid-2">
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <Lightbulb size={16} />
            种植中 ({planted.length})
          </div>
        </div>
        {plantedPager.pageData.map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
            <small style={{ color: "var(--text-2)" }}>计划第{f.planned_resolve_chapter}章回收</small>
          </div>
        ))}
        {!planted.length && (
          <div className="empty" style={{ padding: "24px 16px" }}>
            <p style={{ color: "var(--text-2)", fontSize: 13 }}>暂无种植伏笔</p>
          </div>
        )}
        <Pagination
          page={plantedPager.page}
          pageSize={plantedPager.pageSize}
          total={planted.length}
          onPageChange={plantedPager.setPage}
          onPageSizeChange={plantedPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>
      <div className="card">
        <div className="card-head">
          <div className="card-title">
            <CheckCircle size={16} />
            已回收 ({resolved.length})
          </div>
        </div>
        {resolvedPager.pageData.map(f => (
          <div key={f.id} style={{ padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
            <p style={{ fontSize: 13, margin: 0 }}>{f.content}</p>
          </div>
        ))}
        {!resolved.length && (
          <div className="empty" style={{ padding: "24px 16px" }}>
            <p style={{ color: "var(--text-2)", fontSize: 13 }}>暂无已回收伏笔</p>
          </div>
        )}
        <Pagination
          page={resolvedPager.page}
          pageSize={resolvedPager.pageSize}
          total={resolved.length}
          onPageChange={resolvedPager.setPage}
          onPageSizeChange={resolvedPager.setPageSize}
          pageSizeOptions={[10, 20, 50, 100]}
        />
      </div>
    </div>
    </>
  );
}
