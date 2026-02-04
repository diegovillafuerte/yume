'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import { listLogs, getCorrelation } from '@/lib/api/logs';
import type { LogCorrelationSummary, LogCorrelationDetail, LogTraceItem } from '@/lib/types';

export default function AdminLogsPage() {
  const [phoneFilter, setPhoneFilter] = useState('');
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [expandedCorrelation, setExpandedCorrelation] = useState<string | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<LogTraceItem | null>(null);

  const { data: logsData, isLoading, error, refetch } = useQuery({
    queryKey: ['admin-logs', phoneFilter, errorsOnly],
    queryFn: () => listLogs({
      phone_number: phoneFilter || undefined,
      errors_only: errorsOnly || undefined,
      limit: 50,
    }),
  });

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

  const getTraceTypeIcon = (traceType: string) => {
    switch (traceType) {
      case 'ai_tool':
        return '🔧';
      case 'external_api':
        return '🌐';
      default:
        return '⚙️';
    }
  };

  const handleToggleCorrelation = (correlationId: string) => {
    if (expandedCorrelation === correlationId) {
      setExpandedCorrelation(null);
    } else {
      setExpandedCorrelation(correlationId);
    }
    setSelectedTrace(null);
  };

  const renderTraceTree = (detail: LogCorrelationDetail) => {
    return (
      <div className="mt-2 ml-4 border-l-2 border-gray-200 pl-4 space-y-1">
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
            <span className="text-sm">{getTraceTypeIcon(trace.trace_type)}</span>
            <span className={`text-sm font-mono flex-1 ${trace.is_error ? 'text-red-700' : 'text-gray-700'}`}>
              {trace.function_name}
            </span>
            <span className={`text-xs ${trace.duration_ms > 500 ? 'text-orange-600' : 'text-gray-400'}`}>
              {formatDuration(trace.duration_ms)}
            </span>
            {trace.is_error && (
              <span className="text-xs text-red-600">&#10007;</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderTraceDetail = (trace: LogTraceItem) => {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedTrace(null)}>
        <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
          <div className="p-4 border-b flex justify-between items-center">
            <div>
              <h3 className="font-semibold text-gray-900">{trace.function_name}</h3>
              <p className="text-sm text-gray-500">{trace.module_path}</p>
            </div>
            <button
              onClick={() => setSelectedTrace(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              &times;
            </button>
          </div>
          <div className="p-4 overflow-y-auto max-h-[60vh] space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Type:</span>
                <span className="ml-2 font-medium">{trace.trace_type}</span>
              </div>
              <div>
                <span className="text-gray-500">Duration:</span>
                <span className="ml-2 font-medium">{formatDuration(trace.duration_ms)}</span>
              </div>
            </div>

            {trace.is_error && (
              <div className="bg-red-50 p-3 rounded-lg">
                <p className="text-sm font-medium text-red-700">{trace.error_type}</p>
                <p className="text-sm text-red-600 mt-1">{trace.error_message}</p>
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

  const renderCorrelationRow = (corr: LogCorrelationSummary) => {
    const isExpanded = expandedCorrelation === corr.correlation_id;

    return (
      <div key={corr.correlation_id} className="border-b last:border-b-0">
        <div
          className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
            corr.has_errors ? 'bg-red-50/50' : ''
          }`}
          onClick={() => handleToggleCorrelation(corr.correlation_id)}
        >
          <div className="flex items-center gap-4">
            <span className="text-gray-400 transition-transform" style={{ transform: isExpanded ? 'rotate(90deg)' : 'none' }}>
              &#9654;
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-gray-900">{corr.entry_function}</span>
                {corr.has_errors && (
                  <span className="px-1.5 py-0.5 text-xs bg-red-100 text-red-700 rounded">Error</span>
                )}
              </div>
              <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                {corr.phone_number && (
                  <span>{corr.phone_number}</span>
                )}
                {corr.organization_name && (
                  <span>&rarr; {corr.organization_name}</span>
                )}
                <span>{corr.trace_count} traces</span>
              </div>
            </div>
            <div className="text-right">
              <span className={`text-sm ${corr.total_duration_ms > 2000 ? 'text-orange-600' : 'text-gray-600'}`}>
                {formatDuration(corr.total_duration_ms)}
              </span>
              <div className="text-xs text-gray-400">
                {formatRelativeTime(corr.started_at)}
              </div>
            </div>
          </div>
        </div>

        {isExpanded && (
          <div className="bg-white border-t px-4 pb-4">
            {isLoadingDetail ? (
              <div className="py-4 flex justify-center">
                <div className="w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : correlationDetail ? (
              renderTraceTree(correlationDetail)
            ) : null}
          </div>
        )}
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

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading logs
          </div>
        ) : logsData && logsData.correlations.length > 0 ? (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            {logsData.correlations.map((corr) => renderCorrelationRow(corr))}
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
            No logs yet. Send a message via WhatsApp to see function traces.
          </div>
        )}

        {logsData && logsData.has_more && (
          <div className="text-center text-sm text-gray-500">
            Showing {logsData.correlations.length} of {logsData.total_count} correlations
          </div>
        )}
      </div>

      {/* Trace Detail Modal */}
      {selectedTrace && renderTraceDetail(selectedTrace)}
    </AdminLayout>
  );
}
