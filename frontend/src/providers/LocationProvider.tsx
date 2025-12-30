'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getLocations } from '@/lib/api/locations';
import { useAuth } from './AuthProvider';
import { Location } from '@/lib/types';

interface LocationContextType {
  locations: Location[];
  selectedLocation: Location | null;
  isLoading: boolean;
  selectLocation: (location: Location) => void;
}

const LocationContext = createContext<LocationContextType | undefined>(undefined);

export function LocationProvider({ children }: { children: React.ReactNode }) {
  const { organization, isAuthenticated } = useAuth();
  const [selectedLocation, setSelectedLocation] = useState<Location | null>(null);

  const { data: locations = [], isLoading } = useQuery({
    queryKey: ['locations', organization?.id],
    queryFn: () => getLocations(organization!.id),
    enabled: isAuthenticated && !!organization?.id,
  });

  // Set initial location from localStorage or default to primary
  useEffect(() => {
    if (locations.length > 0 && !selectedLocation) {
      const storedLocationId = localStorage.getItem('selected_location_id');

      if (storedLocationId) {
        const stored = locations.find((l) => l.id === storedLocationId);
        if (stored) {
          setSelectedLocation(stored);
          return;
        }
      }

      // Default to primary location, or first location
      const primary = locations.find((l) => l.is_primary) || locations[0];
      setSelectedLocation(primary);
      localStorage.setItem('selected_location_id', primary.id);
    }
  }, [locations, selectedLocation]);

  const selectLocation = (location: Location) => {
    setSelectedLocation(location);
    localStorage.setItem('selected_location_id', location.id);
  };

  return (
    <LocationContext.Provider
      value={{
        locations,
        selectedLocation,
        isLoading,
        selectLocation,
      }}
    >
      {children}
    </LocationContext.Provider>
  );
}

export function useLocation() {
  const context = useContext(LocationContext);
  if (context === undefined) {
    throw new Error('useLocation must be used within a LocationProvider');
  }
  return context;
}
