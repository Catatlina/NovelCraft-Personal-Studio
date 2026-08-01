/**
 * V7 API client.
 */
import type {
  BrainOverview,
  StoryState,
  StateCreateRequest,
  StateUpdateRequest,
  Goal,
  GoalCreateRequest,
  GoalUpdateRequest,
  GoalTreeResponse,
  Constraint,
  ConstraintCreateRequest,
  ConstraintUpdateRequest,
  Version,
  VersionCreateRequest,
  Snapshot,
  RollbackRequest,
  RollbackResponse,
  DecisionLogItem,
  EventItem,
  Run,
  TraceStep,
} from '../types';

const API_BASE = '/api';

class BrainApiClient {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: {
        'Content-Type': 'application/json',
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ── Brain Overview ────────────────────────────────────────────────────

  async getOverview(novelId: string): Promise<BrainOverview> {
    return this.request<BrainOverview>(`/v7/brain/${novelId}/overview`);
  }

  // ── States ────────────────────────────────────────────────────────────

  async listStates(
    novelId: string,
    stateType?: string,
    params?: { limit?: number; offset?: number }
  ): Promise<{ items: StoryState[]; total: number }> {
    const query = new URLSearchParams();
    if (stateType) query.set('state_type', stateType);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    return this.request(`/v7/brain/${novelId}/states?${query.toString()}`);
  }

  async createState(novelId: string, data: StateCreateRequest): Promise<StoryState> {
    return this.request(`/v7/brain/${novelId}/states`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateState(novelId: string, stateId: string, data: StateUpdateRequest): Promise<StoryState> {
    return this.request(`/v7/brain/${novelId}/states/${stateId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async approveState(novelId: string, stateId: string): Promise<StoryState> {
    return this.request(`/v7/brain/${novelId}/states/${stateId}/approve`, {
      method: 'POST',
    });
  }

  async rejectState(novelId: string, stateId: string): Promise<StoryState> {
    return this.request(`/v7/brain/${novelId}/states/${stateId}/reject`, {
      method: 'POST',
    });
  }

  async getPendingReview(novelId: string): Promise<StoryState[]> {
    return this.request(`/v7/brain/${novelId}/states/pending-review`);
  }

  async getStateChanges(novelId: string, stateId: string): Promise<any[]> {
    return this.request(`/v7/brain/${novelId}/states/${stateId}/changes`);
  }

  // ── Goals ─────────────────────────────────────────────────────────────

  async listGoals(
    novelId: string,
    params?: { goal_type?: string; status?: string; limit?: number }
  ): Promise<Goal[]> {
    const query = new URLSearchParams();
    if (params?.goal_type) query.set('goal_type', params.goal_type);
    if (params?.status) query.set('status', params.status);
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/brain/${novelId}/goals?${query.toString()}`);
  }

  async getGoalTree(novelId: string, goalType?: string): Promise<GoalTreeResponse> {
    const query = new URLSearchParams();
    if (goalType) query.set('goal_type', goalType);
    return this.request(`/v7/brain/${novelId}/goals/tree?${query.toString()}`);
  }

  async createGoal(novelId: string, data: GoalCreateRequest): Promise<Goal> {
    return this.request(`/v7/brain/${novelId}/goals`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateGoal(novelId: string, goalId: string, data: GoalUpdateRequest): Promise<Goal> {
    return this.request(`/v7/brain/${novelId}/goals/${goalId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteGoal(novelId: string, goalId: string): Promise<void> {
    return this.request(`/v7/brain/${novelId}/goals/${goalId}`, {
      method: 'DELETE',
    });
  }

  // ── Constraints ───────────────────────────────────────────────────────

  async listConstraints(
    novelId: string,
    params?: { constraint_type?: string; severity?: string; limit?: number }
  ): Promise<Constraint[]> {
    const query = new URLSearchParams();
    if (params?.constraint_type) query.set('constraint_type', params.constraint_type);
    if (params?.severity) query.set('severity', params.severity);
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/brain/${novelId}/constraints?${query.toString()}`);
  }

  async createConstraint(novelId: string, data: ConstraintCreateRequest): Promise<Constraint> {
    return this.request(`/v7/brain/${novelId}/constraints`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateConstraint(novelId: string, constraintId: string, data: ConstraintUpdateRequest): Promise<Constraint> {
    return this.request(`/v7/brain/${novelId}/constraints/${constraintId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteConstraint(novelId: string, constraintId: string): Promise<void> {
    return this.request(`/v7/brain/${novelId}/constraints/${constraintId}`, {
      method: 'DELETE',
    });
  }

  // ── Versions ──────────────────────────────────────────────────────────

  async listVersions(
    novelId: string,
    params?: { limit?: number; branch?: string }
  ): Promise<Version[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.branch) query.set('branch_name', params.branch);
    return this.request(`/v7/brain/${novelId}/versions?${query.toString()}`);
  }

  async createVersion(novelId: string, data: VersionCreateRequest): Promise<Version> {
    return this.request(`/v7/brain/${novelId}/versions`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listSnapshots(
    novelId: string,
    params?: { limit?: number }
  ): Promise<Snapshot[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/brain/${novelId}/snapshots?${query.toString()}`);
  }

  async createSnapshot(novelId: string): Promise<Snapshot> {
    return this.request(`/v7/brain/${novelId}/snapshots`, {
      method: 'POST',
    });
  }

  async rollback(novelId: string, data: RollbackRequest): Promise<RollbackResponse> {
    return this.request(`/v7/brain/${novelId}/rollback`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ── Decisions ─────────────────────────────────────────────────────────

  async listDecisions(
    novelId: string,
    params?: { status?: string; decision_type?: string; limit?: number }
  ): Promise<DecisionLogItem[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set('status', params.status);
    if (params?.decision_type) query.set('decision_type', params.decision_type);
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/brain/${novelId}/decisions?${query.toString()}`);
  }

  async approveDecision(novelId: string, decisionId: string): Promise<any> {
    return this.request(`/v7/director/${novelId}/decisions/${decisionId}/approve`, {
      method: 'POST',
    });
  }

  async rejectDecision(novelId: string, decisionId: string): Promise<any> {
    return this.request(`/v7/director/${novelId}/decisions/${decisionId}/reject`, {
      method: 'POST',
    });
  }

  // ── Events ────────────────────────────────────────────────────────────

  async listEvents(
    novelId: string,
    params?: { severity?: string; event_category?: string; limit?: number }
  ): Promise<EventItem[]> {
    const query = new URLSearchParams();
    if (params?.severity) query.set('severity', params.severity);
    if (params?.event_category) query.set('event_category', params.event_category);
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/brain/${novelId}/events?${query.toString()}`);
  }

  // ── Trace ─────────────────────────────────────────────────────────────

  async listRuns(
    novelId: string,
    params?: { run_type?: string; status?: string; limit?: number }
  ): Promise<Run[]> {
    const query = new URLSearchParams();
    if (params?.run_type) query.set('run_type', params.run_type);
    if (params?.status) query.set('status', params.status);
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/trace/${novelId}/runs?${query.toString()}`);
  }

  async getRun(novelId: string, runId: string): Promise<Run> {
    return this.request(`/v7/trace/${novelId}/runs/${runId}`);
  }

  async listTraceSteps(
    novelId: string,
    runId: string,
    params?: { limit?: number }
  ): Promise<TraceStep[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    return this.request(`/v7/trace/${novelId}/runs/${runId}/steps?${query.toString()}`);
  }

  // ── Generation / Director ─────────────────────────────────────────────

  async generateChapter(
    novelId: string,
    data: { chapter_number: number; prompt?: string; outline?: string }
  ): Promise<any> {
    return this.request(`/v7/director/${novelId}/generate-chapter`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getPendingDecisions(novelId: string): Promise<{ decisions: any[]; count: number }> {
    return this.request(`/v7/director/${novelId}/decisions/pending`);
  }

  async getDirectorStatus(novelId: string): Promise<any> {
    return this.request(`/v7/director/${novelId}/status`);
  }
}

const brainApi = new BrainApiClient();
export default brainApi;
