import React, { useEffect } from "react";

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Modal confirmation built on `.modal-overlay` + `.confirm-dialog`. Renders
 * nothing when `open` is false. Clicking the scrim or pressing Escape triggers
 * `onCancel`; the confirm button fires `onConfirm` then `onCancel`.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "确认",
  cancelText = "取消",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps): React.ReactElement | null {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const handleConfirm = (): void => {
    onConfirm();
    onCancel();
  };

  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        className={`confirm-dialog${danger ? " danger" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <h3 className="cd-title">{title}</h3>
        <p className="cd-message">{message}</p>
        <div className="cd-actions">
          <button type="button" className="cd-btn cd-btn-cancel" onClick={onCancel}>
            {cancelText}
          </button>
          <button type="button" className="cd-btn cd-btn-confirm" onClick={handleConfirm}>
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmDialog;
