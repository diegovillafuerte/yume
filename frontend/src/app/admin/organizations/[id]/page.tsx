'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import AdminLayout from '@/components/admin/AdminLayout';
import { getOrganization, impersonateOrganization, updateOrganizationStatus, listConversations } from '@/lib/api/admin';

export default function AdminOrganizationDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: org, isLoading, error } = useQuery({
    queryKey: ['admin-organization', id],
    queryFn: () => getOrganization(id as string),
    enabled: !!id,
  });

  const { data: conversations } = useQuery({
    queryKey: ['admin-org-conversations', id],
    queryFn: () => listConversations({ org_id: id as string, limit: 5 }),
    enabled: !!id,
  });

  const impersonateMutation = useMutation({
    mutationFn: impersonateOrganization,
    onSuccess: (data) => {
      localStorage.setItem('auth_token', data.access_token);
      localStorage.setItem('organization', JSON.stringify(data.organization));
      window.open('/schedule', '_blank');
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ orgId, status }: { orgId: string; status: 'active' | 'suspended' }) =>
      updateOrganizationStatus(orgId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-organization', id] });
    },
  });

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
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
        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="text-gray-600 hover:text-gray-900 flex items-center gap-2"
        >
          &larr; Back to Organizations
        </button>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading organization
          </div>
        ) : org ? (
          <>
            {/* Header */}
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">{org.name}</h2>
                  <p className="text-sm text-gray-500 mt-1">{org.id}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => impersonateMutation.mutate(org.id)}
                    disabled={impersonateMutation.isPending}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    Login As
                  </button>
                  <button
                    onClick={() => {
                      const newStatus = org.status === 'suspended' ? 'active' : 'suspended';
                      if (confirm(`Are you sure you want to ${newStatus === 'suspended' ? 'suspend' : 'reactivate'} this organization?`)) {
                        statusMutation.mutate({ orgId: org.id, status: newStatus });
                      }
                    }}
                    disabled={statusMutation.isPending}
                    className={`px-4 py-2 rounded-lg ${
                      org.status === 'suspended'
                        ? 'bg-green-600 text-white hover:bg-green-700'
                        : 'bg-red-600 text-white hover:bg-red-700'
                    } disabled:opacity-50`}
                  >
                    {org.status === 'suspended' ? 'Activate' : 'Suspend'}
                  </button>
                </div>
              </div>

              <div className="mt-4 flex gap-4">
                <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${getStatusBadgeClass(org.status)}`}>
                  {org.status}
                </span>
                {org.whatsapp_connected ? (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-green-100 text-green-800">
                    WhatsApp Connected
                  </span>
                ) : (
                  <span className="inline-flex px-3 py-1 text-sm font-semibold rounded-full bg-gray-100 text-gray-800">
                    WhatsApp Not Connected
                  </span>
                )}
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white shadow rounded-lg p-4">
                <p className="text-sm text-gray-500">Locations</p>
                <p className="text-2xl font-bold text-gray-900">{org.location_count}</p>
              </div>
              <div className="bg-white shadow rounded-lg p-4">
                <p className="text-sm text-gray-500">Staff</p>
                <p className="text-2xl font-bold text-gray-900">{org.staff_count}</p>
              </div>
              <div className="bg-white shadow rounded-lg p-4">
                <p className="text-sm text-gray-500">Customers</p>
                <p className="text-2xl font-bold text-gray-900">{org.customer_count}</p>
              </div>
              <div className="bg-white shadow rounded-lg p-4">
                <p className="text-sm text-gray-500">Appointments</p>
                <p className="text-2xl font-bold text-gray-900">{org.appointment_count}</p>
              </div>
            </div>

            {/* Details */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Details</h3>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <dt className="text-sm text-gray-500">Phone</dt>
                  <dd className="text-sm font-medium text-gray-900">{org.phone_country_code}{org.phone_number}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-500">Timezone</dt>
                  <dd className="text-sm font-medium text-gray-900">{org.timezone}</dd>
                </div>
                <div>
                  <dt className="text-sm text-gray-500">Created</dt>
                  <dd className="text-sm font-medium text-gray-900">{formatDate(org.created_at)}</dd>
                </div>
              </dl>
            </div>

            {/* Recent Conversations */}
            {conversations && conversations.length > 0 && (
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Recent Conversations</h3>
                  <button
                    onClick={() => router.push(`/admin/conversations?org_id=${org.id}`)}
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    View All
                  </button>
                </div>
                <div className="space-y-3">
                  {conversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => router.push(`/admin/conversations/${conv.id}`)}
                      className="flex justify-between items-center p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100"
                    >
                      <div>
                        <p className="text-sm font-medium text-gray-900">
                          {conv.customer_name || conv.customer_phone}
                        </p>
                        <p className="text-xs text-gray-500">{conv.message_count} messages</p>
                      </div>
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        conv.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {conv.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>
    </AdminLayout>
  );
}
