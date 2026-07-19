import React from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  danger: "btn-danger",
  ghost: "btn-ghost",
};

/**
 * Thin wrapper over the tokenized button classes defined in components.css.
 * Maps `variant` -> `.btn-<variant>` and `size="sm"` -> `.btn-sm`, then spreads
 * the remaining native <button> attributes (onClick, disabled, ...).
 */
export function Button({
  variant = "primary",
  size = "md",
  className,
  type = "button",
  ...rest
}: ButtonProps): React.ReactElement {
  const composed = [VARIANT_CLASS[variant], size === "sm" ? "btn-sm" : "", className]
    .filter((c): c is string => Boolean(c))
    .join(" ");
  return <button type={type} className={composed} {...rest} />;
}

export default Button;
