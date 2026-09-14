'use client';

import React, { useState } from 'react';
import { MessageSquare, X, Send, Bot, User, ShieldCheck, Sparkles, CheckCircle } from 'lucide-react';
import { userService } from '../services/userService';

interface Message {
  sender: 'bot' | 'user';
  text: string;
  autoApproved?: boolean;
}

export const AiAssistantDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'bot',
      text: 'Hello! I am Buildora\'s AI HR Assistant. You can ask me company policy questions or request paid leave (requests under 3 days are auto-cleared!).',
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const userText = prompt.trim();
    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setPrompt('');
    setLoading(true);

    try {
      const res = await userService.askHRAssistant(userText);
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: res.answer,
          autoApproved: res.auto_approved_leave,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: 'Sorry, I encountered an issue retrieving policy information. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Bottom-Right Trigger Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-40 bg-[#C28E64] hover:bg-[#A8754F] text-white p-4 rounded-full shadow-2xl transition flex items-center space-x-2 border-2 border-white group"
        >
          <div className="relative">
            <Bot className="w-6 h-6" />
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-400 border-2 border-white rounded-full"></span>
          </div>
          <span className="font-bold text-sm hidden md:inline">AI HR Assistant</span>
        </button>
      )}

      {/* Floating Drawer Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-96 max-w-[calc(100vw-3rem)] h-[520px] bg-white rounded-2xl shadow-2xl border border-stone-200 flex flex-col overflow-hidden animate-slide-up">
          {/* Drawer Header */}
          <div className="bg-[#1E1E1E] text-white p-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-[#C28E64] p-2 rounded-xl text-white">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm">Buildora HR Assistant</h4>
                <div className="flex items-center space-x-1 text-[10px] text-emerald-400">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Security Policy Guardrails Active</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 rounded-lg hover:bg-stone-800 text-stone-400 hover:text-white transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages Body */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-stone-50">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex space-x-2 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'bot' && (
                  <div className="bg-[#C28E64] p-1.5 rounded-lg text-white h-7 w-7 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div
                  className={`p-3 rounded-2xl text-xs max-w-[80%] leading-relaxed ${
                    m.sender === 'user'
                      ? 'bg-[#C28E64] text-white rounded-tr-none'
                      : 'bg-white text-stone-800 border border-stone-200 shadow-sm rounded-tl-none'
                  }`}
                >
                  <p>{m.text}</p>
                  {m.autoApproved && (
                    <div className="mt-2 pt-2 border-t border-emerald-100 flex items-center space-x-1.5 text-emerald-700 font-bold text-[11px]">
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Leave Auto-Approved (&lt;3 days)</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center space-x-2 text-stone-400 text-xs italic">
                <Sparkles className="w-4 h-4 animate-spin text-[#C28E64]" />
                <span>Consulting HR policy database...</span>
              </div>
            )}
          </div>

          {/* Input Form */}
          <form onSubmit={handleSend} className="p-3 bg-white border-t border-stone-200 flex space-x-2">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ask about policies or leave (e.g. 2 days leave)..."
              className="flex-1 px-3 py-2 border border-stone-300 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#C28E64]"
            />
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="bg-[#C28E64] hover:bg-[#A8754F] text-white p-2 rounded-xl transition shadow disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
};
