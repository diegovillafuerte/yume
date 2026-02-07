'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import { listUserActivity, getCorrelation } from '@/lib/api/logs';
import type {
  UserActivityGroup,
  EnrichedCorrelation,
  LogCorrelationDetail,
  LogTraceItem,
} from '@/lib/types';

const FLOW_COLORS: Record<string, string> = {
  customer: 'bg-green-500',
  staff: 'bg-blue-500',
  onboarding: 'bg-purple-500',
  staff_onboarding: 'bg-indigo-500',
  central: 'bg-yellow-500',
  unknown: 'bg-gray-400',
};

const TRACE_TYPE_COLORS: Record<string, string> = {
  service: 'bg-gray-400',
  ai_tool: 'bg-blue-500',
  external_api: 'bg-green-500',
};

export default function AdminLogsPage() {
  const [phoneFilter, setPhoneFilter] = useState('');
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [expandedPhone, setExpandedPhone] = useState<string | null>(null);
  const [expandedCorrelation, setExpandedCorrelation] = useState<string | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<LogTraceItem | null>(null);

  // Level 1: User activity groups
  const { data: activityData, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-activity', phoneFilter, errorsOnly],
    queryFn: () =>
      listUserActivity({
        phone_number: phoneFilter || undefined,
        errors_only: errorsOnly || undefined,
        limit: 20,
      }),
  });

  // Level 3: Trace waterfall for expanded correlation
  const { data: correlationDetail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['admin-logs-detail', expandedCorrelation],
    queryFn: () => getCorrelation(expandedCorrelation!),
    enabled: !!expandedCorrelation,
  });

  const formatRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('es-MX', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleTogglePhone = (phone: string) => {
    if (expandedPhone === phone) {
      setExpandedPhone(null);
      setExpandedCorrelation(null);
    } else {
      setExpandedPhone(phone);
      setExpandedCorrelation(null);
    }
    setSelectedTrace(null);
  };

  const handleToggleCorrelation = (correlationId: string) => {
    if (expandedCorrelation === correlationId) {
      setExpandedCorrelation(null);
    } else {
      setExpandedCorrelation(correlationId);
    }
    setSelectedTrace(null);
  };

  // Level 3: Trace waterfall
  const renderTraceWaterfall = (detail: LogCorrelationDetail) => {
    return (
      <div className="mt-2 ml-6 border-l-2 border-gray-200 pl-3 space-y-1">
        {detail.traces.map((trace, index) => (
          <div
            key={trace.id}
            className={`flex items-center gap-2 p-2 rounded cursor-pointer transition-colors ${
              trace.is_error
                ? 'bg-red-50 hover:bg-red-100'
                : 'bg-gray-50 hover:bg-gray-100'
            } ${selectedTrace?.id === trace.id ? 'ring-2 ring-blue-500' : ''}`}
            onClick={() => setSelectedTrace(trace)}
          >
            <span className="text-gray-400 text-xs w-4">{index + 1}.</span>
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                TRACE_TYPE_COLORS[trace.trace_type] || 'bg-gray-400'
              }`}
            />
            <span
              className={`text-sm font-mono flex-1 truncate ${
                trace.is_error ? 'text-red-700' : 'text-gray-700'
              }`}
            >
              {trace.function_name}
            </span>
            <span
              className={`text-xs flex-shrink-0 ${
                trace.duration_ms > 500 ? 'text-orange-600' : 'text-gray-400'
              }`}
            >
              {formatDuration(trace.duration_ms)}
            </span>
            {trace.is_error && (
              <span className="text-xs text-red-600 flex-shrink-0">&#10007;</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  // Level 2: Correlation timeline row
  const renderCorrelationTimeline = (corr: EnrichedCorrelation) => {
    const isExpanded = expandedCorrelation === corr.correlation_id;

    return (
      <div key={corr.correlation_id} className="border-b border-gray-100 last:border-b-0">
        <div
          className={`pl-8 pr-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors ${
            corr.has_errors ? 'border-l-2 border-red-400' : ''
          }`}
          onClick={() => handleToggleCorrelation(corr.correlation_id)}
        >
          <div className="flex items-start gap-3">
            <span
              className="text-gray-400 transition-transform mt-1 text-xs"
              style={{ transform: isExpanded ? 'rotate(90deg)' : 'none' }}
            >
              &#9654;
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    FLOW_COLORS[corr.flow_type] || 'bg-gray-400'
                  }`}
                />
                <span className="text-sm font-medium text-gray-800">
                  {corr.flow_label}
                </span>
                <span
                  className={`text-xs flex-shrink-0 ${
                    corr.total_duration_ms > 2000
                      ? 'text-orange-600'
                      : 'text-gray-400'
                  }`}
                >
                  {formatDuration(corr.total_duration_ms)}
                </span>
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {formatRelativeTime(corr.started_at)}
                </span>
                {corr.has_errors && (
                  <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded flex-shrink-0">
                    Error
                  </span>
                )}
              </div>

              {/* Message & response previews */}
              {corr.message_preview && (
                <div className="mt-1 text-sm text-gray-600 truncate">
                  <span className="text-gray-400">&gt; </span>
                  &ldquo;{corr.message_preview}&rdquo;
                </div>
              )}
              {corr.response_preview && (
                <div className="text-sm text-gray-500 truncate">
                  <span className="text-gray-400">&lt; </span>
                  &ldquo;{corr.response_preview}&rdquo;
                </div>
              )}

              {/* AI tool pills */}
              {corr.ai_tools_used.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {corr.ai_tools_used.map((tool) => (
                    <span
                      key={tool}
                      className="px-1.5 py-0.5 text-xs bg-blue-50 text-blue-700 rounded font-mono"
                    >
                      {tool}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Level 3: Trace waterfall */}
        {isExpanded && (
          <div className="bg-white pl-8 pr-4 pb-3">
            {isLoadingDetail ? (
              <div className="py-4 flex justify-center">
                <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : correlationDetail ? (
              renderTraceWaterfall(correlationDetail)
            ) : null}
          </div>
        )}
      </div>
    );
  };

  // Level 1: User activity row
  const renderUserGroup = (group: UserActivityGroup) => {
    const isExpanded = expandedPhone === group.phone_number;

    return (
      <div key={group.phone_number} className="border-b last:border-b-0">
        <div
          className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
            group.error_count > 0 ? 'border-l-3 border-red-400' : ''
          }`}
          onClick={() => handleTogglePhone(group.phone_number)}
        >
          <div className="flex items-center gap-3">
            <span
              className="text-gray-400 transition-transform text-sm"
              style={{ transform: isExpanded ? 'rotate(90deg)' : 'none' }}
            >
              &#9654;
            </span>

            <span
              className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                FLOW_COLORS[group.primary_flow_type] || 'bg-gray-400'
              }`}
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-sm font-medium text-gray-900">
                  {group.phone_number}
                </span>
                {group.organization_name && (
                  <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded-full">
                    {group.organization_name}
                  </span>
                )}
                {group.error_count > 0 && (
                  <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">
                    {group.error_count} error{group.error_count !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-sm text-gray-500">
                  {group.primary_flow_label}
                </span>
                {group.latest_message_preview && (
                  <span className="text-sm text-gray-400 truncate">
                    — &ldquo;{group.latest_message_preview}&rdquo;
                  </span>
                )}
              </div>
            </div>

            <div className="text-right flex-shrink-0">
              <div className="text-xs text-gray-500">
                {group.total_interactions} interaction
                {group.total_interactions !== 1 ? 's' : ''}
              </div>
              <div className="text-xs text-gray-400">
                {formatRelativeTime(group.latest_activity)}
              </div>
            </div>
          </div>
        </div>

        {/* Level 2: Correlation timeline */}
        {isExpanded && (
          <div className="bg-gray-50/50">
            {group.correlations.map((corr) => renderCorrelationTimeline(corr))}
          </div>
        )}
      </div>
    );
  };

  // Trace detail modal
  const renderTraceDetail = (trace: LogTraceItem) => {
    return (
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => setSelectedTrace(null)}
      >
        <div
          className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-4 border-b flex justify-between items-center">
            <div>
              <h3 className="font-semibold text-gray-900">
                {trace.function_name}
              </h3>
              <p className="text-sm text-gray-500">{trace.module_path}</p>
            </div>
            <button
              onClick={() => setSelectedTrace(null)}
              className="text-gray-400 hover:text-gray-600 text-xl"
            >
              &times;
            </button>
          </div>
          <div className="p-4 overflow-y-auto max-h-[60vh] space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Type:</span>
                <span className="ml-2">
                  <span
                    className={`inline-block w-2 h-2 rounded-full mr-1 ${
                      TRACE_TYPE_COLORS[trace.trace_type] || 'bg-gray-400'
                    }`}
                  />
                  {trace.trace_type}
                </span>
              </div>
              <div>
                <span className="text-gray-500">Duration:</span>
                <span className="ml-2 font-medium">
                  {formatDuration(trace.duration_ms)}
                </span>
              </div>
            </div>

            {trace.is_error && (
              <div className="bg-red-50 p-3 rounded-lg">
                <p className="text-sm font-medium text-red-700">
                  {trace.error_type}
                </p>
                <p className="text-sm text-red-600 mt-1">
                  {trace.error_message}
                </p>
              </div>
            )}

            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Input</h4>
              <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-x-auto">
                {JSON.stringify(trace.input_summary, null, 2)}
              </pre>
            </div>

            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Output</h4>
              <pre className="bg-gray-50 p-3 rounded-lg text-xs overflow-x-auto">
                {JSON.stringify(trace.output_summary, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Logs</h2>
          <button
            onClick={() => refetch()}
            className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors"
          >
            Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="flex-1 max-w-xs">
            <input
              type="text"
              placeholder="Filter by phone..."
              value={phoneFilter}
              onChange={(e) => setPhoneFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={errorsOnly}
              onChange={(e) => setErrorsOnly(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Errors only
          </label>
        </div>

        {/* Flow type legend */}
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" /> Customer
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500" /> Staff
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-purple-500" /> Onboarding
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-500" /> Central
          </span>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading logs
          </div>
        ) : activityData && activityData.groups.length > 0 ? (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            {activityData.groups.map((group) => renderUserGroup(group))}
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
            No logs yet. Send a message via WhatsApp to see activity.
          </div>
        )}

        {activityData && activityData.has_more && (
          <div className="text-center text-sm text-gray-500">
            Showing {activityData.groups.length} of {activityData.total_count}{' '}
            users
          </div>
        )}
      </div>

      {/* Trace Detail Modal */}
      {selectedTrace && renderTraceDetail(selectedTrace)}
    </AdminLayout>
  );
}
