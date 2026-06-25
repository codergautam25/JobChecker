"use client";

import { useStore } from '@/store';
import { useState, useEffect } from 'react';
import { Bot, X, Send } from 'lucide-react';
import { cn } from '@/lib/utils';

import axios from 'axios';

export function Chatbot() {
  const [mounted, setMounted] = useState(false);
  const { isChatOpen, setChatOpen, chatHistory, addChatMessage, activeReviewId, setActiveReviewId } = useStore();
  const [input, setInput] = useState('');

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input;
    addChatMessage({ role: 'user', content: userMessage });
    setInput('');

    try {
      const res = await axios.post('http://localhost:8000/api/chat', {
        message: userMessage,
        approval_id: activeReviewId
      });
      addChatMessage({ role: 'assistant', content: res.data.reply });
      if (res.data.clearReviewId) {
        setActiveReviewId(null);
      }
    } catch (err) {
      console.error(err);
      addChatMessage({ role: 'assistant', content: "*(Backend error occurred while processing your request.)*" });
    }
  };

  if (!mounted) return null;

  return (
    <>
      <div 
        className={cn(
          "fixed top-24 right-8 w-[400px] h-[600px] max-h-[80vh] bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl flex flex-col overflow-hidden z-[50000] transition-all duration-300 ease-out",
          isChatOpen ? "translate-y-0 opacity-100 pointer-events-auto" : "-translate-y-4 opacity-0 pointer-events-none"
        )}
      >
        <div className="px-6 py-4 border-b border-slate-700/50 bg-slate-800/50 flex justify-between items-center">
          <h3 className="font-semibold flex items-center gap-2 text-slate-100">
            <Bot size={20} className="text-sky-400" /> 
            AI Assistant
          </h3>
          <button 
            onClick={() => setChatOpen(false)}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4 scrollbar-none">
          {chatHistory.map((msg, i) => (
            <div 
              key={i} 
              className={cn(
                "max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed",
                msg.role === 'user' 
                  ? "self-end bg-sky-500 text-slate-950 rounded-br-sm font-medium" 
                  : "self-start bg-slate-800 text-slate-200 rounded-bl-sm border border-slate-700/50"
              )}
            >
              {msg.role === 'assistant' && msg.content.includes('```') ? (
                <div className="whitespace-pre-wrap">
                  {msg.content.split('```').map((part, j) => {
                    if (j % 2 === 1) {
                      return (
                        <pre key={j} className="bg-black/60 p-3 rounded-lg overflow-x-auto mt-2 mb-2 font-mono text-[11px] border border-slate-700/50 text-emerald-400 whitespace-pre">
                          {part.replace(/^bash\n|^text\n/, '')}
                        </pre>
                      );
                    }
                    return <span key={j}>{part}</span>;
                  })}
                </div>
              ) : (
                <span className="whitespace-pre-wrap">{msg.content}</span>
              )}
            </div>
          ))}
        </div>

        <div className="p-4 bg-slate-800/30 border-t border-slate-700/50">
          <form onSubmit={handleSubmit} className="flex gap-2 relative">
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything or type 'yes' to approve..."
              className="flex-1 bg-slate-950/50 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50 focus:ring-1 focus:ring-sky-500/50 transition-all pr-12"
            />
            <button 
              type="submit" 
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-lg transition-colors"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>

      <button 
        onClick={() => setChatOpen(!isChatOpen)}
        className="fixed top-[-10px] right-8 w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 rounded-full flex items-center justify-center text-white shadow-xl shadow-indigo-500/20 z-[49999] transition-transform hover:scale-110 active:scale-95 mt-[15px]"
      >
        <Bot size={24} />
      </button>
    </>
  );
}
