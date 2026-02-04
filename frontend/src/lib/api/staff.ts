import api from './client';
import { Staff, StaffCreate, StaffUpdate } from '@/lib/types';

export async function getStaffList(orgId: string, locationId?: string): Promise<Staff[]> {
  const response = await api.get(`/organizations/${orgId}/staff`, {
    params: locationId ? { location_id: locationId } : undefined,
  });
  return response.data;
}

export async function createStaff(orgId: string, data: StaffCreate): Promise<Staff> {
  const response = await api.post(`/organizations/${orgId}/staff`, data);
  return response.data;
}

export async function updateStaff(
  orgId: string,
  staffId: string,
  data: StaffUpdate
): Promise<Staff> {
  const response = await api.patch(`/organizations/${orgId}/staff/${staffId}`, data);
  return response.data;
}

export async function deleteStaff(orgId: string, staffId: string): Promise<void> {
  await api.delete(`/organizations/${orgId}/staff/${staffId}`);
}

export async function updateStaffServices(
  orgId: string,
  staffId: string,
  serviceTypeIds: string[]
): Promise<Staff> {
  const response = await api.put(`/organizations/${orgId}/staff/${staffId}/services`, {
    service_type_ids: serviceTypeIds,
  });
  return response.data;
}
