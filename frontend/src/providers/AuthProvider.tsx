'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Organization } from '@/lib/types';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  organization: Organization | null;
  token: string | null;
  login: (token: string, organization: Organization) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const router = useRouter();

  useEffect(() => {
    // Check for existing auth on mount
    const storedToken = localStorage.getItem('auth_token');
    const storedOrg = localStorage.getItem('organization');

    if (storedToken && storedOrg) {
      setToken(storedToken);
      try {
        setOrganization(JSON.parse(storedOrg));
      } catch {
        // Invalid stored org, clear everything
        localStorage.removeItem('auth_token');
        localStorage.removeItem('organization');
      }
    }
    setIsLoading(false);
  }, []);

  const login = (newToken: string, org: Organization) => {
    localStorage.setItem('auth_token', newToken);
    localStorage.setItem('organization', JSON.stringify(org));
    setToken(newToken);
    setOrganization(org);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('organization');
    setToken(null);
    setOrganization(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        isLoading,
        organization,
        token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
