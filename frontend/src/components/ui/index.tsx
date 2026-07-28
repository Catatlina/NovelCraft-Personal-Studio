import React, { useState } from "react";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
}: {
  mode?: "client" | "server";
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="pagination" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}>
      <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>上一页</button>
      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
        第 {Math.min(page, pages)} / {pages} 页，共 {total} 条
      </span>
      <button type="button" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>下一页</button>
      <select
        aria-label="每页数量"
        value={pageSize}
        onChange={(event) => onPageSizeChange(Number(event.target.value))}
      >
        {pageSizeOptions.map((size) => <option key={size} value={size}>{size} 条/页</option>)}
      </select>
    </div>
  );
}

export type AccordionItem = {
  key: string;
  title: React.ReactNode;
  content: React.ReactNode;
  defaultOpen?: boolean;
};

function AccordionRow({ item }: { item: AccordionItem }) {
  const [open, setOpen] = useState(Boolean(item.defaultOpen));
  return (
    <div className="accordion-item" style={{ border: "1px solid var(--border-subtle)", borderRadius: 8, marginTop: 10 }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        style={{ width: "100%", justifyContent: "space-between", padding: "10px 12px" }}
      >
        <span>{item.title}</span><span aria-hidden>{open ? "−" : "+"}</span>
      </button>
      {open && <div style={{ padding: "4px 12px 12px" }}>{item.content}</div>}
    </div>
  );
}

export function Accordion({ items }: { items: AccordionItem[] }) {
  return <div>{items.map((item) => <AccordionRow key={item.key} item={item} />)}</div>;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "确认",
  cancelText = "取消",
  danger = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  if (!open) return null;
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="confirm-title" className="modal-backdrop">
      <div className="card" style={{ maxWidth: 440, margin: "15vh auto", padding: 20 }}>
        <h3 id="confirm-title">{title}</h3>
        <p>{message}</p>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button type="button" onClick={onCancel}>{cancelText}</button>
          <button type="button" className={danger ? "danger" : "primary"} onClick={onConfirm}>{confirmText}</button>
        </div>
      </div>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
}) {
  return (
    <div className="empty" style={{ textAlign: "center", padding: 28, color: "var(--text-muted)" }}>
      {icon && <div style={{ display: "flex", justifyContent: "center", marginBottom: 8 }}>{icon}</div>}
      <strong style={{ display: "block", color: "var(--text-primary)" }}>{title}</strong>
      {description && <p style={{ marginTop: 6 }}>{description}</p>}
    </div>
  );
}

export function Spinner({ label = "加载中…" }: { label?: string }) {
  return <div role="status" className="spinner"><span className="spin">◌</span> {label}</div>;
}

export type StepStatus = "done" | "active" | "waiting";
export type TimelineStep = {
  key: string;
  label: string;
  status: StepStatus;
  detail?: React.ReactNode;
};

export function StepTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol style={{ display: "grid", gap: 8, listStyle: "none", padding: 0 }}>
      {steps.map((step) => (
        <li key={step.key} className={`timeline-step ${step.status}`}>
          <strong>{step.status === "done" ? "✓" : step.status === "active" ? "●" : "○"} {step.label}</strong>
          {step.detail && <div style={{ marginTop: 6 }}>{step.detail}</div>}
        </li>
      ))}
    </ol>
  );
}

export const Card = ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div className="card" {...props}>{children}</div>;
export const Modal = ({ open, children }: { open: boolean; children?: React.ReactNode }) => open ? <div role="dialog">{children}</div> : null;
export const Button = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props} />;
export const Input = (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />;
export const Select = (props: React.SelectHTMLAttributes<HTMLSelectElement>) => <select {...props} />;
export const Badge = ({ children, ...props }: React.HTMLAttributes<HTMLSpanElement>) => <span className="badge" {...props}>{children}</span>;
export const Tab = (props: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" role="tab" {...props} />;
