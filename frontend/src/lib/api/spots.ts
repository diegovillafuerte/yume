import api from './client';
import { Spot, SpotCreate, SpotUpdate } from '@/lib/types';

export async function getSpots(orgId: string, locationId: string, activeOnly = true): Promise<Spot[]> {
  const response = await api.get(`/organizations/${orgId}/locations/${locationId}/spots`, {
    params: { active_only: activeOnly },
  });
  return response.data;
}

export async function createSpot(
  orgId: string,
  locationId: string,
  data: SpotCreate
): Promise<Spot> {
  const response = await api.post(`/organizations/${orgId}/locations/${locationId}/spots`, data);
  return response.data;
}

export async function updateSpot(
  orgId: string,
  spotId: string,
  data: SpotUpdate
): Promise<Spot> {
  const response = await api.patch(`/organizations/${orgId}/spots/${spotId}`, data);
  return response.data;
}

export async function deleteSpot(orgId: string, spotId: string): Promise<void> {
  await api.delete(`/organizations/${orgId}/spots/${spotId}`);
}

export async function updateSpotServices(
  orgId: string,
  spotId: string,
  serviceTypeIds: string[]
): Promise<Spot> {
  const response = await api.put(`/organizations/${orgId}/spots/${spotId}/services`, {
    service_type_ids: serviceTypeIds,
  });
  return response.data;
}
