/**
 * Cost Monitor page - V7 Sprint 3
 * 
 * Monitor cost budgets, usage, and alerts.
 */
import { useState, useEffect } from 'react';
import {
  DollarSign, TrendingUp, AlertTriangle, CheckCircle,
  Plus, Settings, Zap, Clock,
} from 'lucide-react';
import brainApi from '../api/client';

interface CostMonitorProps {
  novelId: string;
}

interface Budget {
  id: string;
  budget_type: string;
  budget_scope: string;
  limit_cny: number;
  spent_cny: number;
  remaining_cny: number;
  usage_percentage: number;
  limit_tokens: number;
  spent_tokens: number;
  remaining_tokens: number;
  token_usage_percentage: number;
  period_start: string;
  period_end: string;
  action_on_exceed: string;
  is_active: boolean;
  description: string;
}

export function CostMonitor({ novelId }: CostMonitorProps) {
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Create form
  const [formData, setFormData] = useState({
    budget_type: 'monthly',
    budget_scope: 'novel',
    limit_cny: 100,
    limit_tokens: 1000000,
    action_on_exceed: 'notify',
    description: '',
  });

  useEffect(() => {
    loadBudgets();
  }, [novelId]);

  const loadBudgets = async () => {
    try {
      setLoading(true);
      // 接真实 API：预算列表 + 汇总（后端 cost.py 已就绪）
      const [budgetList, summaryData] = await Promise.all([
        brainApi.listBudgets(novelId),
        brainApi.getCostSummary(novelId),
      ]);
      setBudgets(budgetList || []);
      setSummary(summaryData || null);
    } catch (err: any) {
      console.error('Failed to load budgets:', err);
      setBudgets([]);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBudget = async () => {
    try {
      await brainApi.createBudget(novelId, {
        budget_type: formData.budget_type,
        budget_scope: formData.budget_scope,
        limit_cny: formData.limit_cny,
        limit_tokens: formData.limit_tokens,
        action_on_exceed: formData.action_on_exceed,
        description: formData.description,
      });
      setShowCreateModal(false);
      setFormData({
        budget_type: 'monthly',
        budget_scope: 'novel',
        limit_cny: 100,
        limit_tokens: 1000000,
        action_on_exceed: 'notify',
        description: '',
      });
      await loadBudgets();
    } catch (err: any) {
      console.error('Failed to create budget:', err);
    }
  };

  const getUsageColor = (percentage: number) => {
    if (percentage >= 95) return 'text-red-600';
    if (percentage >= 80) return 'text-amber-600';
    if (percentage >= 50) return 'text-blue-600';
    return 'text-green-600';
  };

  const getProgressColor = (percentage: number) => {
    if (percentage >= 95) return 'bg-red-500';
    if (percentage >= 80) return 'bg-amber-500';
    if (percentage >= 50) return 'bg-blue-500';
    return 'bg-green-500';
  };

  const getStatusBadge = (percentage: number) => {
    if (percentage >= 95) {
      return (
        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-700 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" />
          Critical
        </span>
      );
    }
    if (percentage >= 80) {
      return (
        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">
          <AlertTriangle className="h-3 w-3" />
          Warning
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700 flex items-center gap-1">
        <CheckCircle className="h-3 w-3" />
        Healthy
      </span>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <DollarSign className="h-7 w-7 text-emerald-600" />
            Cost Monitor
          </h1>
          <p className="text-gray-500 mt-1">
            Track and manage your AI generation costs
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          New Budget
        </button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Budget</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  ¥{summary.total_budget_cny.toFixed(2)}
                </p>
              </div>
              <div className="p-3 bg-emerald-50 rounded-lg">
                <DollarSign className="h-6 w-6 text-emerald-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Spent</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  ¥{summary.total_spent_cny.toFixed(2)}
                </p>
              </div>
              <div className="p-3 bg-blue-50 rounded-lg">
                <TrendingUp className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Remaining</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  ¥{summary.total_remaining_cny.toFixed(2)}
                </p>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Usage</p>
                <p className={`text-2xl font-bold mt-1 ${getUsageColor(summary.usage_percentage)}`}>
                  {summary.usage_percentage.toFixed(1)}%
                </p>
              </div>
              <div className="p-3 bg-purple-50 rounded-lg">
                <Zap className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Overall Progress */}
      {summary && (
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">Overall Budget Usage</h2>
            {getStatusBadge(summary.usage_percentage)}
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className={`h-4 rounded-full transition-all ${getProgressColor(summary.usage_percentage)}`}
              style={{ width: `${Math.min(summary.usage_percentage, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-sm text-gray-500">
            <span>¥{summary.total_spent_cny.toFixed(2)} spent</span>
            <span>¥{summary.total_remaining_cny.toFixed(2)} remaining</span>
          </div>
        </div>
      )}

      {/* Budgets List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div className="p-5 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Active Budgets</h2>
        </div>
        
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600" />
          </div>
        ) : budgets.length === 0 ? (
          <div className="text-center py-12">
            <DollarSign className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <p className="text-gray-500">No budgets configured</p>
            <p className="text-sm text-gray-400 mt-1">
              Create your first budget to track costs
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {budgets.map((budget) => (
              <div key={budget.id} className="p-5 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium text-gray-900 capitalize">
                        {budget.budget_type.replace(/_/g, ' ')}
                      </h3>
                      {getStatusBadge(budget.usage_percentage)}
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600 capitalize">
                        {budget.budget_scope}
                      </span>
                    </div>
                    {budget.description && (
                      <p className="text-sm text-gray-500 mt-1">
                        {budget.description}
                      </p>
                    )}
                    
                    {/* Cost progress */}
                    <div className="mt-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Cost</span>
                        <span className="font-medium">
                          ¥{budget.spent_cny.toFixed(2)} / ¥{budget.limit_cny.toFixed(2)}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${getProgressColor(budget.usage_percentage)}`}
                          style={{ width: `${Math.min(budget.usage_percentage, 100)}%` }}
                        />
                      </div>
                    </div>

                    {/* Token progress */}
                    <div className="mt-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Tokens</span>
                        <span className="font-medium">
                          {budget.spent_tokens.toLocaleString()} / {budget.limit_tokens.toLocaleString()}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${getProgressColor(budget.token_usage_percentage)}`}
                          style={{ width: `${Math.min(budget.token_usage_percentage, 100)}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {budget.period_start && new Date(budget.period_start).toLocaleDateString()}
                        {' → '}
                        {budget.period_end && new Date(budget.period_end).toLocaleDateString()}
                      </span>
                      <span>Action on exceed: {budget.action_on_exceed}</span>
                    </div>
                  </div>
                  <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded">
                    <Settings className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Create New Budget</h2>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Budget Type
                  </label>
                  <select
                    value={formData.budget_type}
                    onChange={(e) => setFormData({ ...formData, budget_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="weekly">Weekly</option>
                    <option value="daily">Daily</option>
                    <option value="chapter">Per Chapter</option>
                    <option value="generation">Generation</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Action on Exceed
                  </label>
                  <select
                    value={formData.action_on_exceed}
                    onChange={(e) => setFormData({ ...formData, action_on_exceed: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  >
                    <option value="notify">Notify Only</option>
                    <option value="warn">Warn</option>
                    <option value="block">Block Generation</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Cost Limit (¥)
                </label>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.limit_cny}
                  onChange={(e) => setFormData({ ...formData, limit_cny: parseFloat(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Token Limit
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.limit_tokens}
                  onChange={(e) => setFormData({ ...formData, limit_tokens: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description (optional)
                </label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                  placeholder="Budget description..."
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateBudget}
                className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CostMonitor;
