'use client';

import { useEffect } from 'react';
import type { TraceStepDetail } from '@/lib/types';

interface TraceDetailModalProps {
  trace: TraceStepDetail | null;
  isLoading: boolean;
  onClose: () => void;
}

export default function TraceDetailModal({
  trace,
  isLoading,
  onClose,
}: TraceDetailModalProps) {
  // Close on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  if (!trace && !isLoading) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b px-6 py-4">
            <h3 className="text-lg font-semibold text-gray-900">
              Trace Detail
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="overflow-y-auto max-h-[calc(90vh-130px)] p-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : trace ? (
              <div className="space-y-6">
                {/* Summary */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium text-gray-500">Type:</span>{' '}
                    <span className="font-mono">{trace.trace_type}</span>
                  </div>
                  <div>
                    <span className="font-medium text-gray-500">Sequence:</span>{' '}
                    {trace.sequence_number}
                  </div>
                  <div>
                    <span className="font-medium text-gray-500">Latency:</span>{' '}
                    <span className="font-mono">{trace.latency_ms}ms</span>
                  </div>
                  <div>
                    <span className="font-medium text-gray-500">Status:</span>{' '}
                    {trace.is_error ? (
                      <span className="text-red-600">Error</span>
                    ) : (
                      <span className="text-green-600">Success</span>
                    )}
                  </div>
                </div>

                {/* Error message */}
                {trace.is_error && trace.error_message && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <h4 className="text-sm font-medium text-red-800 mb-1">Error</h4>
                    <p className="text-sm text-red-700 font-mono whitespace-pre-wrap">
                      {trace.error_message}
                    </p>
                  </div>
                )}

                {/* Input Data */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Input Data</h4>
                  <pre className="bg-gray-900 text-green-400 rounded-lg p-4 text-xs overflow-x-auto">
                    {JSON.stringify(trace.input_data, null, 2)}
                  </pre>
                </div>

                {/* Output Data */}
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Output Data</h4>
                  <pre className="bg-gray-900 text-green-400 rounded-lg p-4 text-xs overflow-x-auto">
                    {JSON.stringify(trace.output_data, null, 2)}
                  </pre>
                </div>

                {/* Metadata */}
                {Object.keys(trace.metadata).length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Metadata</h4>
                    <pre className="bg-gray-100 text-gray-800 rounded-lg p-4 text-xs overflow-x-auto">
                      {JSON.stringify(trace.metadata, null, 2)}
                    </pre>
                  </div>
                )}

                {/* Timestamps */}
                <div className="text-xs text-gray-500 border-t pt-4">
                  <div>Started: {new Date(trace.started_at).toISOString()}</div>
                  <div>Completed: {new Date(trace.completed_at).toISOString()}</div>
                </div>
              </div>
            ) : null}
          </div>

          {/* Footer */}
          <div className="border-t px-6 py-4 bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
