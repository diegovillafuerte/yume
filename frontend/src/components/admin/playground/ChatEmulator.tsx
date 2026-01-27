'use client';

import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  content: string;
  direction: 'inbound' | 'outbound';
  timestamp: Date;
}

interface ChatEmulatorProps {
  messages: Message[];
  onSendMessage: (content: string) => Promise<void>;
  isSending: boolean;
  disabled?: boolean;
}

export default function ChatEmulator({
  messages,
  onSendMessage,
  isSending,
  disabled,
}: ChatEmulatorProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isSending || disabled) return;

    const content = inputValue.trim();
    setInputValue('');
    await onSendMessage(content);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('es-MX', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex flex-col h-full bg-gray-100 rounded-lg overflow-hidden">
      {/* Chat header */}
      <div className="bg-green-700 text-white px-4 py-3">
        <h3 className="font-medium">Chat Emulator</h3>
        <p className="text-xs text-green-200">
          Messages sent here process through the real AI pipeline
        </p>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[300px] max-h-[500px]">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 text-sm py-8">
            No messages yet. Send a message to start the conversation.
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${
                msg.direction === 'inbound' ? 'justify-end' : 'justify-start'
              }`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.direction === 'inbound'
                    ? 'bg-green-200 text-gray-800'
                    : 'bg-white text-gray-800 shadow-sm'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                <p
                  className={`text-xs mt-1 ${
                    msg.direction === 'inbound' ? 'text-green-700' : 'text-gray-400'
                  }`}
                >
                  {formatTime(msg.timestamp)}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="border-t bg-white p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={disabled ? 'Select a user first' : 'Type a message...'}
            disabled={disabled || isSending}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:bg-gray-100"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isSending || disabled}
            className="px-6 py-2 bg-green-600 text-white rounded-full text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSending ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Sending
              </span>
            ) : (
              'Send'
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
