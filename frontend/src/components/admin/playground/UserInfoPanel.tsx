'use client';

import type { PlaygroundUserDetail } from '@/lib/types';

interface UserInfoPanelProps {
  user: PlaygroundUserDetail | null;
  isLoading?: boolean;
}

export default function UserInfoPanel({ user, isLoading }: UserInfoPanelProps) {
  if (isLoading) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
        <div className="h-3 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 text-center text-gray-500 text-sm">
        Select a user to see their info
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900">{user.name || 'Unknown'}</h3>
        <span
          className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
            user.user_type === 'staff'
              ? 'bg-blue-100 text-blue-800'
              : 'bg-green-100 text-green-800'
          }`}
        >
          {user.user_type}
        </span>
      </div>

      <div className="space-y-1 text-sm">
        <div className="flex items-center gap-2 text-gray-600">
          <span className="font-mono">{user.phone_number}</span>
        </div>

        <div className="text-gray-600">
          <span className="font-medium">Org:</span> {user.organization_name}
        </div>

        {user.user_type === 'staff' && user.role && (
          <div className="text-gray-600">
            <span className="font-medium">Role:</span> {user.role}
          </div>
        )}

        {user.user_type === 'staff' && user.is_active !== null && (
          <div className="text-gray-600">
            <span className="font-medium">Status:</span>{' '}
            {user.is_active ? (
              <span className="text-green-600">Active</span>
            ) : (
              <span className="text-red-600">Inactive</span>
            )}
          </div>
        )}

        {user.user_type === 'customer' && user.appointment_count !== null && (
          <div className="text-gray-600">
            <span className="font-medium">Appointments:</span> {user.appointment_count}
          </div>
        )}
      </div>
    </div>
  );
}
