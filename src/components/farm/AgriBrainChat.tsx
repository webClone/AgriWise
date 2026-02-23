"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';
import { ToolResultRenderer } from '../chat/widgets/ToolResultRenderer';

interface Message {
  role: 'user' | 'model';
  content: string;
  toolCalls?: { name: string; args: any; result?: any }[];
  metadata?: { intent?: string; evidence?: string[] };
}

interface AgriBrainChatProps {
  context?: any;
}

export default function AgriBrainChat({ context }: AgriBrainChatProps) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    { role: 'model', content: "Hello! I am AgriBrain. I can analyze your fields using Earth Observation data and ML models. Ask me about yield, weather, or crop health." }
  ]);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // DEBUG: Log context to console so user can see it
  useEffect(() => {
      console.log("------------------------------------------");
      console.log("🐛 [AgriBrain] OUTGOING CONTEXT TO API:");
      console.log(context);
      console.log("------------------------------------------");
  }, [context]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // Build conversation history for API (excluding the greeting)
      const historyForApi = [...messages, userMsg].slice(1).map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content
      }));

      const res = await fetch('/api/agribrain/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg.content, history: historyForApi, context })
      });
      
      const data = await res.json();
      
      if (data.error) {
        throw new Error(data.details || data.error);
      }

      const modelMsg: Message = {
        role: 'model',
        content: data.text || "I processed that.",
        toolCalls: data.toolCalls,
        metadata: data.metadata
      };
      
      setMessages(prev => [...prev, modelMsg]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'model', content: `⚠️ System Error: ${e instanceof Error ? e.message : String(e)}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card fade-in flex flex-col h-full overflow-hidden border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center gap-2">
        <span className="text-xl">🧠</span>
        <div>
          <h3 className="m-0 text-base font-semibold text-slate-800 dark:text-slate-200">AgriBrain Assistant</h3>
          <div className="text-xs text-slate-500 dark:text-slate-400">Orchestrator Mode • Plane F</div>
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'}`}>
            
            {/* Tool Indicators */}
            {msg.toolCalls && msg.toolCalls.map((tool, idx) => (
              <div key={idx} className="mb-2 w-full max-w-[90%] fade-in">
                 <div className="px-2 py-1 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-t-lg text-xs text-green-700 dark:text-green-400 font-mono inline-block -mb-px relative z-10">
                   🛠️ Function: <b>{tool.name}</b>
                 </div>
                 
                 {tool.result ? (
                     <div className="bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700 rounded-b-lg rounded-tr-lg p-1 shadow-sm overflow-hidden">
                        <ToolResultRenderer toolName={tool.name} result={tool.result} />
                     </div>
                 ) : (
                     <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-b p-2 text-xs text-slate-500 italic">
                        Executing analysis...
                     </div>
                 )}
              </div>
            ))}
            
            {/* Cognitive Evidence (New) */}
            {msg.metadata && msg.metadata.evidence && msg.metadata.evidence.length > 0 && (
                <div className="mb-1 flex flex-wrap gap-1">
                    {msg.metadata.evidence.map((ev, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded text-[10px] bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 border border-indigo-100 dark:border-indigo-800">
                           🔍 {ev}
                        </span>
                    ))}
                </div>
            )} 

            {/* Bubble */}
            <div 
              dir="ltr"
              className={`
              px-4 py-3 rounded-xl shadow-sm text-sm text-left
              ${msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-br-sm' 
                : 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-bl-sm'}
            `}>
              <ReactMarkdown 
                components={{
                  p: ({node, ...props}) => <p className="m-0 leading-relaxed" {...props} />,
                  ul: ({node, ...props}) => <ul className="my-2 pl-4 list-disc" {...props} />,
                  li: ({node, ...props}) => <li className="mb-1" {...props} />
                }}
              >
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        ))}
        
        {loading && (
          <div className="self-start text-slate-400 text-sm italic animate-pulse">
            AgriBrain is thinking...
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex gap-2">
        <input 
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Ask about yield, weather, or crop status..."
          className="flex-1 p-3 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        />
        <button 
          onClick={handleSend}
          disabled={loading}
          className={`
            px-6 rounded-lg font-semibold text-white transition-all
            ${loading ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 active:scale-95'}
          `}
        >
          Send
        </button>
      </div>
    </div>
  );
}
