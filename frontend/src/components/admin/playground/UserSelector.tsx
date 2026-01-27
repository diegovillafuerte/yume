'use client';

import { useState, useMemo } from 'react';
import type { PlaygroundUserSummary } from '@/lib/types';

interface UserSelectorProps {
  users: PlaygroundUserSummary[];
  selectedPhone: string | null;
  onSelect: (phone: string) => void;
  isLoading?: boolean;
}

export default function UserSelector({
  users,
  selectedPhone,
  onSelect,
  isLoading,
}: UserSelectorProps) {
  const [search, setSearch] = useState('');

  const filteredUsers = useMemo(() => {
    if (!search.trim()) return users;
    const searchLower = search.toLowerCase();
    return users.filter(
      (u) =>
        u.phone_number.includes(search) ||
        u.name?.toLowerCase().includes(searchLower) ||
        u.organization_name.toLowerCase().includes(searchLower)
    );
  }, [users, search]);

  const selectedUser = users.find((u) => u.phone_number === selectedPhone);

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Select User to Emulate
      </label>

      {/* Search input */}
      <input
        type="text"
        placeholder="Search by phone, name, or org..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-500"
      />

      {/* User dropdown */}
      <select
        value={selectedPhone || ''}
        onChange={(e) => onSelect(e.target.value)}
        disabled={isLoading}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50"
      >
        <option value="">-- Select a user --</option>
        {filteredUsers.map((user) => (
          <option key={user.user_id} value={user.phone_number}>
            {user.phone_number} - {user.name || 'Unknown'} ({user.user_type}) - {user.organization_name}
          </option>
        ))}
      </select>

      {filteredUsers.length === 0 && search && (
        <p className="text-xs text-gray-500">No users match your search</p>
      )}
    </div>
  );
}
