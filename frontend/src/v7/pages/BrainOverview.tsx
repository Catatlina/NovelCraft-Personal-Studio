/**
 * Brain Overview page - V7
 * 
 * Shows overall brain state statistics, recent events, and quick actions.
 */
import { useState, useEffect } from 'react';
import {
  Brain, BookOpen, Target, Shield, GitBranch, Activity,
  AlertTriangle, CheckCircle, Clock, Zap,
} from 'lucide-react';
import brainApi from '../api/client';
import type { BrainOverview as BrainOverviewType } from '../types';

interface BrainOverviewProps {
  novelId: string;
}

export function BrainOverview({ novelId }: BrainOverviewProps) {
  const [overview, setOverview] = useState<BrainOverviewType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadOverview();
  }, [novelId]);

  const loadOverview = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await brainApi.getOverview(novelId);
      setOverview(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-red-500 mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <button
          onClick={loadOverview}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!overview) return null;

  const statCards = [
    {
      title: 'States',
      value: overview.states.total,
      icon: Brain,
      color: 'blue',
      sub: `${overview.states.pending_review} pending review`,
      subColor: overview.states.pending_review > 0 ? 'text-amber-600' : 'text-gray-500',
    },
    {
      title: 'Goals',
      value: overview.goals.total,
      icon: Target,
      color: 'green',
      sub: `${overview.goals.completed} completed`,
      subColor: 'text-green-600',
    },
    {
      title: 'Constraints',
      value: overview.constraints.total,
      icon: Shield,
      color: 'purple',
      sub: `${overview.constraints.active} active`,
      subColor: 'text-purple-600',
    },
    {
      title: 'Version',
      value: overview.latest_version?.version_number || 0,
      icon: GitBranch,
      color: 'gray',
      sub: overview.latest_version?.version_type || 'no version',
      subColor: 'text-gray-500',
    },
  ];

  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
    gray: 'bg-gray-50 text-gray-600',
  };

  const severityColors: Record<string, string> = {
    info: 'text-blue-500',
    warning: 'text-amber-500',
    error: 'text-red-500',
    critical: 'text-red-700',
    debug: 'text-gray-400',
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Brain className="h-7 w-7 text-blue-600" />
            Novel Brain
          </h1>
          <p className="text-gray-500 mt-1">
            Global story state, goals, constraints, and version control
          </p>
        </div>
        <button
          onClick={loadOverview}
          className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50 flex items-center gap-2"
        >
          <Activity className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card) => (
          <div
            key={card.title}
            className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{card.title}</p>
                <p className="text-3xl font-bold text-gray-900 mt-1">{card.value}</p>
              </div>
              <div className={`p-2 rounded-lg ${colorClasses[card.color]}`}>
                <card.icon className="h-6 w-6" />
              </div>
            </div>
            <p className={`text-sm mt-3 ${card.subColor}`}>{card.sub}</p>
          </div>
        ))}
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Goal Progress */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Target className="h-5 w-5 text-green-600" />
            Goal Progress
          </h2>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Completed</span>
                <span className="font-medium text-green-600">
                  {overview.goals.completed} / {overview.goals.total}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-green-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${overview.goals.total > 0
                      ? (overview.goals.completed / overview.goals.total) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">In Progress</span>
                <span className="font-medium text-blue-600">
                  {overview.goals.in_progress}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{
                    width: `${overview.goals.total > 0
                      ? (overview.goals.in_progress / overview.goals.total) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">Pending</span>
                <span className="font-medium text-gray-500">
                  {overview.goals.pending}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-gray-400 h-2 rounded-full transition-all"
                  style={{
                    width: `${overview.goals.total > 0
                      ? (overview.goals.pending / overview.goals.total) * 100
                      : 0}%`,
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Recent Events */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            Recent Events
          </h2>
          <div className="space-y-3 max-h-64 overflow-y-auto">
            {overview.recent_events.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-4">
                No events yet
              </p>
            ) : (
              overview.recent_events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-3 p-2 rounded hover:bg-gray-50"
                >
                  <div className={`mt-0.5 ${severityColors[event.severity]}`}>
                    {event.severity === 'error' || event.severity === 'critical' ? (
                      <AlertTriangle className="h-4 w-4" />
                    ) : event.severity === 'warning' ? (
                      <Clock className="h-4 w-4" />
                    ) : (
                      <CheckCircle className="h-4 w-4" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {event.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {event.time ? new Date(event.time).toLocaleString() : ''}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* State Types Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-blue-600" />
          States by Type
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Object.entries(overview.states.by_type).map(([type, count]) => (
            <div
              key={type}
              className="text-center p-3 bg-gray-50 rounded-lg"
            >
              <p className="text-2xl font-bold text-gray-900">{count}</p>
              <p className="text-sm text-gray-500 capitalize">{type}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default BrainOverview;
