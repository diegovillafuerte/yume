'use client';

import { useState } from 'react';
import type { TraceExchangeSummary, TraceStepSummary, TraceStepDetail } from '@/lib/types';
import TraceDetailModal from './TraceDetailModal';

interface ExecutionLoggerProps {
  exchanges: TraceExchangeSummary[];
  isLoading?: boolean;
  onLoadTraceDetail: (traceId: string) => Promise<TraceStepDetail>;
}

// Icon mapping for trace types
const TRACE_TYPE_ICONS: Record<string, string> = {
  message_received: '📨',
  routing_decision: '🔀',
  llm_call: '🧠',
  tool_execution: '⚙️',
  response_assembled: '✅',
};

const TRACE_TYPE_LABELS: Record<string, string> = {
  message_received: 'Message Received',
  routing_decision: 'Routing',
  llm_call: 'LLM Call',
  tool_execution: 'Tool',
  response_assembled: 'Response',
};

export default function ExecutionLogger({
  exchanges,
  isLoading,
  onLoadTraceDetail,
}: ExecutionLoggerProps) {
  const [expandedExchanges, setExpandedExchanges] = useState<Set<string>>(new Set());
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [traceDetail, setTraceDetail] = useState<TraceStepDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const toggleExpand = (exchangeId: string) => {
    const next = new Set(expandedExchanges);
    if (next.has(exchangeId)) {
      next.delete(exchangeId);
    } else {
      next.add(exchangeId);
    }
    setExpandedExchanges(next);
  };

  const handleTraceClick = async (traceId: string) => {
    setSelectedTraceId(traceId);
    setLoadingDetail(true);
    try {
      const detail = await onLoadTraceDetail(traceId);
      setTraceDetail(detail);
    } catch (error) {
      console.error('Failed to load trace detail:', error);
    } finally {
      setLoadingDetail(false);
    }
  };

  const closeModal = () => {
    setSelectedTraceId(null);
    setTraceDetail(null);
  };

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('es-MX', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatLatency = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Execution Logger</h3>
        <span className="text-sm text-gray-500">
          {exchanges.length} exchange{exchanges.length !== 1 ? 's' : ''}
        </span>
      </div>

      {exchanges.length === 0 ? (
        <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          <p>No execution traces yet.</p>
          <p className="text-sm mt-1">Send a message to see the execution trace.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {exchanges.map((exchange) => {
            const isExpanded = expandedExchanges.has(exchange.exchange_id);

            return (
              <div
                key={exchange.exchange_id}
                className="bg-white rounded-lg shadow-sm border overflow-hidden"
              >
                {/* L1: Exchange Summary (clickable) */}
                <button
                  onClick={() => toggleExpand(exchange.exchange_id)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <span className={`transform transition-transform ${isExpanded ? 'rotate-90' : ''}`}>
                      ▶
                    </span>
                    <div className="text-left">
                      <div className="text-sm font-medium text-gray-900 truncate max-w-md">
                        {exchange.user_message_preview || 'Message'}
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatTime(exchange.created_at)} · {exchange.step_count} steps
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={`text-sm font-mono ${
                      exchange.total_latency_ms > 3000 ? 'text-orange-600' : 'text-gray-600'
                    }`}>
                      {formatLatency(exchange.total_latency_ms)}
                    </span>
                  </div>
                </button>

                {/* L2: Steps (expanded) */}
                {isExpanded && (
                  <div className="border-t bg-gray-50 px-4 py-3 space-y-2">
                    {exchange.steps.map((step) => (
                      <button
                        key={step.id}
                        onClick={() => handleTraceClick(step.id)}
                        className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white transition-colors text-left"
                      >
                        <span className="text-lg" title={step.trace_type}>
                          {TRACE_TYPE_ICONS[step.trace_type] || '📋'}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-800">
                            {TRACE_TYPE_LABELS[step.trace_type] || step.trace_type}
                            {step.tool_name && (
                              <span className="font-mono text-blue-600 ml-2">
                                {step.tool_name}
                              </span>
                            )}
                            {step.llm_call_number && (
                              <span className="text-gray-500 ml-2">
                                #{step.llm_call_number}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {step.is_error && (
                            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-red-100 text-red-800">
                              Error
                            </span>
                          )}
                          <span className="text-sm font-mono text-gray-500">
                            {formatLatency(step.latency_ms)}
                          </span>
                          <span className="text-gray-400">→</span>
                        </div>
                      </button>
                    ))}

                    {/* AI Response preview */}
                    {exchange.ai_response_preview && (
                      <div className="mt-3 pt-3 border-t">
                        <div className="text-xs text-gray-500 mb-1">AI Response:</div>
                        <div className="text-sm text-gray-700 italic truncate">
                          "{exchange.ai_response_preview}"
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* L3: Detail Modal */}
      {selectedTraceId && (
        <TraceDetailModal
          trace={traceDetail}
          isLoading={loadingDetail}
          onClose={closeModal}
        />
      )}
    </div>
  );
}
