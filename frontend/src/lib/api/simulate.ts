import api from './client';

export interface SimulateMessageRequest {
  sender_phone: string;
  recipient_phone: string;
  message_body: string;
  sender_name?: string;
}

export interface SimulateMessageResponse {
  message_id: string;
  status: string;
  case?: string;
  route?: string;
  response_text?: string;
  sender_type?: string;
  organization_id?: string;
}

export interface SimulationRecipient {
  phone_number: string;
  label: string;
  type: 'central' | 'business';
  organization_id?: string;
}

export async function simulateMessage(
  req: SimulateMessageRequest
): Promise<SimulateMessageResponse> {
  const response = await api.post<SimulateMessageResponse>('/simulate/message', req);
  return response.data;
}

export async function getSimulationRecipients(): Promise<SimulationRecipient[]> {
  const response = await api.get<SimulationRecipient[]>('/simulate/recipients');
  return response.data;
}
