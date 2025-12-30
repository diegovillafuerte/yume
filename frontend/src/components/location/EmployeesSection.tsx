'use client';

import { useState } from 'react';
import { Staff, ServiceType } from '@/lib/types';
import EmployeeModal from './EmployeeModal';

interface EmployeesSectionProps {
  staff: Staff[];
  services: ServiceType[];
  orgId: string;
  locationId: string;
}

export default function EmployeesSection({ staff, services, orgId, locationId }: EmployeesSectionProps) {
  const [selectedEmployee, setSelectedEmployee] = useState<Staff | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Empleados</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >
          + Agregar
        </button>
      </div>

      {staff.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500">No hay empleados en esta sucursal</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-4 text-blue-600 hover:text-blue-700"
          >
            Agregar el primero
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {staff.map((employee) => (
            <button
              key={employee.id}
              onClick={() => setSelectedEmployee(employee)}
              className="bg-white rounded-lg border border-gray-200 p-4 text-left hover:border-blue-300 hover:shadow-sm transition"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                  <span className="text-blue-600 font-medium">
                    {employee.name.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="min-w-0">
                  <h3 className="font-medium text-gray-900 truncate">{employee.name}</h3>
                  <p className="text-sm text-gray-500">
                    {employee.role === 'owner' ? 'Propietario' : 'Empleado'}
                  </p>
                  {employee.service_types.length > 0 && (
                    <p className="text-xs text-gray-400 mt-1 truncate">
                      {employee.service_types.map(s => s.name).join(', ')}
                    </p>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Edit/Add Modal */}
      {(selectedEmployee || showAddModal) && (
        <EmployeeModal
          employee={selectedEmployee}
          services={services}
          orgId={orgId}
          locationId={locationId}
          onClose={() => {
            setSelectedEmployee(null);
            setShowAddModal(false);
          }}
        />
      )}
    </section>
  );
}
