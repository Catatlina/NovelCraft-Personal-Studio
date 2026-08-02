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

export class V7ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'V7ApiError';
    this.status = status;
  }
}

class BrainApiClient {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers = new Headers(options?.headers);
    headers.set('Content-Type', 'application/json');

    const token = sessionStorage.getItem('nc_token');
    if (token) headers.set('Authorization', `Bearer ${token}`);

    const apiKey = sessionStorage.getItem('nc_api_key');
    const apiUrl = sessionStorage.getItem('nc_api_url');
    const model = sessionStorage.getItem('nc_model');
    if (apiKey) headers.set('X-Api-Key', apiKey);
    if (apiUrl) headers.set('X-Api-Base-Url', apiUrl);
    if (model) headers.set('X-Model', model);

    const requestInit: RequestInit = {
      ...options,
      headers,
      credentials: 'include',
    };

    let response = await fetch(`${API_BASE}${path}`, requestInit);

    // Keep V7 requests on the same refresh path as the rest of the app. The
    // previous client sent no JWT at all, so every protected V7 page rendered
    // as HTTP 401 even when the user was already logged in.
    if (response.status === 401 && token) {
      const { refreshAuthToken } = await import('../../lib/api');
      if (await refreshAuthToken()) {
        const refreshedToken = sessionStorage.getItem('nc_token');
        if (refreshedToken) headers.set('Authorization', `Bearer ${refreshedToken}`);
        response = await fetch(`${API_BASE}${path}`, requestInit);
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const message = error?.message || error?.detail ||
        (response.status === 401 ? '登录状态已失效，请重新登录' :
          response.status === 403 ? '没有访问该工程信息的权限' :
            `V7 请求失败（HTTP ${response.status}）`);
      throw new V7ApiError(response.status, message);
    }

    if (response.status === 204) return undefined as T;
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

  // ── Cost (Sprint 3 — 后端已就绪，前端接入) ───────────────────────────

  async listBudgets(
    novelId: string,
    params?: { budget_type?: string; budget_scope?: string; is_active?: boolean }
  ): Promise<any[]> {
    const query = new URLSearchParams();
    if (params?.budget_type) query.set('budget_type', params.budget_type);
    if (params?.budget_scope) query.set('budget_scope', params.budget_scope);
    if (params?.is_active !== undefined) query.set('is_active', String(params.is_active));
    const qs = query.toString();
    return this.request(`/v7/cost/${novelId}/budgets${qs ? `?${qs}` : ''}`);
  }

  async createBudget(
    novelId: string,
    data: {
      budget_type: string;
      budget_scope: string;
      limit_cny: number;
      limit_tokens?: number;
      period_days?: number;
      action_on_exceed?: string;
      description?: string;
    }
  ): Promise<any> {
    return this.request(`/v7/cost/${novelId}/budgets`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getBudget(novelId: string, budgetId: string): Promise<any> {
    return this.request(`/v7/cost/${novelId}/budgets/${budgetId}`);
  }

  async updateBudget(novelId: string, budgetId: string, data: Record<string, unknown>): Promise<any> {
    return this.request(`/v7/cost/${novelId}/budgets/${budgetId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteBudget(novelId: string, budgetId: string): Promise<any> {
    return this.request(`/v7/cost/${novelId}/budgets/${budgetId}`, {
      method: 'DELETE',
    });
  }

  async resetBudget(novelId: string, budgetId: string): Promise<any> {
    return this.request(`/v7/cost/${novelId}/budgets/${budgetId}/reset`, {
      method: 'POST',
    });
  }

  async getCostSummary(
    novelId: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<any> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString();
    return this.request(`/v7/cost/${novelId}/summary${qs ? `?${qs}` : ''}`);
  }

  async getCostStatsByDate(
    novelId: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<any> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString();
    return this.request(`/v7/cost/${novelId}/stats/daily${qs ? `?${qs}` : ''}`);
  }

  async getCostStatsByTaskType(
    novelId: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<any> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString();
    return this.request(`/v7/cost/${novelId}/stats/task-type${qs ? `?${qs}` : ''}`);
  }

  async getCrossVersionLedger(
    novelId: string,
    params?: { start_date?: string; end_date?: string }
  ): Promise<any> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    const qs = query.toString();
    return this.request(`/v7/cost/${novelId}/ledger${qs ? `?${qs}` : ''}`);
  }

  // ── Prompt versions (Sprint 3 — 后端已就绪，前端接入) ────────────────

  async listPromptNames(novelId?: string): Promise<{ total: number; prompt_names: string[] }> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/names${qs}`);
  }

  async listPromptVersions(
    params?: { prompt_name?: string; is_active?: boolean; skip?: number; limit?: number },
    novelId?: string
  ): Promise<{ total: number; skip: number; limit: number; versions: any[] }> {
    const query = new URLSearchParams();
    if (params?.prompt_name) query.set('prompt_name', params.prompt_name);
    if (params?.is_active !== undefined) query.set('is_active', String(params.is_active));
    if (params?.skip) query.set('skip', String(params.skip));
    if (params?.limit) query.set('limit', String(params.limit));
    if (novelId) query.set('novel_id', novelId);
    return this.request(`/v7/prompt/versions?${query.toString()}`);
  }

  async registerPromptVersion(
    data: {
      prompt_name: string;
      template: string;
      model?: string;
      description?: string;
      change_notes?: string;
      make_default?: boolean;
      force_new?: boolean;
      created_by?: string;
    },
    novelId?: string
  ): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/versions${qs}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getActivePromptVersion(promptName: string, novelId?: string): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/versions/active/${encodeURIComponent(promptName)}${qs}`);
  }

  async getPromptVersion(versionId: string, novelId?: string): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/versions/${versionId}${qs}`);
  }

  async setDefaultPromptVersion(versionId: string, novelId?: string): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/versions/${versionId}/default${qs}`, {
      method: 'POST',
    });
  }

  async deactivatePromptVersion(versionId: string, novelId?: string): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/versions/${versionId}/deactivate${qs}`, {
      method: 'POST',
    });
  }

  async listPromptExecutions(
    params?: { prompt_name?: string; status?: string; skip?: number; limit?: number },
    novelId?: string
  ): Promise<{ count: number; executions: any[] }> {
    const query = new URLSearchParams();
    if (params?.prompt_name) query.set('prompt_name', params.prompt_name);
    if (params?.status) query.set('status', params.status);
    if (params?.skip) query.set('skip', String(params.skip));
    if (params?.limit) query.set('limit', String(params.limit));
    if (novelId) query.set('novel_id', novelId);
    return this.request(`/v7/prompt/executions?${query.toString()}`);
  }

  async getPromptExecutionStats(promptName: string, novelId?: string): Promise<any> {
    const qs = novelId ? `?novel_id=${encodeURIComponent(novelId)}` : '';
    return this.request(`/v7/prompt/executions/stats/${encodeURIComponent(promptName)}${qs}`);
  }
}

const brainApi = new BrainApiClient();
export default brainApi;
