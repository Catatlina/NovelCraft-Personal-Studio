import { useState } from "react";

export type PaginationMode = "client" | "server";

export interface UsePaginationOptions<T> {
  items?: T[];
  total?: number;
  pageSize?: number;
  mode: PaginationMode;
}

export interface ClientPaginationResult<T> {
  mode: "client";
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
  total: number;
  rangeStart: number;
  rangeEnd: number;
  pageData: T[];
}

export interface ServerPaginationResult {
  mode: "server";
  page: number;
  setPage: (page: number) => void;
  pageSize: number;
  setPageSize: (size: number) => void;
  totalPages: number;
  total: number;
  rangeStart: number;
  rangeEnd: number;
  pageData: undefined;
}

export type UsePaginationResult<T> = ClientPaginationResult<T> | ServerPaginationResult;

/**
 * Pagination state hook.
 * - "client": slices `items` locally and returns the current page slice plus
 *   range metadata. Changing page size resets to page 1.
 * - "server": keeps only page / pageSize state; `pageData` is `undefined` and
 *   the parent is expected to refetch via its own onPageChange / onPageSizeChange.
 */
// Overloaded signatures let TypeScript narrow the return type by the literal
// `mode` argument (it cannot narrow a plain union by a parameter value).
// Client mode guarantees `pageData: T[]`; server mode exposes `pageData: undefined`
// so callers are steered to refetch via their own handlers.
export function usePagination<T>(options: {
  items?: T[];
  total?: number;
  pageSize?: number;
  mode: "client";
}): ClientPaginationResult<T>;
export function usePagination<T>(options: {
  items?: T[];
  total?: number;
  pageSize?: number;
  mode: "server";
}): ServerPaginationResult;
export function usePagination<T>({
  items = [],
  total,
  pageSize = 10,
  mode,
}: UsePaginationOptions<T>): UsePaginationResult<T> {
  const [page, setPage] = useState<number>(1);
  const [pageSizeState, setPageSizeState] = useState<number>(pageSize);

  const setPageSize = (size: number): void => {
    setPageSizeState(size);
    setPage(1);
  };

  const resolvedTotal = mode === "client" ? items.length : total ?? 0;
  const totalPages = pageSizeState > 0 ? Math.ceil(resolvedTotal / pageSizeState) : 0;
  const safePage = Math.min(Math.max(page, 1), Math.max(totalPages, 1));
  const rangeStart = resolvedTotal === 0 ? 0 : (safePage - 1) * pageSizeState + 1;
  const rangeEnd = Math.min(safePage * pageSizeState, resolvedTotal);

  if (mode === "client") {
    const start = (safePage - 1) * pageSizeState;
    const pageData = items.slice(start, start + pageSizeState);
    return {
      mode,
      page: safePage,
      setPage,
      pageSize: pageSizeState,
      setPageSize,
      totalPages,
      total: resolvedTotal,
      rangeStart,
      rangeEnd,
      pageData,
    };
  }

  return {
    mode,
    page: safePage,
    setPage,
    pageSize: pageSizeState,
    setPageSize,
    totalPages,
    total: resolvedTotal,
    rangeStart,
    rangeEnd,
    pageData: undefined,
  };
}

export default usePagination;
