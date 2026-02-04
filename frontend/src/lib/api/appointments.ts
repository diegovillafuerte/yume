import api from './client';
import { Appointment } from '@/lib/types';

export interface AppointmentFilters {
  start_date?: string;
  end_date?: string;
  customer_id?: string;
  staff_id?: string;
}

export async function getAppointments(
  orgId: string,
  filters?: AppointmentFilters
): Promise<Appointment[]> {
  const response = await api.get(`/organizations/${orgId}/appointments`, {
    params: filters,
  });
  return response.data;
}

export async function getAppointment(
  orgId: string,
  appointmentId: string
): Promise<Appointment> {
  const response = await api.get(`/organizations/${orgId}/appointments/${appointmentId}`);
  return response.data;
}

export async function cancelAppointment(
  orgId: string,
  appointmentId: string,
  reason?: string
): Promise<Appointment> {
  const response = await api.post(
    `/organizations/${orgId}/appointments/${appointmentId}/cancel`,
    { cancellation_reason: reason }
  );
  return response.data;
}

export async function completeAppointment(
  orgId: string,
  appointmentId: string,
  notes?: string
): Promise<Appointment> {
  const response = await api.post(
    `/organizations/${orgId}/appointments/${appointmentId}/complete`,
    { notes }
  );
  return response.data;
}

export async function markNoShow(
  orgId: string,
  appointmentId: string
): Promise<Appointment> {
  const response = await api.patch(
    `/organizations/${orgId}/appointments/${appointmentId}`,
    { status: 'no_show' }
  );
  return response.data;
}
