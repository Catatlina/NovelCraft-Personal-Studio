/**
 * Event Log page - V7
 * 
 * View all system events and activity.
 */
import { useState, useEffect } from 'react';
import {
  Activity, Info, AlertTriangle, XCircle, CheckCircle,
  Filter, RefreshCw,
} from 'lucide-react';
import brainApi from '../api/client';
import type { EventItem } from '../types';

interface EventLogProps {
  novelId: string;
}

const SEVERITY_FILTERS = [
  { value: '', label: 'All', icon: Activity },
  { value: 'info', label: 'Info', icon: Info },
  { value: 'warning', label: 'Warning', icon: AlertTriangle },
  { value: 'error', label: 'Error', icon: XCircle },
];

const CATEGORY_FILTERS = [
  { value: '', label: 'All Categories' },
  { value: 'state', label: 'State' },
  { value: 'goal', label: 'Goal' },
  { value: 'constraint', label: 'Constraint' },
  { value: 'version', label: 'Version' },
  { value: 'decision', label: 'Decision' },
  { value: 'trace', label: 'Trace' },
];

const SEVERITY_COLORS: Record<string, string> = {
  info: 'text-blue-500 bg-blue-50',
  warning: 'text-amber-500 bg-amber-50',
  error: 'text-red-500 bg-red-50',
  critical: 'text-red-700 bg-red-100',
  debug: 'text-gray-400 bg-gray-50',
};

const SEVERITY_ICONS: Record<string, any> = {
  info: Info,
  warning: AlertTriangle,
  error: XCircle,
  critical: XCircle,
  debug: Activity,
};

export function EventLog({ novelId }: EventLogProps) {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    loadEvents();
  }, [novelId, severityFilter, categoryFilter]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadEvents, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, novelId, severityFilter, categoryFilter]);

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await brainApi.listEvents(novelId, {
        severity: severityFilter || undefined,
        event_category: categoryFilter || undefined,
        limit: 200,
      });
      setEvents(data);
    } catch (err: any) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  };

  const getSeverityIcon = (severity: string) => {
    const Icon = SEVERITY_ICONS[severity] || Activity;
    return Icon;
  };

  const getSeverityColor = (severity: string) => {
    return SEVERITY_COLORS[severity] || 'text-gray-500 bg-gray-50';
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="h-7 w-7 text-blue-600" />
            Event Log
          </h1>
          <p className="text-gray-500 mt-1">
            System events and activity history
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-2 text-sm border rounded-lg flex items-center gap-2 ${
              autoRefresh
                ? 'bg-blue-50 border-blue-300 text-blue-600'
                : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
            }`}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            Auto-refresh
          </button>
          <button
            onClick={loadEvents}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="flex gap-2">
          {SEVERITY_FILTERS.map((filter) => {
            const Icon = filter.icon;
            return (
              <button
                key={filter.value}
                onClick={() => setSeverityFilter(filter.value)}
                className={`px-3 py-1.5 text-sm rounded-lg border flex items-center gap-2 ${
                  severityFilter === filter.value
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                <Icon className="h-4 w-4" />
                {filter.label}
              </button>
            );
          })}
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {CATEGORY_FILTERS.map((filter) => (
              <option key={filter.value} value={filter.value}>
                {filter.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Events List */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-12">
            <Activity className="mx-auto h-12 w-12 text-gray-300 mb-4" />
            <p className="text-gray-500">No events found</p>
            <p className="text-sm text-gray-400 mt-1">
              Events will appear here as the system runs
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {events.map((event) => {
              const Icon = getSeverityIcon(event.severity);
              const colorClass = getSeverityColor(event.severity);
              return (
                <div key={event.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start gap-3">
                    <div className={`p-1.5 rounded ${colorClass}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <h3 className="font-medium text-gray-900 text-sm">
                          {event.name}
                        </h3>
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                          {event.category}
                        </span>
                        <span className="text-xs text-gray-400">
                          {event.time && new Date(event.time).toLocaleString()}
                        </span>
                      </div>
                      {event.description && (
                        <p className="text-sm text-gray-500 mt-1">
                          {event.description}
                        </p>
                      )}
                      {event.data && Object.keys(event.data).length > 0 && (
                        <details className="mt-2">
                          <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
                            View details
                          </summary>
                          <pre className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-600 overflow-x-auto">
                            {JSON.stringify(event.data, null, 2)}
                          </pre>
                        </details>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                        <span>Source: {event.source}</span>
                        {event.data?.run_id && (
                          <span>Run: {event.data.run_id.slice(0, 8)}...</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default EventLog;
