'use client';

import { useState } from 'react';
import { ServiceType } from '@/lib/types';
import ServiceModal from './ServiceModal';

interface ServicesSectionProps {
  services: ServiceType[];
  orgId: string;
}

function formatPrice(cents: number, currency: string = 'MXN'): string {
  const amount = cents / 100;
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency,
  }).format(amount);
}

export default function ServicesSection({ services, orgId }: ServicesSectionProps) {
  const [selectedService, setSelectedService] = useState<ServiceType | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const activeServices = services.filter(s => s.is_active);

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Servicios</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >
          + Agregar
        </button>
      </div>

      {activeServices.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500">No hay servicios configurados</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-4 text-blue-600 hover:text-blue-700"
          >
            Agregar el primero
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeServices.map((service) => (
            <button
              key={service.id}
              onClick={() => setSelectedService(service)}
              className="bg-white rounded-lg border border-gray-200 p-4 text-left hover:border-blue-300 hover:shadow-sm transition"
            >
              <h3 className="font-medium text-gray-900">{service.name}</h3>
              {service.description && (
                <p className="text-sm text-gray-500 mt-1 line-clamp-2">{service.description}</p>
              )}
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                <span className="text-sm text-gray-500">{service.duration_minutes} min</span>
                <span className="font-medium text-gray-900">
                  {formatPrice(service.price_cents, service.currency)}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Edit/Add Modal */}
      {(selectedService || showAddModal) && (
        <ServiceModal
          service={selectedService}
          orgId={orgId}
          onClose={() => {
            setSelectedService(null);
            setShowAddModal(false);
          }}
        />
      )}
    </section>
  );
}
