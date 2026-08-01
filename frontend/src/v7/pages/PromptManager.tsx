/**
 * Prompt Manager page - V7 Sprint 3
 * 
 * Manage prompt versions and execution history.
 */
import { useState } from 'react';
import {
  FileCode, Plus, Clock, CheckCircle, Copy, Eye,
  ChevronDown, ChevronUp, Zap, Tag,
} from 'lucide-react';

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

const MOCK_PROMPTS: PromptVersion[] = [
  {
    id: 'prompt-1',
    prompt_name: 'chapter_generation',
    version: 3,
    version_label: 'v3.0',
    model: 'deepseek-chat',
    prompt_hash: 'a1b2c3d4e5f6g7h8',
    description: 'Main chapter generation prompt',
    change_notes: 'Improved character consistency instructions',
    is_active: true,
    is_default: true,
    created_at: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'prompt-2',
    prompt_name: 'chapter_generation',
    version: 2,
    version_label: 'v2.0',
    model: 'deepseek-chat',
    prompt_hash: 'b2c3d4e5f6g7h8i9',
    description: 'Main chapter generation prompt',
    change_notes: 'Added pacing guidelines',
    is_active: true,
    is_default: false,
    created_at: new Date(Date.now() - 7 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'prompt-3',
    prompt_name: 'chapter_generation',
    version: 1,
    version_label: 'v1.0',
    model: 'deepseek-chat',
    prompt_hash: 'c3d4e5f6g7h8i9j0',
    description: 'Initial version',
    change_notes: 'First version',
    is_active: false,
    is_default: false,
    created_at: new Date(Date.now() - 14 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'prompt-4',
    prompt_name: 'review_7dim',
    version: 2,
    version_label: 'v2.0',
    model: 'deepseek-chat',
    prompt_hash: 'd4e5f6g7h8i9j0k1',
    description: '7-dimensional review prompt',
    change_notes: 'Added consistency check dimension',
    is_active: true,
    is_default: true,
    created_at: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'prompt-5',
    prompt_name: 'deai_style',
    version: 1,
    version_label: 'v1.0',
    model: 'deepseek-chat',
    prompt_hash: 'e5f6g7h8i9j0k1l2',
    description: 'De-AI style transformation',
    change_notes: 'Initial version',
    is_active: true,
    is_default: true,
    created_at: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(),
  },
];

export function PromptManager({ novelId }: PromptManagerProps) {
  const [prompts, setPrompts] = useState<PromptVersion[]>(MOCK_PROMPTS);
  const [selectedPrompt, setSelectedPrompt] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Group by prompt name
  const groupedPrompts = prompts.reduce((acc, prompt) => {
    if (!acc[prompt.prompt_name]) {
      acc[prompt.prompt_name] = [];
    }
    acc[prompt.prompt_name].push(prompt);
    return acc;
  }, {} as Record<string, PromptVersion[]>);

  const handleSetDefault = (promptId: string) => {
    const prompt = prompts.find(p => p.id === promptId);
    if (!prompt) return;

    setPrompts(prev => prev.map(p => {
      if (p.prompt_name === prompt.prompt_name) {
        return { ...p, is_default: p.id === promptId };
      }
      return p;
    }));
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
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
                      onClick={() => setExpandedId(isExpanded ? null : version.id)}
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
                                  handleSetDefault(version.id);
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
                          <div className="text-xs text-gray-400 italic">
                            Prompt template content would be displayed here in full version
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
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                  placeholder="e.g., chapter_generation"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Model
                </label>
                <select className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500">
                  <option value="deepseek-chat">DeepSeek Chat</option>
                  <option value="claude-3-sonnet">Claude 3 Sonnet</option>
                  <option value="gpt-4o">GPT-4o</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Change Notes
                </label>
                <textarea
                  rows={3}
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
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700"
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
