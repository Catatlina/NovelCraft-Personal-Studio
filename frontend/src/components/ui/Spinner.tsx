import React from "react";

export type SpinnerSize = "sm" | "md" | "lg";
export type SpinnerVariant = "spinner" | "skeleton";

export interface SpinnerProps {
  size?: SpinnerSize;
  label?: string;
  variant?: SpinnerVariant;
  /** Extra class — primarily used to size the skeleton variant (e.g. width). */
  className?: string;
}

/**
 * Loading indicator.
 * - `variant="spinner"` renders a rotating ring tinted with `--brand-500`.
 * - `variant="skeleton"` renders a shimmering block; size its width via the
 *   `className` prop (e.g. a utility class or inline-style helper).
 */
export function Spinner({
  size = "md",
  label,
  variant = "spinner",
  className,
}: SpinnerProps): React.ReactElement {
  if (variant === "skeleton") {
    const composed = ["skeleton", className].filter(Boolean).join(" ");
    return <span className={composed} role="status" aria-label={label ?? "加载中"} />;
  }
  const composed = ["spinner", size, className].filter(Boolean).join(" ");
  return (
    <span className={composed} role="status" aria-label={label ?? "加载中"}>
      <span className="spinner-ring" />
      {label && <span className="spinner-label">{label}</span>}
    </span>
  );
}

export default Spinner;
