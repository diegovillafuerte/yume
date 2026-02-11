'use client';

import { useState, useEffect, useRef } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import AdminLayout from '@/components/admin/AdminLayout';
import {
  simulateMessage,
  getSimulationRecipients,
  type SimulateMessageResponse,
  type SimulationRecipient,
} from '@/lib/api/simulate';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  metadata?: {
    case?: string;
    route?: string;
    sender_type?: string;
    organization_id?: string;
  };
}

const ROUTE_LABELS: Record<string, string> = {
  business_onboarding: 'Onboarding',
  business_management: 'Staff Mgmt',
  business_whatsapp: 'Business WhatsApp',
  redirect: 'Redirect',
  end_customer: 'Customer',
};

const CASE_COLORS: Record<string, string> = {
  '1': 'bg-purple-100 text-purple-700',
  '1b': 'bg-purple-100 text-purple-700',
  '2a': 'bg-blue-100 text-blue-700',
  '2b': 'bg-yellow-100 text-yellow-700',
  '3': 'bg-green-100 text-green-700',
  '4': 'bg-blue-100 text-blue-700',
  '5': 'bg-emerald-100 text-emerald-700',
};

export default function AdminSimulatePage() {
  const [recipientPhone, setRecipientPhone] = useState('');
  const [senderPhone, setSenderPhone] = useState('');
  const [senderName, setSenderName] = useState('');
  const [messageInput, setMessageInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load saved sender from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('sim_sender_phone');
    if (saved) setSenderPhone(saved);
    const savedName = localStorage.getItem('sim_sender_name');
    if (savedName) setSenderName(savedName);
  }, []);

  // Save sender to localStorage when changed
  useEffect(() => {
    if (senderPhone) localStorage.setItem('sim_sender_phone', senderPhone);
  }, [senderPhone]);
  useEffect(() => {
    if (senderName) localStorage.setItem('sim_sender_name', senderName);
  }, [senderName]);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch recipients
  const { data: recipients, isLoading: recipientsLoading, error: recipientsError } = useQuery({
    queryKey: ['simulation-recipients'],
    queryFn: getSimulationRecipients,
  });

  // Set default recipient when loaded
  useEffect(() => {
    if (recipients && recipients.length > 0 && !recipientPhone) {
      setRecipientPhone(recipients[0].phone_number);
    }
  }, [recipients, recipientPhone]);

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: simulateMessage,
    onSuccess: (data: SimulateMessageResponse) => {
      const assistantMsg: ChatMessage = {
        id: data.message_id + '_response',
        role: 'assistant',
        text: data.response_text || '(no response)',
        metadata: {
          case: data.case ?? undefined,
          route: data.route ?? undefined,
          sender_type: data.sender_type ?? undefined,
          organization_id: data.organization_id ?? undefined,
        },
      };
      setMessages((prev) => [...prev, assistantMsg]);
    },
    onError: (error: Error & { response?: { status?: number } }) => {
      const errorMsg: ChatMessage = {
        id: `error_${Date.now()}`,
        role: 'assistant',
        text: error.response?.status === 404
          ? 'Simulation not available (endpoint not found — are you in production?)'
          : `Error: ${error.message}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    },
  });

  const handleSend = () => {
    const text = messageInput.trim();
    if (!text || !recipientPhone || !senderPhone) return;

    // Add user message to chat
    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      role: 'user',
      text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setMessageInput('');

    // Send to API
    sendMutation.mutate({
      sender_phone: senderPhone,
      recipient_phone: recipientPhone,
      message_body: text,
      sender_name: senderName || undefined,
    });
  };

  const handleClear = () => {
    setMessages([]);
  };

  const selectedRecipient = recipients?.find(
    (r: SimulationRecipient) => r.phone_number === recipientPhone
  );

  return (
    <AdminLayout>
      <div className="flex gap-6 h-[calc(100vh-180px)]">
        {/* Left: Config Panel */}
        <div className="w-72 flex-shrink-0 space-y-4">
          <h2 className="text-lg font-bold text-gray-900">Simulate</h2>

          {/* Recipient */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Recipient (To)
            </label>
            {recipientsLoading ? (
              <div className="h-10 bg-gray-100 rounded animate-pulse" />
            ) : recipientsError ? (
              <p className="text-sm text-red-500">
                Failed to load recipients. Simulation may not be available.
              </p>
            ) : (
              <select
                value={recipientPhone}
                onChange={(e) => setRecipientPhone(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {recipients?.map((r: SimulationRecipient) => (
                  <option key={r.phone_number} value={r.phone_number}>
                    {r.label} ({r.phone_number})
                  </option>
                ))}
              </select>
            )}
            {selectedRecipient && (
              <p className="text-xs text-gray-400 mt-1">
                Type: {selectedRecipient.type}
              </p>
            )}
          </div>

          {/* Sender Phone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sender Phone (From)
            </label>
            <input
              type="text"
              value={senderPhone}
              onChange={(e) => setSenderPhone(e.target.value)}
              placeholder="+525512345678"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Sender Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sender Name
            </label>
            <input
              type="text"
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              placeholder="Juan Perez"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Clear button */}
          <button
            onClick={handleClear}
            className="w-full px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
          >
            Clear Conversation
          </button>

          {/* Info */}
          <div className="text-xs text-gray-400 space-y-1">
            <p>Messages go through the real routing + AI pipeline.</p>
            <p>WhatsApp delivery is mocked (no real messages sent).</p>
            <p>Multi-turn conversations work automatically.</p>
          </div>
        </div>

        {/* Right: Chat Panel */}
        <div className="flex-1 flex flex-col bg-white rounded-lg shadow overflow-hidden">
          {/* Chat messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                Send a message to start the simulation
              </div>
            )}
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[75%] rounded-lg px-4 py-2 ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                  {msg.metadata && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {msg.metadata.case && (
                        <span
                          className={`px-1.5 py-0.5 text-xs rounded font-medium ${
                            CASE_COLORS[msg.metadata.case] || 'bg-gray-100 text-gray-600'
                          }`}
                        >
                          Case {msg.metadata.case}
                        </span>
                      )}
                      {msg.metadata.route && (
                        <span className="px-1.5 py-0.5 text-xs rounded bg-gray-200 text-gray-600">
                          {ROUTE_LABELS[msg.metadata.route] || msg.metadata.route}
                        </span>
                      )}
                      {msg.metadata.sender_type && (
                        <span className="px-1.5 py-0.5 text-xs rounded bg-gray-200 text-gray-600">
                          {msg.metadata.sender_type}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {sendMutation.isPending && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-lg px-4 py-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="border-t p-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={messageInput}
                onChange={(e) => setMessageInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={
                  !senderPhone
                    ? 'Enter a sender phone number first...'
                    : 'Type a message...'
                }
                disabled={!senderPhone || !recipientPhone || sendMutation.isPending}
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-400"
              />
              <button
                onClick={handleSend}
                disabled={!messageInput.trim() || !senderPhone || !recipientPhone || sendMutation.isPending}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
