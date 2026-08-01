/**
 * Constraint Manager page - V7
 * 
 * Manage story constraints and rules.
 */
import { useState, useEffect } from 'react';
import {
  Shield, Plus, Trash2, AlertTriangle, CheckCircle,
  Info, XCircle, Settings,
} from 'lucide-react';
import brainApi from '../api/client';
import type { Constraint } from '../types';

interface ConstraintManagerProps {
  novelId: string;
}

const CONSTRAINT_TYPES = [
  { value: 'character', label: 'Character' },
  { value: 'plot', label: 'Plot' },
  { value: 'world', label: 'World' },
  { value: 'style', label: 'Style' },
  { value: 'theme', label: 'Theme' },
  { value: 'pacing', label: 'Pacing' },
];

const SEVERITY_CONFIG = {
  info: { color: 'text-blue-600', bg: 'bg-blue-50', border: 'border-blue-200', icon: Info },
  warning: { color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-200', icon: AlertTriangle },
  error: { color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-200', icon: XCircle },
  blocking: { color: 'text-red-700', bg: 'bg-red-100', border: 'border-red-300', icon: Shield },
};

export function ConstraintManager({ novelId }: ConstraintManagerProps) {
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [selectedType, setSelectedType] = useState('character');
  const [selectedSeverity, setSelectedSeverity] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Create form
  const [formData, setFormData] = useState({
    constraint_name: '',
    description: '',
    constraint_value: '{}',
    severity: 'warning',
    check_method: 'ai_review',
    priority: 50,
  });
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    loadConstraints();
  }, [novelId, selectedType, selectedSeverity]);

  const loadConstraints = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listConstraints(novelId, {
        constraint_type: selectedType,
        severity: selectedSeverity || undefined,
        limit: 200,
      });
      setConstraints(data);
    } catch (err: any) {
      console.error('Failed to load constraints:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      setFormError(null);
      let parsedValue: Record<string, any>;
      try {
        parsedValue = JSON.parse(formData.constraint_value);
      } catch {
        setFormError('Invalid JSON in constraint value');
        return;
      }

      await brainApi.createConstraint(novelId, {
        constraint_type: selectedType,
        constraint_name: formData.constraint_name,
        description: formData.description || undefined,
        constraint_value: parsedValue,
        severity: formData.severity,
        check_method: formData.check_method,
        priority: formData.priority,
      });

      setShowCreateModal(false);
      setFormData({
        constraint_name: '',
        description: '',
        constraint_value: '{}',
        severity: 'warning',
        check_method: 'ai_review',
        priority: 50,
      });
      loadConstraints();
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  const handleDelete = async (constraintId: string) => {
    if (!confirm('Delete this constraint?')) return;
    try {
      await brainApi.deleteConstraint(novelId, constraintId);
      loadConstraints();
    } catch (err: any) {
      console.error('Failed to delete constraint:', err);
    }
  };

  const getSeverityConfig = (severity: string) => {
    return SEVERITY_CONFIG[severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.warning;
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="h-7 w-7 text-purple-600" />
            Constraint Manager
          </h1>
          <p className="text-gray-500 mt-1">
            Define and enforce story constraints and rules
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          Add Constraint
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex gap-2 border-b border-gray-200 flex-1">
          {CONSTRAINT_TYPES.map((type) => (
            <button
              key={type.value}
              onClick={() => setSelectedType(type.value)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                selectedType === type.value
                  ? 'border-purple-600 text-purple-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {['all', 'info', 'warning', 'error', 'blocking'].map((sev) => (
            <button
              key={sev}
              onClick={() => setSelectedSeverity(sev === 'all' ? null : sev)}
              className={`px-3 py-1.5 text-sm rounded-lg border ${
                (sev === 'all' && !selectedSeverity) || selectedSeverity === sev
                  ? 'bg-purple-600 text-white border-purple-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {sev.charAt(0).toUpperCase() + sev.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Constraints List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600" />
          </div>
        ) : constraints.length === 0 ? (
          <div className="text-center py-12">
            <Shield className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <p className="text-gray-500">No constraints found</p>
            <p className="text-sm text-gray-400 mt-1">
              Create your first {selectedType} constraint
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {constraints.map((constraint) => {
              const sevConfig = getSeverityConfig(constraint.severity);
              const SevIcon = sevConfig.icon;
              return (
                <div key={constraint.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <div className={`p-1.5 rounded ${sevConfig.bg}`}>
                          <SevIcon className={`h-4 w-4 ${sevConfig.color}`} />
                        </div>
                        <h3 className="font-medium text-gray-900">
                          {constraint.name}
                        </h3>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${sevConfig.bg} ${sevConfig.color}`}>
                          {constraint.severity}
                        </span>
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                          Priority {constraint.priority}
                        </span>
                        {constraint.violation_count > 0 && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-600">
                            {constraint.violation_count} violations
                          </span>
                        )}
                      </div>
                      {constraint.description && (
                        <p className="text-sm text-gray-500 mt-2 ml-10">
                          {constraint.description}
                        </p>
                      )}
                      <div className="mt-2 ml-10">
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                            View constraint details
                          </summary>
                          <pre className="mt-2 p-3 bg-gray-50 rounded text-xs text-gray-600 overflow-x-auto">
                            {JSON.stringify(constraint.value, null, 2)}
                          </pre>
                        </details>
                      </div>
                      <div className="flex items-center gap-4 mt-2 ml-10 text-xs text-gray-400">
                        <span>Check method: {constraint.check_method}</span>
                        {constraint.last_violation_at && (
                          <span>Last violation: {new Date(constraint.last_violation_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => handleDelete(constraint.id)}
                      className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Add {selectedType} Constraint
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Constraint Name
                </label>
                <input
                  type="text"
                  value={formData.constraint_name}
                  onChange={(e) => setFormData({ ...formData, constraint_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  placeholder="e.g., No plot armor"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  placeholder="Describe the constraint..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Constraint Value (JSON)
                </label>
                <textarea
                  value={formData.constraint_value}
                  onChange={(e) => setFormData({ ...formData, constraint_value: e.target.value })}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 font-mono text-sm"
                  placeholder='{"rule": "value"}'
                />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Severity
                  </label>
                  <select
                    value={formData.severity}
                    onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    <option value="info">Info</option>
                    <option value="warning">Warning</option>
                    <option value="error">Error</option>
                    <option value="blocking">Blocking</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Check Method
                  </label>
                  <select
                    value={formData.check_method}
                    onChange={(e) => setFormData({ ...formData, check_method: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    <option value="ai_review">AI Review</option>
                    <option value="regex">Regex</option>
                    <option value="manual">Manual</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Priority
                  </label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={formData.priority}
                    onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
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
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
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

export default ConstraintManager;
