'use client';

import { useState, useCallback } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import UserSelector from '@/components/admin/playground/UserSelector';
import UserInfoPanel from '@/components/admin/playground/UserInfoPanel';
import ChatEmulator from '@/components/admin/playground/ChatEmulator';
import ExecutionLogger from '@/components/admin/playground/ExecutionLogger';
import {
  listPlaygroundUsers,
  getPlaygroundUser,
  sendPlaygroundMessage,
  listPlaygroundExchanges,
  getTraceDetail,
} from '@/lib/api/playground';
import type { TraceExchangeSummary } from '@/lib/types';

interface ChatMessage {
  id: string;
  content: string;
  direction: 'inbound' | 'outbound';
  timestamp: Date;
}

export default function PlaygroundPage() {
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [exchanges, setExchanges] = useState<TraceExchangeSummary[]>([]);

  // Fetch all users for dropdown
  const { data: users = [], isLoading: usersLoading } = useQuery({
    queryKey: ['playground-users'],
    queryFn: () => listPlaygroundUsers({ limit: 200 }),
  });

  // Fetch selected user details
  const { data: userDetail, isLoading: userDetailLoading } = useQuery({
    queryKey: ['playground-user', selectedPhone],
    queryFn: () => (selectedPhone ? getPlaygroundUser(selectedPhone) : null),
    enabled: !!selectedPhone,
  });

  // Fetch recent exchanges when user is selected
  const { data: recentExchanges, isLoading: exchangesLoading } = useQuery({
    queryKey: ['playground-exchanges', userDetail?.organization_id],
    queryFn: () =>
      userDetail?.organization_id
        ? listPlaygroundExchanges({ org_id: userDetail.organization_id, limit: 20 })
        : null,
    enabled: !!userDetail?.organization_id,
  });

  // Update exchanges when recent exchanges load
  const handleUserSelect = (phone: string) => {
    setSelectedPhone(phone);
    setChatMessages([]); // Clear chat when user changes
    setExchanges([]); // Clear exchanges
  };

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      if (!selectedPhone) throw new Error('No user selected');
      return sendPlaygroundMessage({
        phone_number: selectedPhone,
        message_content: content,
      });
    },
    onSuccess: async (result, content) => {
      // Add user's message to chat
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        content,
        direction: 'inbound',
        timestamp: new Date(),
      };

      // Add AI's response to chat
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        content: result.response_text,
        direction: 'outbound',
        timestamp: new Date(),
      };

      setChatMessages((prev) => [...prev, userMessage, aiMessage]);

      // Fetch updated exchanges
      if (userDetail?.organization_id) {
        const updatedExchanges = await listPlaygroundExchanges({
          org_id: userDetail.organization_id,
          limit: 20,
        });
        setExchanges(updatedExchanges.exchanges);
      }
    },
  });

  const handleSendMessage = async (content: string) => {
    await sendMutation.mutateAsync(content);
  };

  const handleLoadTraceDetail = useCallback(async (traceId: string) => {
    return getTraceDetail(traceId);
  }, []);

  // Combine fetched exchanges with current session exchanges
  const displayExchanges =
    exchanges.length > 0 ? exchanges : recentExchanges?.exchanges || [];

  return (
    <AdminLayout>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Conversation Playground</h2>
          <p className="text-sm text-gray-500 mt-1">
            Emulate conversations and debug the AI pipeline execution
          </p>
        </div>

        {/* Main layout: Two columns */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left column: User selection, info, and chat (~40%) */}
          <div className="lg:col-span-2 space-y-4">
            {/* User selector */}
            <UserSelector
              users={users}
              selectedPhone={selectedPhone}
              onSelect={handleUserSelect}
              isLoading={usersLoading}
            />

            {/* User info panel */}
            <UserInfoPanel user={userDetail || null} isLoading={userDetailLoading} />

            {/* Chat emulator */}
            <ChatEmulator
              messages={chatMessages}
              onSendMessage={handleSendMessage}
              isSending={sendMutation.isPending}
              disabled={!selectedPhone}
            />
          </div>

          {/* Right column: Execution logger (~60%) */}
          <div className="lg:col-span-3">
            <ExecutionLogger
              exchanges={displayExchanges}
              isLoading={exchangesLoading && !exchanges.length}
              onLoadTraceDetail={handleLoadTraceDetail}
            />
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
