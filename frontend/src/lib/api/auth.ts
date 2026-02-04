import api from './client';
import { Organization } from '@/lib/types';

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  organization: Organization;
}

export interface MagicLinkResponse {
  message: string;
}

export async function requestMagicLink(phoneNumber: string): Promise<MagicLinkResponse> {
  const response = await api.post<MagicLinkResponse>('/auth/request-magic-link', {
    phone_number: phoneNumber,
  });
  return response.data;
}

export async function verifyMagicLink(token: string): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>('/auth/verify-magic-link', {
    token,
  });
  return response.data;
}
