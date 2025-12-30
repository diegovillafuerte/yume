'use client';

import { useQuery } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import { getAdminStats } from '@/lib/api/admin';

export default function AdminDashboardPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: getAdminStats,
  });

  return (
    <AdminLayout>
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading stats
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Organizations Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Organizations</h3>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.organizations.total}</p>
              <div className="mt-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Active</span>
                  <span className="text-green-600 font-medium">{stats.organizations.active}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Onboarding</span>
                  <span className="text-yellow-600 font-medium">{stats.organizations.onboarding}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Suspended</span>
                  <span className="text-red-600 font-medium">{stats.organizations.suspended}</span>
                </div>
              </div>
            </div>

            {/* Appointments Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Appointments</h3>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.appointments.total}</p>
              <div className="mt-4 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Completed</span>
                  <span className="text-green-600 font-medium">{stats.appointments.completed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Pending</span>
                  <span className="text-yellow-600 font-medium">{stats.appointments.pending}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Cancelled</span>
                  <span className="text-red-600 font-medium">{stats.appointments.cancelled}</span>
                </div>
              </div>
            </div>

            {/* Customers Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Customers</h3>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.customers_total}</p>
              <p className="text-sm text-gray-500 mt-4">Total registered customers</p>
            </div>

            {/* Messages Card */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-sm font-medium text-gray-500 uppercase">Messages</h3>
              <p className="text-3xl font-bold text-gray-900 mt-2">{stats.messages_total}</p>
              <p className="text-sm text-gray-500 mt-4">Total WhatsApp messages</p>
            </div>
          </div>
        ) : null}
      </div>
    </AdminLayout>
  );
}
