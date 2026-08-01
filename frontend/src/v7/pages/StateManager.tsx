/**
 * State Manager page - V7
 * 
 * Manage story states with confidence gating.
 */
import { useState, useEffect } from 'react';
import {
  Database, Plus, Check, X, AlertTriangle, Clock, History,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import brainApi from '../api/client';
import type { StoryState } from '../types';

interface StateManagerProps {
  novelId: string;
}

const STATE_TYPES = [
  { value: 'global', label: 'Global' },
  { value: 'character', label: 'Character' },
  { value: 'world', label: 'World' },
  { value: 'plot', label: 'Plot' },
  { value: 'reader', label: 'Reader' },
];

export function StateManager({ novelId }: StateManagerProps) {
  const [states, setStates] = useState<StoryState[]>([]);
  const [selectedType, setSelectedType] = useState('global');
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedState, setSelectedState] = useState<StoryState | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  // Create form state
  const [formData, setFormData] = useState({
    state_key: '',
    state_value: '{}',
    confidence: 0.9,
    source: 'human',
    reason: '',
  });
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    loadStates();
  }, [novelId, selectedType]);

  const loadStates = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listStates(novelId, selectedType, { limit: 100 });
      setStates(data.items);
    } catch (err: any) {
      console.error('Failed to load states:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      setFormError(null);
      let parsedValue: Record<string, any>;
      try {
        parsedValue = JSON.parse(formData.state_value);
      } catch {
        setFormError('Invalid JSON in state value');
        return;
      }

      await brainApi.createState(novelId, {
        state_type: selectedType,
        state_key: formData.state_key,
        state_value: parsedValue,
        confidence: formData.confidence,
        source: formData.source,
        reason: formData.reason || undefined,
      });

      setShowCreateModal(false);
      setFormData({
        state_key: '',
        state_value: '{}',
        confidence: 0.9,
        source: 'human',
        reason: '',
      });
      loadStates();
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  const handleApprove = async (stateId: string) => {
    try {
      await brainApi.approveState(novelId, stateId);
      loadStates();
    } catch (err: any) {
      console.error('Failed to approve state:', err);
    }
  };

  const handleReject = async (stateId: string) => {
    try {
      await brainApi.rejectState(novelId, stateId);
      loadStates();
    } catch (err: any) {
      console.error('Failed to reject state:', err);
    }
  };

  const loadHistory = async (stateId: string) => {
    try {
      const data = await brainApi.getStateChanges(novelId, stateId);
      setHistory(data);
      setShowHistory(true);
    } catch (err: any) {
      console.error('Failed to load history:', err);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'text-green-600 bg-green-50';
    if (confidence >= 0.7) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.9) return 'High';
    if (confidence >= 0.7) return 'Medium';
    return 'Low';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Database className="h-7 w-7 text-blue-600" />
            State Manager
          </h1>
          <p className="text-gray-500 mt-1">
            Manage story states with confidence gating
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add State
        </button>
      </div>

      {/* Type Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {STATE_TYPES.map((type) => (
          <button
            key={type.value}
            onClick={() => setSelectedType(type.value)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              selectedType === type.value
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {type.label}
          </button>
        ))}
      </div>

      {/* States List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : states.length === 0 ? (
          <div className="text-center py-12">
            <Database className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <p className="text-gray-500">No states found</p>
            <p className="text-sm text-gray-400 mt-1">
              Create your first {selectedType} state
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {states.map((state) => (
              <div
                key={state.id}
                className="p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium text-gray-900">{state.key}</h3>
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConfidenceColor(state.confidence)}`}
                      >
                        {getConfidenceLabel(state.confidence)} ({Math.round(state.confidence * 100)}%)
                      </span>
                      {state.is_pending_review && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          Pending Review
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      Version {state.version} • Source: {state.source}
                    </p>
                    <pre className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600 overflow-x-auto max-h-24">
                      {JSON.stringify(state.value, null, 2)}
                    </pre>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => loadHistory(state.id)}
                      className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                      title="View history"
                    >
                      <History className="h-4 w-4" />
                    </button>
                    {state.is_pending_review && (
                      <>
                        <button
                          onClick={() => handleApprove(state.id)}
                          className="p-2 text-green-600 hover:bg-green-50 rounded"
                          title="Approve"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleReject(state.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded"
                          title="Reject"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Add {selectedType} State
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  State Key
                </label>
                <input
                  type="text"
                  value={formData.state_key}
                  onChange={(e) => setFormData({ ...formData, state_key: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="e.g., protagonist_status"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  State Value (JSON)
                </label>
                <textarea
                  value={formData.state_value}
                  onChange={(e) => setFormData({ ...formData, state_value: e.target.value })}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                  placeholder='{"key": "value"}'
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Source
                  </label>
                  <select
                    value={formData.source}
                    onChange={(e) => setFormData({ ...formData, source: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="human">Human</option>
                    <option value="ai_extracted">AI Extracted</option>
                    <option value="imported">Imported</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reason (optional)
                </label>
                <input
                  type="text"
                  value={formData.reason}
                  onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Why this change?"
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
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                State Change History
              </h2>
              <button
                onClick={() => setShowHistory(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              {history.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No history found</p>
              ) : (
                <div className="space-y-4">
                  {history.map((change, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className="w-3 h-3 rounded-full bg-blue-500" />
                        {index < history.length - 1 && (
                          <div className="w-0.5 flex-1 bg-gray-200" />
                        )}
                      </div>
                      <div className="flex-1 pb-4">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 capitalize">
                            {change.change_type}
                          </span>
                          <span className="text-sm text-gray-500">
                            {change.created_at && new Date(change.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">
                          Source: {change.source}
                          {change.reason && ` • ${change.reason}`}
                        </p>
                        {change.old_value && (
                          <div className="mt-2">
                            <p className="text-xs text-gray-400 mb-1">Old value:</p>
                            <pre className="p-2 bg-gray-50 rounded text-xs text-gray-500">
                              {JSON.stringify(change.old_value, null, 2)}
                            </pre>
                          </div>
                        )}
                        {change.new_value && (
                          <div className="mt-2">
                            <p className="text-xs text-gray-400 mb-1">New value:</p>
                            <pre className="p-2 bg-green-50 rounded text-xs text-green-700">
                              {JSON.stringify(change.new_value, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default StateManager;
