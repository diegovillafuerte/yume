'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import AdminLayout from '@/components/admin/AdminLayout';
import { listOrganizations, impersonateOrganization, updateOrganizationStatus, deleteOrganization } from '@/lib/api/admin';
import type { AdminOrganizationSummary } from '@/lib/types';

export default function AdminOrganizationsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: organizations, isLoading, error } = useQuery({
    queryKey: ['admin-organizations', search, statusFilter],
    queryFn: () => listOrganizations({
      search: search || undefined,
      status: statusFilter || undefined
    }),
  });

  const impersonateMutation = useMutation({
    mutationFn: impersonateOrganization,
    onSuccess: (data) => {
      // Store the org token and redirect to main app
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('organization', JSON.stringify(data.organization));
      window.open('/schedule', '_blank');
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ orgId, status }: { orgId: string; status: 'active' | 'suspended' }) =>
      updateOrganizationStatus(orgId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-organizations'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteOrganization,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-organizations'] });
    },
  });

  const handleImpersonate = (org: AdminOrganizationSummary) => {
    if (confirm(`Login as "${org.name || '(Sin nombre)' }"? This will open in a new tab.`)) {
      impersonateMutation.mutate(org.id);
    }
  };

  const handleToggleStatus = (org: AdminOrganizationSummary) => {
    const newStatus = org.status === 'suspended' ? 'active' : 'suspended';
    const action = newStatus === 'suspended' ? 'suspend' : 'reactivate';
    if (confirm(`Are you sure you want to ${action} "${org.name || '(Sin nombre)'}"?`)) {
      statusMutation.mutate({ orgId: org.id, status: newStatus });
    }
  };

  const handleDelete = (org: AdminOrganizationSummary) => {
    if (confirm(`Are you sure you want to PERMANENTLY DELETE "${org.name || '(Sin nombre)'}" and ALL associated data? This cannot be undone.`)) {
      deleteMutation.mutate(org.id);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800';
      case 'onboarding':
        return 'bg-yellow-100 text-yellow-800';
      case 'suspended':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">Organizations</h2>
        </div>

        {/* Filters */}
        <div className="flex gap-4">
          <input
            type="text"
            placeholder="Search by name or phone..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-500"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="onboarding">Onboarding</option>
            <option value="suspended">Suspended</option>
          </select>
        </div>

        {/* Organizations List */}
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading organizations
          </div>
        ) : organizations && organizations.length > 0 ? (
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Organization
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Assigned Number
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {organizations.map((org) => (
                  <tr key={org.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{org.name || '(Onboarding)'}</div>
                      <div className="text-xs text-gray-500">{org.id}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {org.phone_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeClass(org.status)}`}>
                        {org.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      {org.whatsapp_phone_number ? (
                        <span className="text-green-600 font-mono">{org.whatsapp_phone_number}</span>
                      ) : (
                        <span className="text-gray-400">&mdash;</span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(org.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                      <button
                        onClick={() => router.push(`/admin/organizations/${org.id}`)}
                        className="text-gray-600 hover:text-gray-900"
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleImpersonate(org)}
                        disabled={impersonateMutation.isPending}
                        className="text-blue-600 hover:text-blue-900 disabled:opacity-50"
                      >
                        Login As
                      </button>
                      <button
                        onClick={() => handleToggleStatus(org)}
                        disabled={statusMutation.isPending}
                        className={`${
                          org.status === 'suspended'
                            ? 'text-green-600 hover:text-green-900'
                            : 'text-red-600 hover:text-red-900'
                        } disabled:opacity-50`}
                      >
                        {org.status === 'suspended' ? 'Activate' : 'Suspend'}
                      </button>
                      <button
                        onClick={() => handleDelete(org)}
                        disabled={deleteMutation.isPending}
                        className="text-red-600 hover:text-red-900 disabled:opacity-50"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
            No organizations found
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
