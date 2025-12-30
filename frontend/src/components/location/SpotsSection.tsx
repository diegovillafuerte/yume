'use client';

import { useState } from 'react';
import { Spot, ServiceType } from '@/lib/types';
import SpotModal from './SpotModal';

interface SpotsSectionProps {
  spots: Spot[];
  services: ServiceType[];
  orgId: string;
  locationId: string;
}

export default function SpotsSection({ spots, services, orgId, locationId }: SpotsSectionProps) {
  const [selectedSpot, setSelectedSpot] = useState<Spot | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const activeSpots = spots.filter(s => s.is_active);

  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Estaciones de Trabajo</h2>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
        >
          + Agregar
        </button>
      </div>

      {activeSpots.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-500">No hay estaciones configuradas</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-4 text-blue-600 hover:text-blue-700"
          >
            Agregar la primera
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeSpots.map((spot) => (
            <button
              key={spot.id}
              onClick={() => setSelectedSpot(spot)}
              className="bg-white rounded-lg border border-gray-200 p-4 text-left hover:border-blue-300 hover:shadow-sm transition"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                </div>
                <div className="min-w-0">
                  <h3 className="font-medium text-gray-900">{spot.name}</h3>
                  {spot.description && (
                    <p className="text-sm text-gray-500 truncate">{spot.description}</p>
                  )}
                  {spot.service_types.length > 0 && (
                    <p className="text-xs text-gray-400 mt-1 truncate">
                      {spot.service_types.map(s => s.name).join(', ')}
                    </p>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Edit/Add Modal */}
      {(selectedSpot || showAddModal) && (
        <SpotModal
          spot={selectedSpot}
          services={services}
          orgId={orgId}
          locationId={locationId}
          onClose={() => {
            setSelectedSpot(null);
            setShowAddModal(false);
          }}
        />
      )}
    </section>
  );
}
