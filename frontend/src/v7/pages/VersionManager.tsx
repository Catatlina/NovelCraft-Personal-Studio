/**
 * Version Manager page - V7
 * 
 * Manage story versions and snapshots.
 */
import { useState, useEffect } from 'react';
import {
  GitBranch, Camera, RotateCcw, Plus, Tag, Clock,
  ChevronDown, ChevronUp,
} from 'lucide-react';
import brainApi from '../api/client';
import type { Version, Snapshot } from '../types';

interface VersionManagerProps {
  novelId: string;
}

export function VersionManager({ novelId }: VersionManagerProps) {
  const [versions, setVersions] = useState<Version[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [activeTab, setActiveTab] = useState<'versions' | 'snapshots'>('versions');
  const [loading, setLoading] = useState(true);
  const [showCreateVersionModal, setShowCreateVersionModal] = useState(false);
  const [showRollbackModal, setShowRollbackModal] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState<Snapshot | null>(null);

  // Create version form
  const [versionForm, setVersionForm] = useState({
    version_type: 'manual',
    description: '',
    branch_name: 'main',
    tag_name: '',
  });
  const [rollbackReason, setRollbackReason] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === 'versions') {
      loadVersions();
    } else {
      loadSnapshots();
    }
  }, [novelId, activeTab]);

  const loadVersions = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listVersions(novelId, { limit: 50 });
      setVersions(data);
    } catch (err: any) {
      console.error('Failed to load versions:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadSnapshots = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listSnapshots(novelId, { limit: 50 });
      setSnapshots(data);
    } catch (err: any) {
      console.error('Failed to load snapshots:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateVersion = async () => {
    try {
      setFormError(null);
      await brainApi.createVersion(novelId, {
        version_type: versionForm.version_type,
        description: versionForm.description || undefined,
        branch_name: versionForm.branch_name,
        tag_name: versionForm.tag_name || undefined,
      });

      setShowCreateVersionModal(false);
      setVersionForm({
        version_type: 'manual',
        description: '',
        branch_name: 'main',
        tag_name: '',
      });
      loadVersions();
    } catch (err: any) {
      setFormError(err.message);
    }
  };

  const handleCreateSnapshot = async () => {
    try {
      await brainApi.createSnapshot(novelId);
      loadSnapshots();
    } catch (err: any) {
      console.error('Failed to create snapshot:', err);
    }
  };

  const handleRollback = async () => {
    if (!selectedSnapshot) return;
    try {
      await brainApi.rollback(novelId, {
        snapshot_id: selectedSnapshot.id,
        reason: rollbackReason || undefined,
      });
      setShowRollbackModal(false);
      setSelectedSnapshot(null);
      setRollbackReason('');
      loadVersions();
    } catch (err: any) {
      console.error('Failed to rollback:', err);
    }
  };

  const formatSize = (bytes?: number) => {
    if (!bytes) return '-';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const versionTypeColors: Record<string, string> = {
    auto: 'bg-gray-100 text-gray-600',
    manual: 'bg-blue-100 text-blue-600',
    milestone: 'bg-green-100 text-green-600',
    rollback: 'bg-amber-100 text-amber-600',
    chapter: 'bg-purple-100 text-purple-600',
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch className="h-7 w-7 text-gray-600" />
            Version Control
          </h1>
          <p className="text-gray-500 mt-1">
            Track versions and snapshots of your story brain
          </p>
        </div>
        <div className="flex gap-3">
          {activeTab === 'versions' ? (
            <button
              onClick={() => setShowCreateVersionModal(true)}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              New Version
            </button>
          ) : (
            <button
              onClick={handleCreateSnapshot}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 flex items-center gap-2"
            >
              <Camera className="h-4 w-4" />
              Take Snapshot
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('versions')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-2 ${
            activeTab === 'versions'
              ? 'border-gray-800 text-gray-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <GitBranch className="h-4 w-4" />
          Versions
        </button>
        <button
          onClick={() => setActiveTab('snapshots')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors flex items-center gap-2 ${
            activeTab === 'snapshots'
              ? 'border-gray-800 text-gray-900'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Camera className="h-4 w-4" />
          Snapshots
        </button>
      </div>

      {/* Content */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-600" />
          </div>
        ) : activeTab === 'versions' ? (
          versions.length === 0 ? (
            <div className="text-center py-12">
              <GitBranch className="mx-auto h-12 w-12 text-gray-300 mb-4" />
              <p className="text-gray-500">No versions yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Create your first version
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {versions.map((version, index) => (
                <div key={version.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start gap-4">
                    <div className="flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full ${
                        index === 0 ? 'bg-green-500' : 'bg-gray-300'
                      }`} />
                      {index < versions.length - 1 && (
                        <div className="w-0.5 flex-1 bg-gray-200 mt-1" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-gray-900">
                          v{version.version_number}
                        </span>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          versionTypeColors[version.version_type] || 'bg-gray-100 text-gray-600'
                        }`}>
                          {version.version_type}
                        </span>
                        {version.tag_name && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">
                            <Tag className="h-3 w-3" />
                            {version.tag_name}
                          </span>
                        )}
                        {version.branch_name && (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-50 text-blue-600">
                            {version.branch_name}
                          </span>
                        )}
                      </div>
                      {version.description && (
                        <p className="text-sm text-gray-600 mt-1">
                          {version.description}
                        </p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {version.created_at && new Date(version.created_at).toLocaleString()}
                        </span>
                        <span>by {version.created_by}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          snapshots.length === 0 ? (
            <div className="text-center py-12">
              <Camera className="mx-auto h-12 w-12 text-gray-300 mb-4" />
              <p className="text-gray-500">No snapshots yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Take your first snapshot
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {snapshots.map((snapshot) => (
                <div key={snapshot.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-gray-100 rounded-lg">
                        <Camera className="h-5 w-5 text-gray-600" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">
                          {snapshot.snapshot_type} snapshot
                        </h3>
                        <p className="text-sm text-gray-500">
                          {snapshot.description || 'No description'}
                        </p>
                        <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {snapshot.created_at && new Date(snapshot.created_at).toLocaleString()}
                          </span>
                          <span>{formatSize(snapshot.size_bytes)}</span>
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedSnapshot(snapshot);
                        setShowRollbackModal(true);
                      }}
                      className="px-3 py-1.5 text-sm text-amber-600 border border-amber-300 rounded-lg hover:bg-amber-50 flex items-center gap-2"
                    >
                      <RotateCcw className="h-4 w-4" />
                      Rollback
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )
        )}
      </div>

      {/* Create Version Modal */}
      {showCreateVersionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">
                Create New Version
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Version Type
                </label>
                <select
                  value={versionForm.version_type}
                  onChange={(e) => setVersionForm({ ...versionForm, version_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-gray-500"
                >
                  <option value="manual">Manual</option>
                  <option value="milestone">Milestone</option>
                  <option value="chapter">Chapter</option>
                  <option value="auto">Auto</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={versionForm.description}
                  onChange={(e) => setVersionForm({ ...versionForm, description: e.target.value })}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-gray-500"
                  placeholder="What changed in this version?"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Branch
                  </label>
                  <input
                    type="text"
                    value={versionForm.branch_name}
                    onChange={(e) => setVersionForm({ ...versionForm, branch_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tag (optional)
                  </label>
                  <input
                    type="text"
                    value={versionForm.tag_name}
                    onChange={(e) => setVersionForm({ ...versionForm, tag_name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-500 focus:border-gray-500"
                    placeholder="e.g., v1.0"
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
                onClick={() => setShowCreateVersionModal(false)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateVersion}
                className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900"
              >
                Create Version
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rollback Modal */}
      {showRollbackModal && selectedSnapshot && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <RotateCcw className="h-5 w-5 text-amber-500" />
                Rollback to Snapshot
              </h2>
            </div>
            <div className="p-6 space-y-4">
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-sm text-amber-800">
                  <strong>Warning:</strong> Rolling back will create a new version
                  based on this snapshot. This action cannot be undone.
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500 mb-2">Snapshot:</p>
                <p className="font-medium text-gray-900">
                  {selectedSnapshot.snapshot_type} snapshot
                </p>
                <p className="text-sm text-gray-500">
                  {selectedSnapshot.created_at && new Date(selectedSnapshot.created_at).toLocaleString()}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Reason (optional)
                </label>
                <textarea
                  value={rollbackReason}
                  onChange={(e) => setRollbackReason(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                  placeholder="Why are you rolling back?"
                />
              </div>
            </div>
            <div className="p-6 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowRollbackModal(false);
                  setSelectedSnapshot(null);
                }}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRollback}
                className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700"
              >
                Rollback
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default VersionManager;
