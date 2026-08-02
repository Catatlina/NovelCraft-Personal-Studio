/**
 * Prompt Manager page - V7 Sprint 3
 * 
 * Manage prompt versions and execution history.
 */
import { useState, useEffect } from 'react';
import {
  FileCode, Plus, Clock, CheckCircle, Copy, Eye,
  ChevronDown, ChevronUp, Zap, Tag,
} from 'lucide-react';
import brainApi from '../api/client';

interface PromptManagerProps {
  novelId: string;
}

interface PromptVersion {
  id: string;
  prompt_name: string;
  version: number;
  version_label: string;
  model: string;
  prompt_hash: string;
  description: string;
  change_notes: string;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
}

export function PromptManager({ novelId }: PromptManagerProps) {
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [templateText, setTemplateText] = useState('');
  const [createForm, setCreateForm] = useState({
    prompt_name: '',
    model: 'deepseek-chat',
    change_notes: '',
    template: '',
  });

  useEffect(() => {
    loadPrompts();
  }, [novelId]);

  const loadPrompts = async () => {
    try {
      setLoading(true);
      setError(null);
      const resp = await brainApi.listPromptVersions(
        { limit: 200 },
        novelId,
      );
      setPrompts(resp?.versions || []);
    } catch (err: any) {
      console.error('Failed to load prompts:', err);
      setError(err?.message || '加载失败');
      setPrompts([]);
    } finally {
      setLoading(false);
    }
  };

  // Group by prompt name
  const groupedPrompts = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.prompt_name]) {
      acc[prompt.prompt_name] = [];
    }
    acc[prompt.prompt_name].push(prompt);
    return acc;
  }, {} as Record<string, PromptVersion[]>);

  const handleSetDefault = async (promptId: string) => {
    try {
      await brainApi.setDefaultPromptVersion(promptId, novelId);
      await loadPrompts();
    } catch (err: any) {
      console.error('Failed to set default:', err);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleShowTemplate = async (versionId: string) => {
    try {
      const v = await brainApi.getPromptVersion(versionId, novelId);
      setTemplateText(v?.template || '（无模板内容）');
      setExpandedId(prev => (prev === versionId ? null : versionId));
    } catch (err: any) {
      console.error('Failed to load template:', err);
      setTemplateText('（模板加载失败）');
    }
  };

  const handleCreateVersion = async () => {
    if (!createForm.prompt_name.trim() || !createForm.template.trim()) return;
    try {
      await brainApi.registerPromptVersion(
        {
          prompt_name: createForm.prompt_name.trim(),
          template: createForm.template,
          model: createForm.model,
          change_notes: createForm.change_notes || undefined,
          make_default: false,
        },
        novelId,
      );
      setShowCreateModal(false);
      setCreateForm({ prompt_name: '', model: 'deepseek-chat', change_notes: '', template: '' });
      await loadPrompts();
    } catch (err: any) {
      console.error('Failed to create prompt version:', err);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileCode className="h-7 w-7 text-violet-600" />
            Prompt Manager
          </h1>
          <p className="text-gray-500 mt-1">
            Manage prompt versions and execution history
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          New Version
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Prompts</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {Object.keys(groupedPrompts).length}
              </p>
            </div>
            <div className="p-3 bg-violet-50 rounded-lg">
              <FileCode className="h-6 w-6 text-violet-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Versions</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {prompts.length}
              </p>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <Tag className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Active</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {prompts.filter(p => p.is_active).length}
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
              <p className="text-sm text-gray-500">Defaults</p>
              <p className="text-2xl font-bold text-amber-600 mt-1">
                {prompts.filter(p => p.is_default).length}
              </p>
            </div>
            <div className="p-3 bg-amber-50 rounded-lg">
              <Zap className="h-6 w-6 text-amber-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Prompt Groups */}
      {loading ? (
        <div className="flex items-center justify-center p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600" />
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <p className="text-gray-500">{error}</p>
          <button
            onClick={loadPrompts}
            className="mt-3 px-4 py-2 text-sm text-violet-600 border border-violet-200 rounded-lg hover:bg-violet-50"
          >
            重试
          </button>
        </div>
      ) : Object.keys(groupedPrompts).length === 0 ? (
        <div className="text-center py-12">
          <FileCode className="mx-auto h-12 w-12 text-gray-300 mb-4" />
          <p className="text-gray-500">暂无 prompt 版本记录</p>
          <p className="text-sm text-gray-400 mt-1">
            创建第一个版本以开始追踪 prompt 变更
          </p>
        </div>
      ) : (
      <div className="space-y-6">
        {Object.entries(groupedPrompts).map(([name, versions]) => (
          <div key={name} className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            <div className="p-5 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileCode className="h-5 w-5 text-violet-600" />
                  <h2 className="font-semibold text-gray-900 font-mono">{name}</h2>
                  <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-200 text-gray-600">
                    {versions.length} versions
                  </span>
                </div>
                <button
                  onClick={() => setSelectedPrompt(selectedPrompt === name ? null : name)}
                  className="text-sm text-violet-600 hover:text-violet-700"
                >
                  {selectedPrompt === name ? 'Collapse' : 'Expand all'}
                </button>
              </div>
            </div>

            <div className="divide-y divide-gray-100">
              {versions.map((version, index) => {
                const isExpanded = expandedId === version.id || selectedPrompt === name;
                return (
                  <div key={version.id}>
                    <div
                      className="p-4 cursor-pointer hover:bg-gray-50"
                      onClick={() => handleShowTemplate(version.id)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4 text-gray-400" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-gray-400" />
                          )}
                          <span className="font-mono text-sm font-medium text-gray-900">
                            {version.version_label}
                          </span>
                          {version.is_default && (
                            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-amber-100 text-amber-700 flex items-center gap-1">
                              <Zap className="h-3 w-3" />
                              Default
                            </span>
                          )}
                          {version.is_active ? (
                            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700">
                              Active
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-500">
                              Inactive
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-500">
                          <span className="font-mono text-xs">
                            {version.model}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {new Date(version.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      {version.change_notes && (
                        <p className="text-sm text-gray-500 mt-1 ml-7">
                          {version.change_notes}
                        </p>
                      )}
                    </div>

                    {isExpanded && (
                      <div className="px-4 pb-4 ml-7">
                        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-xs font-medium text-gray-500">
                              Hash: <code className="font-mono">{version.prompt_hash}</code>
                            </span>
                            <div className="flex gap-2">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleCopy(version.prompt_hash);
                                }}
                                className="p-1 text-gray-400 hover:text-gray-600"
                                title="Copy hash"
                              >
                                <Copy className="h-4 w-4" />
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void handleSetDefault(version.id);
                                }}
                                className="px-2 py-1 text-xs text-violet-600 border border-violet-200 rounded hover:bg-violet-50"
                                disabled={version.is_default}
                              >
                                {version.is_default ? 'Default' : 'Set as default'}
                              </button>
                            </div>
                          </div>
                          {version.description && (
                            <p className="text-sm text-gray-600 mb-3">
                              {version.description}
                            </p>
                          )}
                          <div className="text-xs text-gray-600 whitespace-pre-wrap font-mono max-h-40 overflow-y-auto">
                            {templateText || '（点击版本加载模板内容）'}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Create New Prompt Version</h2>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prompt Name
                </label>
                <input
                  type="text"
                  value={createForm.prompt_name}
                  onChange={(e) => setCreateForm({ ...createForm, prompt_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  placeholder="e.g., chapter_generation"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Model
                </label>
                <select
                  value={createForm.model}
                  onChange={(e) => setCreateForm({ ...createForm, model: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                >
                  <option value="deepseek-chat">DeepSeek Chat</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Change Notes
                </label>
                <textarea
                  rows={3}
                  value={createForm.change_notes}
                  onChange={(e) => setCreateForm({ ...createForm, change_notes: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  placeholder="What changed in this version?"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prompt Template
                </label>
                <textarea
                  rows={6}
                  value={createForm.template}
                  onChange={(e) => setCreateForm({ ...createForm, template: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 font-mono text-sm"
                  placeholder="Enter prompt template..."
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
                onClick={handleCreateVersion}
                disabled={!createForm.prompt_name.trim() || !createForm.template.trim()}
                className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed"
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

export default PromptManager;
