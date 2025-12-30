'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import AdminLayout from '@/components/admin/AdminLayout';
import { getConversation } from '@/lib/api/admin';
import type { AdminMessageDetail } from '@/lib/types';

export default function AdminConversationDetailPage() {
  const { id } = useParams();
  const router = useRouter();

  const { data: conversation, isLoading, error } = useQuery({
    queryKey: ['admin-conversation', id],
    queryFn: () => getConversation(id as string),
    enabled: !!id,
  });

  const formatTime = (dateString: string) => {
    return new Date(dateString).toLocaleTimeString('es-MX', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('es-MX', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const getSenderLabel = (senderType: string) => {
    switch (senderType) {
      case 'customer':
        return 'Customer';
      case 'ai':
        return 'AI (Yume)';
      case 'staff':
        return 'Staff';
      default:
        return senderType;
    }
  };

  const getMessageStyle = (direction: string, senderType: string) => {
    if (direction === 'inbound') {
      return 'bg-gray-100 text-gray-900 mr-auto';
    }
    if (senderType === 'ai') {
      return 'bg-blue-500 text-white ml-auto';
    }
    return 'bg-green-500 text-white ml-auto';
  };

  // Group messages by date
  const groupMessagesByDate = (messages: AdminMessageDetail[] | undefined) => {
    if (!messages) return {};

    const groups: Record<string, AdminMessageDetail[]> = {};
    messages.forEach((msg) => {
      const date = new Date(msg.created_at).toDateString();
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(msg);
    });
    return groups;
  };

  return (
    <AdminLayout>
      <div className="space-y-6">
        {/* Back button */}
        <button
          onClick={() => router.back()}
          className="text-gray-600 hover:text-gray-900 flex items-center gap-2"
        >
          &larr; Back to Conversations
        </button>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-4 border-gray-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="bg-red-50 text-red-600 p-4 rounded-lg">
            Error loading conversation
          </div>
        ) : conversation ? (
          <>
            {/* Header */}
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">
                    Conversation with {conversation.customer_name || conversation.customer_phone}
                  </h2>
                  <p className="text-sm text-gray-500 mt-1">
                    {conversation.organization_name} | {conversation.customer_phone}
                  </p>
                </div>
                <span className={`inline-flex px-3 py-1 text-sm font-semibold rounded-full ${
                  conversation.status === 'active'
                    ? 'bg-green-100 text-green-800'
                    : conversation.status === 'handed_off'
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {conversation.status}
                </span>
              </div>
              <p className="text-sm text-gray-500 mt-2">
                {conversation.message_count} messages
              </p>
            </div>

            {/* Messages */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Messages</h3>

              {conversation.messages.length === 0 ? (
                <p className="text-gray-500 text-center py-8">No messages yet</p>
              ) : (
                <div className="space-y-6">
                  {Object.entries(groupMessagesByDate(conversation.messages)).map(([date, messages]) => (
                    <div key={date}>
                      {/* Date separator */}
                      <div className="flex items-center justify-center mb-4">
                        <span className="bg-gray-200 text-gray-600 text-xs px-3 py-1 rounded-full">
                          {formatDate(messages[0].created_at)}
                        </span>
                      </div>

                      {/* Messages for this date */}
                      <div className="space-y-3">
                        {messages.map((msg) => (
                          <div
                            key={msg.id}
                            className={`max-w-[70%] rounded-lg p-3 ${getMessageStyle(msg.direction, msg.sender_type)}`}
                          >
                            <div className="text-xs opacity-75 mb-1">
                              {getSenderLabel(msg.sender_type)} - {formatTime(msg.created_at)}
                            </div>
                            <p className="whitespace-pre-wrap break-words">
                              {msg.content || `[${msg.content_type}]`}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </AdminLayout>
  );
}
