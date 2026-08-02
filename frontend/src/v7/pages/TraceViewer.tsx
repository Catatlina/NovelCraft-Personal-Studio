/**
 * Trace Viewer page - V7 Sprint 2
 * 
 * View agent execution traces with step-by-step details.
 */
import { useState, useEffect } from 'react';
import {
  Activity, Clock, Zap, DollarSign, ChevronRight,
  Play, CheckCircle, XCircle, AlertCircle,
  Eye, EyeOff,
} from 'lucide-react';
import brainApi from '../api/client';
import type { Run, TraceStep } from '../types';

interface TraceViewerProps {
  novelId: string;
}

export function TraceViewer({ novelId }: TraceViewerProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRun, setSelectedRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [selectedStep, setSelectedStep] = useState<TraceStep | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    loadRuns();
  }, [novelId]);

  const loadRuns = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listRuns(novelId, { limit: 50 });
      setRuns(data || []);
    } catch (err: any) {
      console.error('Failed to load runs:', err);
      // 失败时显示空态，不伪造演示数据
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const loadSteps = async (runId: string) => {
    try {
      const data = await brainApi.listTraceSteps(novelId, runId);
      setSteps(data || []);
    } catch (err: any) {
      console.error('Failed to load steps:', err);
      // 失败时显示空态，不伪造演示数据
      setSteps([]);
    }
  };

  const handleSelectRun = async (run: Run) => {
    setSelectedRun(run);
    setSelectedStep(null);
    await loadSteps(run.id);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50';
      case 'running': return 'text-blue-600 bg-blue-50';
      case 'failed': return 'text-red-600 bg-red-50';
      case 'pending': return 'text-gray-500 bg-gray-50';
      default: return 'text-gray-500 bg-gray-50';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return CheckCircle;
      case 'running': return Play;
      case 'failed': return XCircle;
      default: return AlertCircle;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}m ${secs}s`;
  };

  const formatCost = (cost?: number) => {
    if (cost === undefined || cost === null) return '-';
    return `¥${cost.toFixed(4)}`;
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="h-7 w-7 text-cyan-600" />
            Trace Viewer
          </h1>
          <p className="text-gray-500 mt-1">
            View agent execution traces and step-by-step details
          </p>
        </div>
        <button
          onClick={loadRuns}
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Runs List */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900">Runs</h2>
            </div>
            <div className="divide-y divide-gray-100 max-h-[600px] overflow-y-auto">
              {loading ? (
                <div className="flex items-center justify-center p-8">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-600" />
                </div>
              ) : runs.length === 0 ? (
                <div className="text-center py-8">
                  <Activity className="mx-auto h-8 w-8 text-gray-300 mb-2" />
                  <p className="text-sm text-gray-500">No runs yet</p>
                </div>
              ) : (
                runs.map((run) => {
                  const StatusIcon = getStatusIcon(run.status);
                  const isSelected = selectedRun?.id === run.id;
                  return (
                    <div
                      key={run.id}
                      onClick={() => handleSelectRun(run)}
                      className={`p-4 cursor-pointer transition-colors ${
                        isSelected ? 'bg-cyan-50' : 'hover:bg-gray-50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <StatusIcon className={`h-4 w-4 ${getStatusColor(run.status).split(' ')[0]}`} />
                          <span className="font-medium text-sm text-gray-900 capitalize">
                            {run.run_type.replace(/_/g, ' ')}
                          </span>
                        </div>
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-500">
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDuration(run.duration_seconds)}
                        </div>
                        <div className="flex items-center gap-1">
                          <Zap className="h-3 w-3" />
                          {run.total_tokens?.toLocaleString() || 0} tokens
                        </div>
                        <div className="flex items-center gap-1">
                          <DollarSign className="h-3 w-3" />
                          {formatCost(run.total_cost)}
                        </div>
                        <div>
                          Ch. {run.chapter_number || '-'}
                        </div>
                      </div>
                      {run.started_at && (
                        <p className="text-xs text-gray-400 mt-2">
                          {new Date(run.started_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Steps Timeline */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">
                {selectedRun ? 'Trace Steps' : 'Select a run to view steps'}
              </h2>
              {selectedRun && (
                <button
                  onClick={() => setShowDetails(!showDetails)}
                  className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
                >
                  {showDetails ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  {showDetails ? 'Hide details' : 'Show details'}
                </button>
              )}
            </div>
            
            {selectedRun && (
              <div className="p-4">
                {/* Run summary */}
                <div className="grid grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">{steps.length}</p>
                    <p className="text-xs text-gray-500">Steps</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">
                      {formatDuration(selectedRun.duration_seconds)}
                    </p>
                    <p className="text-xs text-gray-500">Duration</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">
                      {selectedRun.total_tokens?.toLocaleString() || 0}
                    </p>
                    <p className="text-xs text-gray-500">Tokens</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-bold text-gray-900">
                      {formatCost(selectedRun.total_cost)}
                    </p>
                    <p className="text-xs text-gray-500">Cost</p>
                  </div>
                </div>

                {/* Steps timeline */}
                <div className="space-y-2">
                  {steps.map((step, index) => {
                    const StatusIcon = getStatusIcon(step.status);
                    const isSelected = selectedStep?.id === step.id;
                    return (
                      <div
                        key={step.id}
                        onClick={() => setSelectedStep(isSelected ? null : step)}
                        className={`p-3 rounded-lg cursor-pointer transition-colors ${
                          isSelected ? 'bg-cyan-50 border border-cyan-200' : 'hover:bg-gray-50 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex flex-col items-center">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${getStatusColor(step.status)}`}>
                              <StatusIcon className="h-4 w-4" />
                            </div>
                            {index < steps.length - 1 && (
                              <div className="w-0.5 h-4 bg-gray-200" />
                            )}
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-sm text-gray-900 font-mono">
                                {step.step_name}
                              </span>
                              <span className="text-xs text-gray-500">
                                {formatDuration(step.duration_seconds)}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                              <span className="capitalize">{step.step_type}</span>
                              {step.tokens_input || step.tokens_output ? (
                                <span>
                                  {step.tokens_input?.toLocaleString() || 0} → {step.tokens_output?.toLocaleString() || 0} tokens
                                </span>
                              ) : null}
                              {step.confidence !== undefined && (
                                <span>Confidence: {Math.round(step.confidence * 100)}%</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Step details */}
                        {isSelected && showDetails && (
                          <div className="mt-3 ml-11 p-3 bg-white rounded border border-gray-200">
                            {step.input_summary && (
                              <div className="mb-2">
                                <p className="text-xs font-medium text-gray-500 mb-1">Input</p>
                                <p className="text-sm text-gray-700">{step.input_summary}</p>
                              </div>
                            )}
                            {step.output_summary && (
                              <div className="mb-2">
                                <p className="text-xs font-medium text-gray-500 mb-1">Output</p>
                                <p className="text-sm text-gray-700">{step.output_summary}</p>
                              </div>
                            )}
                            {step.model && (
                              <p className="text-xs text-gray-500">Model: {step.model}</p>
                            )}
                            {step.prompt_version && (
                              <p className="text-xs text-gray-500">Prompt: {step.prompt_version}</p>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default TraceViewer;
