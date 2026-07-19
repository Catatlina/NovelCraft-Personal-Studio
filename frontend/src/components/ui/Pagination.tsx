import React, { useState } from "react";
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

export interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  mode?: "client" | "server";
}

const DEFAULT_PAGE_SIZE_OPTIONS: number[] = [10, 20, 50, 100];
const WINDOW_SIZE = 5;

/** Build a windowed list of page numbers centered on the current page. */
function buildWindow(current: number, totalPages: number): number[] {
  const start0 = Math.max(1, current - Math.floor(WINDOW_SIZE / 2));
  const end = Math.min(totalPages, start0 + WINDOW_SIZE - 1);
  const start = Math.max(1, end - WINDOW_SIZE + 1);
  const pages: number[] = [];
  for (let p = start; p <= end; p += 1) pages.push(p);
  return pages;
}

/**
 * Footer pagination control. Renders the "显示：start-end / 共total条" summary,
 * a page-size <select>, first / prev / next / last buttons (disabled at the
 * boundaries), a windowed list of page numbers, and a jump-to-page input.
 * Works for both client-side slicing and server-side fetching — the parent
 * drives the data through `onPageChange` / `onPageSizeChange`.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
}: PaginationProps): React.ReactElement {
  const totalPages = pageSize > 0 ? Math.ceil(total / pageSize) : 0;
  const safePage = Math.min(Math.max(page, 1), Math.max(totalPages, 1));
  const start = total === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const end = Math.min(safePage * pageSize, total);
  const [jumpValue, setJumpValue] = useState<string>("");

  const goTo = (target: number): void => {
    const clamped = Math.min(Math.max(target, 1), Math.max(totalPages, 1));
    if (clamped !== safePage) onPageChange(clamped);
  };

  const handleJump = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const parsed = Number(jumpValue);
    if (Number.isFinite(parsed) && parsed > 0) goTo(Math.trunc(parsed));
    setJumpValue("");
  };

  const handleSizeChange = (e: React.ChangeEvent<HTMLSelectElement>): void => {
    onPageSizeChange?.(Number(e.target.value));
  };

  const windowPages = totalPages > 0 ? buildWindow(safePage, totalPages) : [];

  return (
    <div className="pagination">
      <span className="pagination-info">
        显示：{start}-{end} / 共{total}条
      </span>

      {onPageSizeChange && (
        <label className="pagination-size">
          每页
          <select value={pageSize} onChange={handleSizeChange} aria-label="每页条数">
            {pageSizeOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </label>
      )}

      <button
        type="button"
        className="pagination-btn"
        onClick={() => goTo(1)}
        disabled={safePage <= 1}
        aria-label="首页"
      >
        <ChevronsLeft size={16} />
      </button>
      <button
        type="button"
        className="pagination-btn"
        onClick={() => goTo(safePage - 1)}
        disabled={safePage <= 1}
        aria-label="上一页"
      >
        <ChevronLeft size={16} />
      </button>

      {windowPages.map((p) => (
        <button
          type="button"
          key={p}
          className={`pagination-btn${p === safePage ? " active" : ""}`}
          onClick={() => goTo(p)}
          aria-current={p === safePage ? "page" : undefined}
        >
          {p}
        </button>
      ))}

      <button
        type="button"
        className="pagination-btn"
        onClick={() => goTo(safePage + 1)}
        disabled={safePage >= totalPages}
        aria-label="下一页"
      >
        <ChevronRight size={16} />
      </button>
      <button
        type="button"
        className="pagination-btn"
        onClick={() => goTo(totalPages)}
        disabled={safePage >= totalPages}
        aria-label="末页"
      >
        <ChevronsRight size={16} />
      </button>

      <form className="pagination-jump" onSubmit={handleJump}>
        跳至
        <input
          type="number"
          min={1}
          max={totalPages || 1}
          value={jumpValue}
          onChange={(e) => setJumpValue(e.target.value)}
          placeholder="__"
          aria-label="跳页"
        />
        页
      </form>
    </div>
  );
}

export default Pagination;
