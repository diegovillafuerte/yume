'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import AdminLayout from '@/components/admin/AdminLayout';
import { getActivityFeed } from '@/lib/api/admin';

export default function AdminActivityPage() {
  const router = useRouter();

  const { data: activities, isLoading, error } = useQuery({
    queryKey: ['admin-activity'],
    queryFn: () => getActivityFeed(100),
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString('es-MX', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getActionLabel = (actionType: string) => {
    switch (actionType) {
      case 'org_created':
        return 'New organization';
      case 'appointment_pending':
        return 'Appointment created';
      case 'appointment_confirmed':
        return 'Appointment confirmed';
      case 'appointment_completed':
        return 'Appointment completed';
      case 'appointment_cancelled':
        return 'Appointment cancelled';
      case 'appointment_no_show':
        return 'No show';
      default:
        return actionType.replace(/_/g, ' ');
    }
  };

  const getActionIcon = (actionType: string) => {
    if (actionType === 'org_created') {
      return (
        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
          <span className="text-blue-600 text-sm">+</span>
        </div>
      );
    }
    if (actionType.includes('completed')) {
      return (
        <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
          <span className="text-green-600 text-sm">&#10003;</span>
        </div>
      );
    }
    if (actionType.includes('cancelled') || actionType.includes('no_show')) {
      return (
        <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
          <span className="text-red-600 text-sm">&times;</span>
        </div>
      );
    }
    return (
      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
        <span className="text-gray-600 text-sm">&#8226;</span>
      </div>
    );
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-gray-900">Activity Feed</h2>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading activity feed
          </div>
        ) : activities && activities.length > 0 ? (
          <div className="bg-white shadow rounded-lg">
            <div className="divide-y divide-gray-200">
              {activities.map((activity) => (
                <div
                  key={activity.id}
                  className="p-4 hover:bg-gray-50 cursor-pointer"
                  onClick={() => router.push(`/admin/organizations/${activity.organization_id}`)}
                >
                  <div className="flex items-start gap-4">
                    {getActionIcon(activity.action_type)}
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {getActionLabel(activity.action_type)}
                          </p>
                          <p className="text-sm text-gray-500">
                            {activity.organization_name}
                          </p>
                        </div>
                        <span className="text-xs text-gray-400">
                          {formatDate(activity.timestamp)}
                        </span>
                      </div>
                      {activity.details && Object.keys(activity.details).length > 0 && (
                        <div className="mt-2 text-xs text-gray-500">
                          {typeof activity.details.scheduled_start === 'string' && (
                            <span>
                              Scheduled: {new Date(activity.details.scheduled_start).toLocaleString('es-MX')}
                            </span>
                          )}
                          {typeof activity.details.source === 'string' && (
                            <span className="ml-2">
                              Source: {activity.details.source}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-white shadow rounded-lg p-8 text-center text-gray-500">
            No activity yet
          </div>
        )}
      </div>
    </AdminLayout>
  );
}
