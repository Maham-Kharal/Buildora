'use client';

import React, { useState, useEffect } from 'react';
import { Bot, X, Send, ShieldCheck, Sparkles, CheckCircle, ExternalLink } from 'lucide-react';
import { userService } from '../services/userService';
import { adminService } from '../../admin/services/adminService';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  sender: 'bot' | 'user';
  text: string;
  autoApproved?: boolean;
}

export const AiAssistantDrawer: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [userRole, setUserRole] = useState<string>('WORKER');
  const [sessionId, setSessionId] = useState<string>('');

  const [messages, setMessages] = useState<Message[]>([
    {
      sender: 'bot',
      text: 'Hello! I am your Buildora Enterprise AI Assistant.\n\nI can help you with:\n1. 📝 **Leave Requests & Auto-Clearance** (Requests < 3 days auto-approved)\n2. 📜 **Company Policy KB** (Safety protocols, site rules)\n3. 🏗️ **Steel Takeoff Estimation** (Admin Operations)\n4. 📁 **Past Project History** (SQL Database filter)',
    },
  ]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Create or retrieve session ID for stateful conversational slot filling
      let sId = sessionStorage.getItem('buildora_ai_session_id');
      if (!sId) {
        sId = `sess_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
        sessionStorage.setItem('buildora_ai_session_id', sId);
      }
      setSessionId(sId);

      const userStr = localStorage.getItem('buildora_user');
      if (userStr) {
        try {
          const u = JSON.parse(userStr);
          if (u.role) {
            const role = u.role.toUpperCase();
            setUserRole(role);
            if (role === 'ADMIN') {
              setMessages([
                {
                  sender: 'bot',
                  text: 'Hello! I am your Buildora Enterprise Admin AI Assistant.\n\nI can help you with:\n1. 📁 **Past Project History** — Search historical construction projects by area, steel quantity, location, and project characteristics\n2. 📊 **Financial Expense Reports** (Daily, Weekly, Monthly, and custom date range breakdowns)\n3. 🏗️ **Steel Takeoff Estimation** — Interactive estimation using project details and historical data',
                },
              ]);
            } else {
              setMessages([
                {
                  sender: 'bot',
                  text: 'Hello! I am your Buildora Field AI Assistant.\n\nI can help you with:\n1. 📝 **Leave Requests & Clearance** (Requests up to 3 days auto-approved)\n2. 📊 **Check Leave Balance** (Verify remaining paid annual leave days)\n3. 📜 **Company Policy KB** (Safety protocols & site guidelines)',
                },
              ]);
            }
          }
        } catch (e) {}
      }
    }
  }, []);

  const handleSend = async (e: React.FormEvent | null, customText?: string) => {
    if (e) e.preventDefault();
    const userText = customText || prompt.trim();
    if (!userText) return;

    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    if (!customText) setPrompt('');
    setLoading(true);

    try {
      let res: { answer?: string; message?: string; session_id?: string; auto_approved_leave?: boolean };
      if (userRole === 'ADMIN') {
        res = await adminService.askAdminAIChat(userText, sessionId);
      } else {
        res = await userService.askHRAssistant(userText, sessionId, userRole);
      }

      const rawText = res.message || res.answer || (res as any).response || '';
      const botText = (typeof rawText === 'string' && rawText.trim()) ? rawText : 'Unable to display the assistant response.';

      if (res.session_id) {
        setSessionId(res.session_id);
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('buildora_ai_session_id', res.session_id);
        }
      }

      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: botText,
          autoApproved: res.auto_approved_leave || false,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'bot',
          text: 'Sorry, I encountered an issue consulting the database. Please try again.',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickAction = (text: string) => {
    handleSend(null, text);
  };

  const MarkdownMessage = ({ text }: { text: string }) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Headings
        h1: ({ children }) => <h1 className="text-sm font-bold mt-2 mb-1 text-stone-900">{children}</h1>,
        h2: ({ children }) => <h2 className="text-xs font-bold mt-2 mb-1 text-stone-900">{children}</h2>,
        h3: ({ children }) => <h3 className="text-xs font-semibold mt-1.5 mb-0.5 text-stone-800">{children}</h3>,
        // Paragraphs
        p: ({ children }) => <p className="mb-1.5 leading-relaxed last:mb-0">{children}</p>,
        // Bold
        strong: ({ children }) => <strong className="font-bold text-stone-900">{children}</strong>,
        // Italic
        em: ({ children }) => <em className="italic text-stone-700">{children}</em>,
        // Unordered list
        ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 my-1 pl-1">{children}</ul>,
        // Ordered list
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 my-1 pl-1">{children}</ol>,
        // List item
        li: ({ children }) => <li className="text-xs leading-relaxed">{children}</li>,
        // Inline code
        code: ({ children }) => (
          <code className="bg-stone-100 text-stone-700 text-[10px] px-1.5 py-0.5 rounded font-mono border border-stone-200">
            {children}
          </code>
        ),
        // Code block
        pre: ({ children }) => (
          <pre className="bg-stone-100 text-stone-700 text-[10px] p-2 rounded-lg font-mono overflow-x-auto my-1.5 border border-stone-200">
            {children}
          </pre>
        ),
        // Horizontal rule
        hr: () => <hr className="border-stone-200 my-2" />,
        // Links — open in new tab
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 text-blue-600 underline font-semibold hover:text-blue-800 transition"
          >
            {children}
            <ExternalLink className="w-2.5 h-2.5 inline-block" />
          </a>
        ),
        // Blockquote
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-[#C28E64] pl-2 text-stone-600 italic my-1.5">
            {children}
          </blockquote>
        ),
      }}
    >
      {text}
    </ReactMarkdown>
  );

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
          <span className="font-bold text-sm hidden md:inline">Buildora AI Assistant</span>
        </button>
      )}

      {/* Floating Drawer Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-[450px] max-w-[calc(100vw-2rem)] h-[600px] bg-white rounded-2xl shadow-2xl border border-stone-200 flex flex-col overflow-hidden animate-slide-up">
          {/* Drawer Header */}
          <div className="bg-[#1E1E1E] text-white p-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-[#C28E64] p-2 rounded-xl text-white">
                <Bot className="w-5 h-5" />
              </div>
              <div>
                <h4 className="font-bold text-sm">Buildora Enterprise AI Assistant</h4>
                <div className="flex items-center space-x-1 text-[10px] text-emerald-400 font-semibold">
                  <ShieldCheck className="w-3 h-3" />
                  <span>Stateful Gemini 1.5 AI Agent</span>
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

          {/* Quick Filter Action Pills */}
          <div className="bg-stone-100 px-3 py-2 border-b border-stone-200 flex items-center space-x-1.5 overflow-x-auto text-xs scrollbar-none">
            <span className="text-[10px] font-bold text-stone-500 uppercase tracking-wider shrink-0">Quick Actions:</span>
            {userRole === 'WORKER' ? (
              <>
                <button
                  onClick={() => handleQuickAction('I want to request 2 days leave')}
                  className="bg-white border border-emerald-300 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-emerald-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  📝 Request Leave (&lt;3 Days)
                </button>
                <button
                  onClick={() => handleQuickAction('How many leave days do I have left?')}
                  className="bg-white border border-indigo-300 text-indigo-800 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-indigo-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  📊 Check Leave Balance
                </button>
                <button
                  onClick={() => handleQuickAction('What are the company policies for safety and expenses?')}
                  className="bg-white border border-blue-300 text-blue-800 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-blue-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  📜 Company Policies
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={() => handleQuickAction('Show me past project history from the database')}
                  className="bg-white border border-purple-300 text-purple-800 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-purple-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  📁 Past Project History
                </button>
                <button
                  onClick={() => handleQuickAction('Show me expense report with project breakdown')}
                  className="bg-white border border-emerald-300 text-emerald-800 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-emerald-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  📊 Expense Reports
                </button>
                <button
                  onClick={() => handleQuickAction('I want to estimate the cost of steel')}
                  className="bg-white border border-amber-300 text-amber-900 font-bold px-2.5 py-1 rounded-full text-[11px] hover:bg-amber-600 hover:text-white transition shrink-0 shadow-sm"
                >
                  🏗️ Steel Estimation
                </button>
              </>
            )}
          </div>

          {/* Messages Body */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3 bg-stone-50 text-xs">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex space-x-2 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'bot' && (
                  <div className="bg-[#C28E64] p-1.5 rounded-lg text-white h-7 w-7 flex items-center justify-center shrink-0 mt-1 shadow-sm">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div
                  className={`p-3.5 rounded-2xl text-xs max-w-[85%] leading-relaxed ${
                    m.sender === 'user'
                      ? 'bg-[#C28E64] text-white rounded-tr-none font-semibold shadow-sm whitespace-pre-line'
                      : 'bg-white text-stone-800 border border-stone-200 shadow-sm rounded-tl-none'
                  }`}
                >
                  {m.sender === 'bot' ? (
                    <MarkdownMessage text={m.text} />
                  ) : (
                    <span>{m.text}</span>
                  )}
                  {m.autoApproved && (
                    <div className="mt-2 pt-2 border-t border-emerald-100 flex items-center space-x-1.5 text-emerald-700 font-bold text-[11px]">
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Leave Auto-Approved (&lt;3 days threshold)</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex items-center space-x-2 text-stone-400 text-xs italic">
                <Sparkles className="w-4 h-4 animate-spin text-[#C28E64]" />
                <span>Consulting Gemini AI & project database...</span>
              </div>
            )}
          </div>

          {/* Input Form */}
          <form onSubmit={(e) => handleSend(e)} className="p-3 bg-white border-t border-stone-200 flex space-x-2">
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={userRole === 'WORKER' ? "Ask about leave balance or company safety policy..." : "Ask about expense reports, past projects, or steel estimation..."}
              className="flex-1 px-3.5 py-2 border border-stone-300 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-[#C28E64]"
            />
            <button
              type="submit"
              disabled={loading || !prompt.trim()}
              className="bg-[#C28E64] hover:bg-[#A8754F] text-white px-4 py-2 rounded-xl font-bold text-xs transition shadow disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
};
