/**
 * Decision Log page - V7 Sprint 2
 * 
 * View and manage AI decisions with human approval workflow.
 */
import { useState, useEffect } from 'react';
import {
  Scale, Check, X, Clock, AlertTriangle, User, Bot,
  Filter, ChevronDown, ChevronUp,
} from 'lucide-react';
import brainApi from '../api/client';
import type { DecisionLogItem } from '../types';

interface DecisionLogProps {
  novelId: string;
}

const STATUS_FILTERS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'completed', label: 'Completed' },
];

const PERMISSION_LEVELS = [
  { value: 'auto', label: 'Auto', color: 'text-green-600 bg-green-50' },
  { value: 'notify', label: 'Notify', color: 'text-blue-600 bg-blue-50' },
  { value: 'approve', label: 'Approve', color: 'text-amber-600 bg-amber-50' },
  { value: 'forbidden', label: 'Forbidden', color: 'text-red-600 bg-red-50' },
];

export function DecisionLog({ novelId }: DecisionLogProps) {
  const [decisions, setDecisions] = useState<DecisionLogItem[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    loadDecisions();
  }, [novelId, statusFilter]);

  const loadDecisions = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listDecisions(novelId, {
        status: statusFilter || undefined,
        limit: 100,
      });
      setDecisions(data);
    } catch (err: any) {
      console.error('Failed to load decisions:', err);
      // Mock data for demo
      setDecisions([
        {
          id: 'dec-1',
          decision_type: 'chapter_plan',
          decision: 'Chapter 5 plan approved',
          decision_reason: 'Plot aligns with current goals',
          confidence: 0.85,
          permission_level: 'auto',
          status: 'completed',
          decided_by: 'ai',
          decided_at: new Date(Date.now() - 3600000).toISOString(),
          context: { chapter_number: 5, goals_advanced: 2 },
        },
        {
          id: 'dec-2',
          decision_type: 'character_change',
          decision: 'Protagonist personality shift',
          decision_reason: 'Character development milestone',
          confidence: 0.72,
          permission_level: 'approve',
          status: 'pending',
          decided_by: 'ai',
          context: { character: 'protagonist', change_type: 'personality' },
        },
        {
          id: 'dec-3',
          decision_type: 'plot_twist',
          decision: 'Add plot twist in chapter 8',
          decision_reason: 'Reader engagement forecast low',
          confidence: 0.65,
          permission_level: 'approve',
          status: 'pending',
          decided_by: 'ai',
          context: { chapter: 8, twist_type: 'reveal' },
        },
        {
          id: 'dec-4',
          decision_type: 'pacing_adjustment',
          decision: 'Slow down pacing',
          decision_reason: 'Recent chapters too fast',
          confidence: 0.9,
          permission_level: 'notify',
          status: 'completed',
          decided_by: 'ai',
          decided_at: new Date(Date.now() - 7200000).toISOString(),
          context: { adjustment: 'slow', factor: 0.8 },
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (decisionId: string) => {
    try {
      await brainApi.approveDecision(novelId, decisionId);
      loadDecisions();
    } catch (err: any) {
      console.error('Failed to approve:', err);
      // Update locally for demo
      setDecisions(prev => prev.map(d => 
        d.id === decisionId ? { ...d, status: 'approved', decided_by: 'human' } : d
      ));
    }
  };

  const handleReject = async (decisionId: string) => {
    try {
      await brainApi.rejectDecision(novelId, decisionId);
      loadDecisions();
    } catch (err: any) {
      console.error('Failed to reject:', err);
      // Update locally for demo
      setDecisions(prev => prev.map(d => 
        d.id === decisionId ? { ...d, status: 'rejected', decided_by: 'human' } : d
      ));
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'approved':
        return 'text-green-600 bg-green-50';
      case 'pending':
        return 'text-amber-600 bg-amber-50';
      case 'rejected':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-500 bg-gray-50';
    }
  };

  const getPermissionConfig = (level: string) => {
    return PERMISSION_LEVELS.find(p => p.value === level) || PERMISSION_LEVELS[0];
  };

  const pendingCount = decisions.filter(d => d.status === 'pending').length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Scale className="h-7 w-7 text-indigo-600" />
            Decision Log
          </h1>
          <p className="text-gray-500 mt-1">
            Review and manage AI decisions
          </p>
        </div>
        {pendingCount > 0 && (
          <div className="px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-600" />
            <span className="text-sm font-medium text-amber-700">
              {pendingCount} pending approval
            </span>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <div className="flex gap-2">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                onClick={() => setStatusFilter(filter.value)}
                className={`px-3 py-1.5 text-sm rounded-lg border ${
                  statusFilter === filter.value
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Decisions List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : decisions.length === 0 ? (
          <div className="text-center py-12">
            <Scale className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <p className="text-gray-500">No decisions found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {decisions.map((decision) => {
              const permConfig = getPermissionConfig(decision.permission_level);
              const isExpanded = expandedId === decision.id;
              const isPending = decision.status === 'pending';
              
              return (
                <div key={decision.id} className="hover:bg-gray-50">
                  <div
                    className="p-4 cursor-pointer"
                    onClick={() => setExpandedId(isExpanded ? null : decision.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <h3 className="font-medium text-gray-900">
                            {decision.decision}
                          </h3>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full capitalize ${getStatusColor(decision.status)}`}>
                            {decision.status}
                          </span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${permConfig.color}`}>
                            {permConfig.label}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                          <span className="flex items-center gap-1">
                            {decision.decided_by === 'ai' ? (
                              <Bot className="h-4 w-4" />
                            ) : (
                              <User className="h-4 w-4" />
                            )}
                            {decision.decided_by}
                          </span>
                          <span className="flex items-center gap-1">
                            <AlertTriangle className="h-4 w-4" />
                            {Math.round(decision.confidence * 100)}% confidence
                          </span>
                          <span className="capitalize">{decision.decision_type.replace(/_/g, ' ')}</span>
                          {decision.decided_at && (
                            <span>{new Date(decision.decided_at).toLocaleString()}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isPending && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleApprove(decision.id);
                              }}
                              className="px-3 py-1.5 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 flex items-center gap-1"
                            >
                              <Check className="h-4 w-4" />
                              Approve
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReject(decision.id);
                              }}
                              className="px-3 py-1.5 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 flex items-center gap-1"
                            >
                              <X className="h-4 w-4" />
                              Reject
                            </button>
                          </>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="h-5 w-5 text-gray-400" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-gray-400" />
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-4 pb-4 ml-6">
                      <div className="p-4 bg-gray-50 rounded-lg">
                        <h4 className="text-sm font-medium text-gray-700 mb-2">Reason</h4>
                        <p className="text-sm text-gray-600">
                          {decision.decision_reason || 'No reason provided'}
                        </p>
                        
                        {decision.context && Object.keys(decision.context).length > 0 && (
                          <div className="mt-3">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">Context</h4>
                            <pre className="p-2 bg-white rounded text-xs text-gray-600 overflow-x-auto">
                              {JSON.stringify(decision.context, null, 2)}
                            </pre>
                          </div>
                        )}

                        {decision.alternatives && decision.alternatives.length > 0 && (
                          <div className="mt-3">
                            <h4 className="text-sm font-medium text-gray-700 mb-2">Alternatives Considered</h4>
                            <ul className="text-sm text-gray-600 list-disc list-inside">
                              {decision.alternatives.map((alt, i) => (
                                <li key={i}>{alt}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default DecisionLog;
