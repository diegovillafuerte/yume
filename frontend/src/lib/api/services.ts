import api from './client';
import { ServiceType, ServiceTypeCreate, ServiceTypeUpdate } from '@/lib/types';

export async function getServices(orgId: string): Promise<ServiceType[]> {
  const response = await api.get(`/organizations/${orgId}/service-types`);
  return response.data;
}

export async function createService(orgId: string, data: ServiceTypeCreate): Promise<ServiceType> {
  const response = await api.post(`/organizations/${orgId}/service-types`, data);
  return response.data;
}

export async function updateService(
  orgId: string,
  serviceId: string,
  data: ServiceTypeUpdate
): Promise<ServiceType> {
  const response = await api.patch(`/organizations/${orgId}/service-types/${serviceId}`, data);
  return response.data;
}

export async function deleteService(orgId: string, serviceId: string): Promise<void> {
  await api.delete(`/organizations/${orgId}/service-types/${serviceId}`);
}
