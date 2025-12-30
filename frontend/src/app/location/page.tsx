'use client';

import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuth } from '@/providers/AuthProvider';
import { useLocation } from '@/providers/LocationProvider';
import { useQuery } from '@tanstack/react-query';
import { getStaffList } from '@/lib/api/staff';
import { getServices } from '@/lib/api/services';
import { getSpots } from '@/lib/api/spots';
import EmployeesSection from '@/components/location/EmployeesSection';
import ServicesSection from '@/components/location/ServicesSection';
import SpotsSection from '@/components/location/SpotsSection';

export default function LocationPage() {
  const { organization } = useAuth();
  const { selectedLocation } = useLocation();

  const orgId = organization?.id;
  const locationId = selectedLocation?.id;

  // Fetch staff for this location
  const { data: staff = [], isLoading: staffLoading } = useQuery({
    queryKey: ['staff', orgId, locationId],
    queryFn: () => getStaffList(orgId!, locationId),
    enabled: !!orgId && !!locationId,
  });

  // Fetch services for this organization
  const { data: services = [], isLoading: servicesLoading } = useQuery({
    queryKey: ['services', orgId],
    queryFn: () => getServices(orgId!),
    enabled: !!orgId,
  });

  // Fetch spots for this location
  const { data: spots = [], isLoading: spotsLoading } = useQuery({
    queryKey: ['spots', orgId, locationId],
    queryFn: () => getSpots(orgId!, locationId!, false),
    enabled: !!orgId && !!locationId,
  });

  const isLoading = staffLoading || servicesLoading || spotsLoading;

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {selectedLocation?.name || 'Sucursal'}
          </h1>
          {selectedLocation?.address && (
            <p className="text-gray-600 mt-1">{selectedLocation.address}</p>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          </div>
        ) : (
          <>
            {/* Empleados Section */}
            <EmployeesSection
              staff={staff}
              services={services}
              orgId={orgId!}
              locationId={locationId!}
            />

            {/* Servicios Section */}
            <ServicesSection
              services={services}
              orgId={orgId!}
            />

            {/* Estaciones Section */}
            <SpotsSection
              spots={spots}
              services={services}
              orgId={orgId!}
              locationId={locationId!}
            />
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
