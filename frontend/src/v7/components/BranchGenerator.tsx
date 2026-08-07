/**
 * 分支生成器组件
 *
 * 提供剧情分支探索功能：
 * - 选中文字后可以生成分支
 * - 展示 1-3 条不同走向的分支选项
 * - 可以应用某条分支到正文
 * - 可以保存分支为草稿
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ChevronRight,
  Copy,
  GitBranch,
  Lightbulb,
  RefreshCw,
  Save,
  Sparkles,
  Wand2,
  X,
} from 'lucide-react';

interface BranchOption {
  id: string;
  title: string;
  content: string;
  direction: string;
  confidence: number;
  created_at?: string;
}

interface BranchResult {
  id: string;
  novel_id: string;
  chapter_id: string;
  source_text: string;
  source_start: number;
  source_end: number;
  options: BranchOption[];
  status: string;
  created_at?: string;
}

interface BranchGeneratorProps {
  novelId?: string;
  chapterId?: string;
  selectedText?: string;
  selectedRange?: { start: number; end: number } | null;
  onApplyBranch?: (content: string, mode: 'replace' | 'insert_after' | 'insert_before') => void;
  onClose?: () => void;
}

type GenerationStatus = 'idle' | 'generating' | 'success' | 'error';

export default function BranchGenerator({
  novelId,
  chapterId,
  selectedText,
  selectedRange,
  onApplyBranch,
  onClose,
}: BranchGeneratorProps) {
  const [status, setStatus] = useState<GenerationStatus>('idle');
  const [result, setResult] = useState<BranchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [numOptions, setNumOptions] = useState(3);

  // 检查是否可以生成分支
  const canGenerate = useMemo(() => {
    return !!selectedText && selectedText.length >= 10 && !!novelId && !!chapterId;
  }, [selectedText, novelId, chapterId]);

  // 生成分支
  const handleGenerate = useCallback(async () => {
    if (!canGenerate || !selectedText || !selectedRange) return;

    setStatus('generating');
    setError(null);
    setResult(null);
    setSelectedOption(null);

    try {
      // 调用 API 生成分支
      const response = await fetch('/api/v7/branches/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          novel_id: novelId,
          chapter_id: chapterId,
          source_text: selectedText,
          source_start: selectedRange.start,
          source_end: selectedRange.end,
          num_options: numOptions,
        }),
      });

      if (!response.ok) {
        throw new Error(`生成失败：${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      setStatus('success');
    } catch (err) {
      setError(err instanceof Error ? err.message : '生成失败');
      setStatus('error');
    }
  }, [canGenerate, selectedText, selectedRange, novelId, chapterId, numOptions]);

  // 应用分支
  const handleApply = useCallback((option: BranchOption, mode: 'replace' | 'insert_after' | 'insert_before') => {
    if (onApplyBranch) {
      onApplyBranch(option.content, mode);
    }
  }, [onApplyBranch]);

  // 保存分支
  const handleSave = useCallback(async (option: BranchOption) => {
    if (!result) return;

    try {
      const response = await fetch(`/api/v7/branches/${result.id}/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          option_id: option.id,
          title: option.title,
        }),
      });

      if (!response.ok) {
        throw new Error('保存失败');
      }

      // 可以显示保存成功的提示
    } catch (err) {
      console.error('保存分支失败：', err);
    }
  }, [result]);

  // 复制分支内容
  const handleCopy = useCallback((content: string) => {
    navigator.clipboard.writeText(content).catch(console.error);
  }, []);

  // 重新生成
  const handleRegenerate = useCallback(() => {
    handleGenerate();
  }, [handleGenerate]);

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-purple-600" />
          <h2 className="font-semibold text-gray-800">剧情分支</h2>
        </div>
        {onClose && (
          <button
            className="p-1 hover:bg-gray-100 rounded text-gray-500"
            onClick={onClose}
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* 生成控制区 */}
      <div className="p-4 border-b">
        <div className="mb-3">
          <label className="block text-xs text-gray-500 mb-1">生成分支数量</label>
          <div className="flex gap-2">
            {[2, 3, 4].map(n => (
              <button
                key={n}
                className={`flex-1 py-1.5 text-sm rounded border transition-colors ${
                  numOptions === n
                    ? 'bg-purple-50 border-purple-300 text-purple-700'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                }`}
                onClick={() => setNumOptions(n)}
              >
                {n} 条
              </button>
            ))}
          </div>
        </div>

        <button
          className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-lg font-medium transition-colors ${
            canGenerate && status !== 'generating'
              ? 'bg-purple-600 text-white hover:bg-purple-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          }`}
          onClick={handleGenerate}
          disabled={!canGenerate || status === 'generating'}
        >
          {status === 'generating' ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              生成中...
            </>
          ) : (
            <>
              <Wand2 className="w-4 h-4" />
              探索分支
            </>
          )}
        </button>

        {!canGenerate && (
          <p className="mt-2 text-xs text-gray-400 text-center">
            请先选中一段文字（至少 10 字）
          </p>
        )}
      </div>

      {/* 选中的文本预览 */}
      {selectedText && (
        <div className="px-4 py-3 border-b bg-gray-50">
          <div className="text-xs text-gray-500 mb-1">选中的文本：</div>
          <div className="text-sm text-gray-700 line-clamp-3 bg-white p-2 rounded border">
            {selectedText}
          </div>
        </div>
      )}

      {/* 错误提示 */}
      {status === 'error' && error && (
        <div className="mx-4 my-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-sm text-red-600">{error}</div>
          <button
            className="mt-2 text-xs text-red-500 hover:text-red-700 underline"
            onClick={handleRegenerate}
          >
            重试
          </button>
        </div>
      )}

      {/* 分支选项列表 */}
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {status === 'success' && result && (
          <>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">
                生成了 {result.options.length} 条分支
              </span>
              <button
                className="flex items-center gap-1 text-xs text-purple-600 hover:text-purple-700"
                onClick={handleRegenerate}
              >
                <RefreshCw className="w-3 h-3" />
                重新生成
              </button>
            </div>

            {result.options.map((option, index) => (
              <div
                key={option.id}
                className={`border rounded-lg overflow-hidden transition-all cursor-pointer ${
                  selectedOption === option.id
                    ? 'border-purple-400 ring-2 ring-purple-100'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => setSelectedOption(
                  selectedOption === option.id ? null : option.id
                )}
              >
                {/* 分支标题 */}
                <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 flex items-center justify-center bg-purple-100 text-purple-700 rounded-full text-xs font-bold">
                      {index + 1}
                    </span>
                    <span className="font-medium text-sm text-gray-800">
                      {option.title}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-400">
                      置信度 {Math.round(option.confidence * 100)}%
                    </span>
                    <ChevronRight className={`w-4 h-4 text-gray-400 transition-transform ${
                      selectedOption === option.id ? 'rotate-90' : ''
                    }`} />
                  </div>
                </div>

                {/* 分支内容 */}
                {selectedOption === option.id && (
                  <div className="p-3">
                    <div className="text-sm text-gray-700 whitespace-pre-wrap mb-3 max-h-48 overflow-auto">
                      {option.content}
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleApply(option, 'replace');
                        }}
                      >
                        <Sparkles className="w-3 h-3" />
                        替换应用
                      </button>
                      <button
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-50 text-blue-600 border border-blue-200 rounded hover:bg-blue-100 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleApply(option, 'insert_after');
                        }}
                      >
                        插入后面
                      </button>
                      <button
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-50 text-gray-600 border border-gray-200 rounded hover:bg-gray-100 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSave(option);
                        }}
                      >
                        <Save className="w-3 h-3" />
                        保存草稿
                      </button>
                      <button
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-50 text-gray-600 border border-gray-200 rounded hover:bg-gray-100 transition-colors"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCopy(option.content);
                        }}
                      >
                        <Copy className="w-3 h-3" />
                        复制
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </>
        )}

        {/* 空状态 */}
        {status === 'idle' && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Lightbulb className="w-12 h-12 text-gray-300 mb-3" />
            <p className="text-sm text-gray-500 mb-1">探索剧情的多种可能</p>
            <p className="text-xs text-gray-400">
              选中一段文字，点击"探索分支"<br />
              AI 会生成不同走向的剧情供你选择
            </p>
          </div>
        )}
      </div>

      {/* 底部提示 */}
      <div className="px-4 py-2 border-t bg-gray-50">
        <p className="text-xs text-gray-400 text-center">
          💡 分支只是创意辅助，不会自动修改正文
        </p>
      </div>
    </div>
  );
}
