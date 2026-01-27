import api from './client';
import type {
  PlaygroundUserSummary,
  PlaygroundUserDetail,
  PlaygroundSendRequest,
  PlaygroundSendResponse,
  PlaygroundExchangeListResponse,
  PlaygroundTraceListResponse,
  TraceStepDetail,
} from '@/lib/types';

export async function listPlaygroundUsers(params?: {
  search?: string;
  limit?: number;
}): Promise<PlaygroundUserSummary[]> {
  const response = await api.get<PlaygroundUserSummary[]>('/admin/playground/users', {
    params,
  });
  return response.data;
}

export async function getPlaygroundUser(phoneNumber: string): Promise<PlaygroundUserDetail> {
  const response = await api.get<PlaygroundUserDetail>(
    `/admin/playground/users/${encodeURIComponent(phoneNumber)}`
  );
  return response.data;
}

export async function sendPlaygroundMessage(
  request: PlaygroundSendRequest
): Promise<PlaygroundSendResponse> {
  const response = await api.post<PlaygroundSendResponse>('/admin/playground/send', request);
  return response.data;
}

export async function listPlaygroundExchanges(params?: {
  phone_number?: string;
  org_id?: string;
  limit?: number;
}): Promise<PlaygroundExchangeListResponse> {
  const response = await api.get<PlaygroundExchangeListResponse>('/admin/playground/exchanges', {
    params,
  });
  return response.data;
}

export async function getExchangeTraces(exchangeId: string): Promise<PlaygroundTraceListResponse> {
  const response = await api.get<PlaygroundTraceListResponse>('/admin/playground/traces', {
    params: { exchange_id: exchangeId },
  });
  return response.data;
}

export async function getTraceDetail(traceId: string): Promise<TraceStepDetail> {
  const response = await api.get<TraceStepDetail>(`/admin/playground/traces/${traceId}`);
  return response.data;
}
