/**
 * V7 TypeScript type definitions.
 */

// Common types
export interface PaginationParams {
  skip?: number;
  limit?: number;
}

export interface SuccessResponse {
  success: boolean;
  message?: string;
}

// Brain Overview
export interface BrainOverview {
  novel_id: string;
  states: {
    by_type: Record<string, number>;
    total: number;
    pending_review: number;
  };
  goals: {
    total: number;
    completed: number;
    in_progress: number;
    pending: number;
  };
  constraints: {
    total: number;
    active: number;
  };
  latest_version: Version | null;
  recent_events: EventItem[];
}

// Story States
export interface StoryState {
  id: string;
  key: string;
  value: Record<string, any>;
  confidence: number;
  version: number;
  source: string;
  is_pending_review: boolean;
  updated_at?: string;
}

export interface StateCreateRequest {
  state_type: string;
  state_key: string;
  state_value: Record<string, any>;
  confidence?: number;
  source?: string;
  reason?: string;
}

export interface StateUpdateResponse {
  action: 'updated' | 'pending_review' | 'created' | 'discarded';
  state: StoryState | null;
  confidence: number;
  reason?: string;
}

// Goals
export interface Goal {
  id: string;
  name: string;
  type: string;
  description?: string;
  parent_goal_id?: string;
  order: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  progress: number;
  target_chapter?: number;
  completed_chapter?: number;
  priority: number;
  confidence: number;
}

export interface GoalCreateRequest {
  goal_type: string;
  goal_name: string;
  description?: string;
  parent_goal_id?: string;
  goal_order?: number;
  target_chapter?: number;
  priority?: number;
  confidence?: number;
  metadata?: Record<string, any>;
}

export interface GoalUpdateRequest {
  goal_name?: string;
  description?: string;
  status?: string;
  progress?: number;
  priority?: number;
}

export interface GoalTreeNode {
  id: string;
  name: string;
  type: string;
  status: string;
  progress: number;
  priority: number;
  children: GoalTreeNode[];
}

// Constraints
export interface Constraint {
  id: string;
  type: string;
  name: string;
  description?: string;
  value: Record<string, any>;
  severity: 'info' | 'warning' | 'error' | 'blocking';
  check_method: string;
  priority: number;
  violation_count: number;
  last_violation_at?: string;
}

export interface ConstraintCreateRequest {
  constraint_type: string;
  constraint_name: string;
  description?: string;
  constraint_value: Record<string, any>;
  severity?: string;
  check_method?: string;
  priority?: number;
}

export interface ConstraintUpdateRequest {
  constraint_name?: string;
  description?: string;
  constraint_value?: Record<string, any>;
  severity?: string;
  priority?: number;
  is_active?: boolean;
}

// Versions
export interface Version {
  id: string;
  version_number: number;
  version_type: string;
  description?: string;
  branch_name?: string;
  tag_name?: string;
  created_by: string;
  created_at?: string;
}

export interface Snapshot {
  id: string;
  snapshot_type: string;
  description?: string;
  size_bytes?: number;
  created_at?: string;
}

export interface RollbackRequest {
  snapshot_id: string;
  reason?: string;
}

export interface RollbackResponse {
  version_id: string;
  version_number: number;
  snapshot_id: string;
  status: string;
  note: string;
}

// Decisions
export interface DecisionLog {
  id: string;
  decision_type: string;
  decision: string;
  reason?: string;
  confidence: number;
  permission_level: string;
  status: string;
  decided_by: string;
  created_at?: string;
}

// Events
export interface EventItem {
  id: string;
  type: string;
  name: string;
  category: string;
  severity: 'debug' | 'info' | 'warning' | 'error' | 'critical';
  description?: string;
  source: string;
  time?: string;
  data: Record<string, any>;
}

// Trace / Runs
export interface AgentRun {
  id: string;
  run_type: string;
  status: 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  total_tokens: number;
  total_cost: number;
  step_count: number;
  chapter_number?: number;
}

export interface TraceStep {
  id: string;
  step_name: string;
  step_type: string;
  step_order: number;
  status: 'running' | 'completed' | 'failed' | 'skipped';
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  input_summary?: string;
  output_summary?: string;
  tokens_input: number;
  tokens_output: number;
  cost: number;
  model?: string;
  confidence?: number;
}
