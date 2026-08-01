/**
 * Goal Manager page - V7
 * 
 * Manage story goals with tree view and progress tracking.
 */
import { useState, useEffect } from 'react';
import {
  Target, Plus, Trash2, ChevronRight, ChevronDown,
  CheckCircle, Circle, Clock, AlertCircle,
} from 'lucide-react';
import brainApi from '../api/client';
import type { Goal, GoalTreeNode } from '../types';

interface GoalManagerProps {
  novelId: string;
}

const GOAL_TYPES = [
  { value: 'plot', label: 'Plot' },
  { value: 'character', label: 'Character' },
  { value: 'theme', label: 'Theme' },
  { value: 'world', label: 'World' },
  { value: 'pacing', label: 'Pacing' },
];

const STATUS_COLORS: Record<string, string> = {
  pending: 'text-gray-500',
  in_progress: 'text-blue-600',
  completed: 'text-green-600',
  failed: 'text-red-600',
  skipped: 'text-gray-400',
};

const STATUS_ICONS: Record<string, any> = {
  pending: Circle,
  in_progress: Clock,
  completed: CheckCircle,
  failed: AlertCircle,
  skipped: Circle,
};

export function GoalManager({ novelId }: GoalManagerProps) {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [goalTree, setGoalTree] = useState<GoalTreeNode[]>([]);
  const [selectedType, setSelectedType] = useState('plot');
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list');
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Create form
  const [formData, setFormData] = useState({
    goal_name: '',
    description: '',
    goal_order: 0,
    target_chapter: '',
    priority: 50,
    confidence: 0.8,
    parent_goal_id: '',
  });
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    loadGoals();
    if (viewMode === 'tree') {
      loadGoalTree();
    }
  }, [novelId, selectedType, viewMode]);

  const loadGoals = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listGoals(novelId, { goal_type: selectedType, limit: 200 });
      setGoals(data);
    } catch (err: any) {
      console.error('Failed to load goals:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadGoalTree = async () => {
    try {
      const data = await brainApi.getGoalTree(novelId, selectedType);
      setGoalTree(data.tree);
    } catch (err: any) {
      console.error('Failed to load goal tree:', err);
    }
  };

  const handleCreate = async () => {
    try {
      setFormError(null);
      await brainApi.createGoal(novelId, {
        goal_type: selectedType,
        goal_name: formData.goal_name,
        description: formData.description || undefined,
        goal_order: formData.goal_order,
        target_chapter: formData.target_chapter ? parseInt(formData.target_chapter) : undefined,
        priority: formData.priority,
        confidence: formData.confidence,
        parent_goal_id: formData.parent_goal_id || undefined,
      });

      setShowCreateModal(false);
      setFormData({
        goal_name: '',
        description: '',
        goal_order: 0,
        target_chapter: '',
        priority: 50,
        confidence: 0.8,
        parent_goal_id: '',
      });
      loadGoals();
      if (viewMode === 'tree') loadGoalTree();
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  const handleDelete = async (goalId: string) => {
    if (!confirm('Delete this goal?')) return;
    try {
      await brainApi.deleteGoal(novelId, goalId);
      loadGoals();
      if (viewMode === 'tree') loadGoalTree();
    } catch (err: any) {
      console.error('Failed to delete goal:', err);
    }
  };

  const toggleNode = (nodeId: string) => {
    const newExpanded = new Set(expandedNodes);
    if (newExpanded.has(nodeId)) {
      newExpanded.delete(nodeId);
    } else {
      newExpanded.add(nodeId);
    }
    setExpandedNodes(newExpanded);
  };

  const renderTreeNode = (node: GoalTreeNode, depth: number = 0) => {
    const StatusIcon = STATUS_ICONS[node.status] || Circle;
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;

    return (
      <div key={node.id}>
        <div
          className="flex items-center gap-2 py-2 px-3 hover:bg-gray-50 rounded cursor-pointer"
          style={{ paddingLeft: `${depth * 24 + 12}px` }}
          onClick={() => hasChildren && toggleNode(node.id)}
        >
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400" />
            )
          ) : (
            <div className="w-4" />
          )}
          <StatusIcon className={`h-4 w-4 ${STATUS_COLORS[node.status]}`} />
          <span className="flex-1 text-sm font-medium text-gray-900">
            {node.name}
          </span>
          <div className="flex items-center gap-2">
            <div className="w-24 bg-gray-200 rounded-full h-1.5">
              <div
                className="bg-blue-500 h-1.5 rounded-full"
                style={{ width: `${node.progress * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 w-10 text-right">
              {Math.round(node.progress * 100)}%
            </span>
          </div>
        </div>
        {isExpanded && hasChildren && (
          <div>
            {node.children.map((child) => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Target className="h-7 w-7 text-green-600" />
            Goal Manager
          </h1>
          <p className="text-gray-500 mt-1">
            Track story goals and their progress
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex border border-gray-300 rounded-lg overflow-hidden">
            <button
              onClick={() => setViewMode('list')}
              className={`px-3 py-1.5 text-sm ${
                viewMode === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              List
            </button>
            <button
              onClick={() => setViewMode('tree')}
              className={`px-3 py-1.5 text-sm ${
                viewMode === 'tree'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Tree
            </button>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Add Goal
          </button>
        </div>
      </div>

      {/* Type Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {GOAL_TYPES.map((type) => (
          <button
            key={type.value}
            onClick={() => setSelectedType(type.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              selectedType === type.value
                ? 'border-green-600 text-green-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {type.label}
          </button>
        ))}
      </div>

      {/* Goals Content */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600" />
          </div>
        ) : viewMode === 'list' ? (
          goals.length === 0 ? (
            <div className="text-center py-12">
              <Target className="mx-auto h-12 w-12 text-gray-300 mb-4" />
              <p className="text-gray-500">No goals found</p>
              <p className="text-sm text-gray-400 mt-1">
                Create your first {selectedType} goal
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {goals.map((goal) => {
                const StatusIcon = STATUS_ICONS[goal.status] || Circle;
                return (
                  <div key={goal.id} className="p-4 hover:bg-gray-50">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <StatusIcon className={`h-5 w-5 ${STATUS_COLORS[goal.status]}`} />
                          <h3 className="font-medium text-gray-900">{goal.name}</h3>
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                            Priority {goal.priority}
                          </span>
                        </div>
                        {goal.description && (
                          <p className="text-sm text-gray-500 mt-1 ml-8">
                            {goal.description}
                          </p>
                        )}
                        <div className="flex items-center gap-4 mt-2 ml-8">
                          <div className="flex items-center gap-2 flex-1 max-w-xs">
                            <div className="flex-1 bg-gray-200 rounded-full h-2">
                              <div
                                className="bg-green-500 h-2 rounded-full transition-all"
                                style={{ width: `${goal.progress * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500 w-10 text-right">
                              {Math.round(goal.progress * 100)}%
                            </span>
                          </div>
                          {goal.target_chapter && (
                            <span className="text-xs text-gray-400">
                              Target: Ch. {goal.target_chapter}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => handleDelete(goal.id)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          <div className="p-2">
            {goalTree.length === 0 ? (
              <div className="text-center py-12">
                <Target className="mx-auto h-12 w-12 text-gray-300 mb-4" />
                <p className="text-gray-500">No goals found</p>
              </div>
            ) : (
              goalTree.map((node) => renderTreeNode(node))
            )}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Add {selectedType} Goal
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Goal Name
                </label>
                <input
                  type="text"
                  value={formData.goal_name}
                  onChange={(e) => setFormData({ ...formData, goal_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  placeholder="e.g., Protagonist discovers the truth"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  placeholder="Describe the goal..."
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Target Chapter
                  </label>
                  <input
                    type="number"
                    value={formData.target_chapter}
                    onChange={(e) => setFormData({ ...formData, target_chapter: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                    placeholder="e.g., 25"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Priority (0-100)
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Confidence: {Math.round(formData.confidence * 100)}%
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={formData.confidence}
                  onChange={(e) => setFormData({ ...formData, confidence: parseFloat(e.target.value) })}
                  className="w-full"
                />
              </div>
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                  {formError}
                </div>
              )}
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
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

export default GoalManager;
