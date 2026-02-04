import api from './client';
import { Location, LocationCreate, LocationUpdate } from '@/lib/types';

export async function getLocations(orgId: string): Promise<Location[]> {
  const response = await api.get(`/organizations/${orgId}/locations`);
  return response.data;
}

export async function createLocation(orgId: string, data: LocationCreate): Promise<Location> {
  const response = await api.post(`/organizations/${orgId}/locations`, data);
  return response.data;
}

export async function updateLocation(
  orgId: string,
  locationId: string,
  data: LocationUpdate
): Promise<Location> {
  const response = await api.patch(`/organizations/${orgId}/locations/${locationId}`, data);
  return response.data;
}

export async function deleteLocation(orgId: string, locationId: string): Promise<void> {
  await api.delete(`/organizations/${orgId}/locations/${locationId}`);
}
