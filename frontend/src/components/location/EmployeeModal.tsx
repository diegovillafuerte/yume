'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Staff, ServiceType, StaffCreate, StaffUpdate } from '@/lib/types';
import { createStaff, updateStaff, deleteStaff, updateStaffServices } from '@/lib/api/staff';

interface EmployeeModalProps {
  employee: Staff | null;
  services: ServiceType[];
  orgId: string;
  locationId: string;
  onClose: () => void;
}

export default function EmployeeModal({ employee, services, orgId, locationId, onClose }: EmployeeModalProps) {
  const queryClient = useQueryClient();
  const isEditing = !!employee;

  const [formData, setFormData] = useState({
    name: employee?.name || '',
    phone_number: employee?.phone_number || '',
    role: (employee?.role || 'employee') as 'owner' | 'employee',
  });
  const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>(
    employee?.service_types.map(s => s.id) || []
  );

  const createMutation = useMutation({
    mutationFn: (data: StaffCreate) => createStaff(orgId, data),
    onSuccess: async (newStaff) => {
      if (selectedServiceIds.length > 0) {
        await updateStaffServices(orgId, newStaff.id, selectedServiceIds);
      }
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      onClose();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: StaffUpdate) => updateStaff(orgId, employee!.id, data),
    onSuccess: async () => {
      await updateStaffServices(orgId, employee!.id, selectedServiceIds);
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      onClose();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteStaff(orgId, employee!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['staff'] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isEditing) {
      updateMutation.mutate(formData);
    } else {
      createMutation.mutate({
        ...formData,
        location_id: locationId,
      });
    }
  };

  const toggleService = (serviceId: string) => {
    setSelectedServiceIds(prev =>
      prev.includes(serviceId)
        ? prev.filter(id => id !== serviceId)
        : [...prev, serviceId]
    );
  };

  const isLoading = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Editar Empleado' : 'Nuevo Empleado'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">WhatsApp</label>
            <input
              type="tel"
              value={formData.phone_number}
              onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
              placeholder="+52 55 1234 5678"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value as 'owner' | 'employee' })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="employee">Empleado</option>
              <option value="owner">Propietario</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Servicios que realiza</label>
            <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-3">
              {services.filter(s => s.is_active).map((service) => (
                <label key={service.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedServiceIds.includes(service.id)}
                    onChange={() => toggleService(service.id)}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{service.name}</span>
                </label>
              ))}
              {services.filter(s => s.is_active).length === 0 && (
                <p className="text-sm text-gray-500">No hay servicios disponibles</p>
              )}
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            {isEditing && (
              <button
                type="button"
                onClick={() => {
                  if (confirm('¿Eliminar este empleado?')) {
                    deleteMutation.mutate();
                  }
                }}
                disabled={isLoading}
                className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition"
              >
                Eliminar
              </button>
            )}
            <div className="flex-1" />
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {isLoading ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
