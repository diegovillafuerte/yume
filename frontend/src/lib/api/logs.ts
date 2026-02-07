import api from './client';
import type {
  LogCorrelationListResponse,
  LogCorrelationDetail,
  LogTraceItem,
  UserActivityListResponse,
} from '@/lib/types';

export interface ListLogsParams {
  phone_number?: string;
  organization_id?: string;
  errors_only?: boolean;
  skip?: number;
  limit?: number;
}

export async function listLogs(params?: ListLogsParams): Promise<LogCorrelationListResponse> {
  const response = await api.get<LogCorrelationListResponse>('/admin/logs', {
    params,
  });
  return response.data;
}

export interface ListUserActivityParams {
  phone_number?: string;
  organization_id?: string;
  errors_only?: boolean;
  skip?: number;
  limit?: number;
}

export async function listUserActivity(params?: ListUserActivityParams): Promise<UserActivityListResponse> {
  const response = await api.get<UserActivityListResponse>('/admin/logs/activity', {
    params,
  });
  return response.data;
}

export async function getCorrelation(correlationId: string): Promise<LogCorrelationDetail> {
  const response = await api.get<LogCorrelationDetail>(`/admin/logs/${correlationId}`);
  return response.data;
}

export async function getTraceDetail(
  correlationId: string,
  traceId: string
): Promise<LogTraceItem> {
  const response = await api.get<LogTraceItem>(
    `/admin/logs/${correlationId}/traces/${traceId}`
  );
  return response.data;
}
