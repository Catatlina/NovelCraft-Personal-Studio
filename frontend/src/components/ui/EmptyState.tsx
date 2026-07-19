import React from "react";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

/**
 * Centered empty / zero-data placeholder built on the existing `.empty` base
 * class, with an illustration container (`.empty-ic`) and an optional action
 * slot (`.empty-action`).
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps): React.ReactElement {
  return (
    <div className="empty">
      {icon && <div className="empty-ic">{icon}</div>}
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div className="empty-action">{action}</div>}
    </div>
  );
}

export default EmptyState;
