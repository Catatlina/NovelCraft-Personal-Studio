import { useState } from 'react';

interface PaginationOptions<T> {
    items?: T[];
    pageSize?: number;
    mode?: string;
    total?: number;
}

export function usePagination<T>(opts: PaginationOptions<T>) {
    const items = opts.items || [];
    const [pageSize, setPageSize] = useState(opts.pageSize || 20);
    const [page, setPage] = useState(1);
    const totalItems = opts.total || items.length;
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    const paged = opts.mode === 'server' ? items : items.slice((page - 1) * pageSize, page * pageSize);
    return { page, setPage, totalPages, paged, pageSize, setPageSize, pageData: paged, total: totalItems };
}
