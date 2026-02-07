'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import { listPendingNumberOrganizations, assignWhatsAppNumber } from '@/lib/api/admin';
import type { PendingNumberOrg } from '@/lib/types';

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('es-MX', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

interface AssignModalProps {
  org: PendingNumberOrg;
  onClose: () => void;
  onAssign: (phoneNumber: string, senderSid: string) => void;
  isLoading: boolean;
}

function AssignModal({ org, onClose, onAssign, isLoading }: AssignModalProps) {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [senderSid, setSenderSid] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAssign(phoneNumber, senderSid);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Assign WhatsApp Number
        </h3>
        <p className="text-sm text-gray-600 mb-4">
          Assign a number to <strong>{org.name || 'Unnamed Business'}</strong>
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Phone Number (E.164)
            </label>
            <input
              type="text"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+525512345678"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              Include country code (e.g., +52 for Mexico)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sender SID
            </label>
            <input
              type="text"
              value={senderSid}
              onChange={(e) => setSenderSid(e.target.value)}
              placeholder="XE..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              required
            />
            <p className="text-xs text-gray-500 mt-1">
              From Twilio Console &rarr; Messaging &rarr; Senders
            </p>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
              disabled={isLoading || !phoneNumber || !senderSid}
            >
              {isLoading ? 'Assigning...' : 'Assign Number'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function PendingNumbersPage() {
  const queryClient = useQueryClient();
  const [selectedOrg, setSelectedOrg] = useState<PendingNumberOrg | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const { data: orgs, isLoading, error } = useQuery({
    queryKey: ['pending-number-orgs'],
    queryFn: listPendingNumberOrganizations,
  });

  const assignMutation = useMutation({
    mutationFn: ({
      orgId,
      phoneNumber,
      senderSid,
    }: {
      orgId: string;
      phoneNumber: string;
      senderSid: string;
    }) => assignWhatsAppNumber(orgId, { phone_number: phoneNumber, sender_sid: senderSid }),
    onSuccess: (data) => {
      setSuccessMessage(`Number ${data.phone_number} assigned to ${data.organization_name || 'organization'}`);
      setSelectedOrg(null);
      queryClient.invalidateQueries({ queryKey: ['pending-number-orgs'] });
      setTimeout(() => setSuccessMessage(null), 5000);
    },
    onError: (error) => {
      console.error('Failed to assign number:', error);
    },
  });

  const handleAssign = (phoneNumber: string, senderSid: string) => {
    if (selectedOrg) {
      assignMutation.mutate({
        orgId: selectedOrg.id,
        phoneNumber,
        senderSid,
      });
    }
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Pending Number Assignments</h2>
          <div className="text-sm text-gray-500">
            {orgs?.length || 0} organizations waiting
          </div>
        </div>

        {successMessage && (
          <div className="bg-green-50 text-green-800 px-4 py-3 rounded-lg">
            {successMessage}
          </div>
        )}

        {assignMutation.isError && (
          <div className="bg-red-50 text-red-600 px-4 py-3 rounded-lg">
            Failed to assign number. Please try again.
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading pending organizations
          </div>
        ) : orgs && orgs.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-4xl mb-4">&#128079;</div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              No pending assignments
            </h3>
            <p className="text-gray-500">
              All organizations have been assigned WhatsApp numbers.
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Business
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Owner Phone
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {orgs?.map((org) => (
                  <tr key={org.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">
                        {org.name || 'Unnamed Business'}
                      </div>
                      {org.owner_name && (
                        <div className="text-sm text-gray-500">{org.owner_name}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {org.phone_number}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(org.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                        Pending
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <button
                        onClick={() => setSelectedOrg(org)}
                        className="text-sm font-medium text-gray-900 hover:text-gray-700"
                      >
                        Assign Number
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="bg-gray-50 rounded-lg p-6">
          <h3 className="font-medium text-gray-900 mb-3">How to assign a number</h3>
          <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
            <li>Go to Twilio Console &rarr; Messaging &rarr; Senders</li>
            <li>Create a new WhatsApp sender or find an existing one</li>
            <li>Copy the phone number (E.164 format) and Sender SID</li>
            <li>Click &quot;Assign Number&quot; next to the organization</li>
            <li>Enter the phone number and Sender SID</li>
            <li>The organization will be notified via WhatsApp</li>
          </ol>
        </div>
      </div>

      {selectedOrg && (
        <AssignModal
          org={selectedOrg}
          onClose={() => setSelectedOrg(null)}
          onAssign={handleAssign}
          isLoading={assignMutation.isPending}
        />
      )}
    </AdminLayout>
  );
}
