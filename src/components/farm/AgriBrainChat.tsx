"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, SendHorizontal, BrainCircuit, X } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import { ToolResultRenderer } from '../chat/widgets/ToolResultRenderer';
import ARFWidget from '../chat/widgets/ARFWidget';
import { usePlotIntelligence as usePlotIntelHook } from "@/hooks/usePlotIntelligence";

interface Message {
  role: 'user' | 'model';
  content: string;
  toolCalls?: { name: string; args: any; result?: any }[];
  metadata?: { intent?: string; evidence?: string[] };
  arf?: any;
  thinkingTrace?: string;
}

function ThinkingTraceRenderer({ trace }: { trace: string }) {
  const renderLine = (line: string, i: number) => {
    let el = <span dangerouslySetInnerHTML={{
        __html: line
            .replace(/\[LOW CONFIDENCE[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/30 text-amber-700 dark:text-amber-500 text-[10px] font-bold tracking-wide uppercase mx-1">⚠️ Low Conf</span>')
            .replace(/\[MISSING DRIVER[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-red-500/20 border border-red-500/30 text-red-700 dark:text-red-500 text-[10px] font-bold tracking-wide uppercase mx-1">❌ Missing</span>')
            .replace(/\[HIGH CONFIDENCE[^\]]*\]/gi, '<span class="px-1.5 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/30 text-emerald-700 dark:text-emerald-500 text-[10px] font-bold tracking-wide uppercase mx-1">✅ High Conf</span>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
    }} />
    return <div key={i} className="mb-1 leading-relaxed">{el}</div>;
  };

  return (
    <div className="flex flex-col">
      {trace.split('\n').filter(l => l.trim() !== "").map((line, i) => renderLine(line, i))}
    </div>
  );
}

const MetricHighlighter = ({ children }: { children: React.ReactNode }) => {
  const processNode = (node: React.ReactNode): React.ReactNode => {
    if (typeof node === 'string') {
      const regex = /(\b\d+(?:\.\d+)?\s*(?:mm|cm|m|km|kg|g|ha|%|NDVI|°C|°F|C|F|days|weeks|months|hours|mm\/h|obs)?\b)/gi;
      const parts = node.split(regex);
      if (parts.length === 1) return node;
      
      return parts.map((part, i) => {
        if (part.match(regex)) {
          // Exclude single digit numbers that aren't decimals or have units, to avoid over-highlighting basic text like "step 1"
          if (/^\d$/.test(part.trim())) return part;
          
          return (
            <span key={i} className="inline-flex items-center gap-0.5 px-1.5 py-px mx-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-700 dark:text-indigo-400 font-mono font-bold whitespace-nowrap shadow-sm align-baseline transition-colors hover:bg-indigo-500/20 cursor-default">
              <BrainCircuit className="w-3 h-3 opacity-70 shrink-0 relative -top-[0.5px]" />
              {part}
            </span>
          );
        }
        return part;
      });
    }
    if (React.isValidElement(node)) {
      return React.cloneElement(node, { ...node.props, children: React.Children.map(node.props.children, processNode) });
    }
    return node;
  };

  return <>{React.Children.map(children, processNode)}</>;
};

interface AgriBrainChatProps {
  context?: any;
  onZoneUpdate?: (zones: any, zoneSuitability: any) => void;
  suggestedQuery?: { label: string; query: string } | null;
  initialQuery?: string | null;
}

export default function AgriBrainChat({ context, onZoneUpdate, suggestedQuery, initialQuery }: AgriBrainChatProps) {
  const [input, setInput] = useState(initialQuery || "");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Executing analysis...");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { detailMode } = usePlotIntelHook();

  const STORAGE_KEY = `agribrain_chat_${context?.plot_id || 'default'}`;

  // Load from local storage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setMessages(JSON.parse(stored));
      }
    } catch (e) {
      console.error("Failed to load chat history", e);
    }
  }, [STORAGE_KEY]);

  useEffect(() => {
    try {
      if (messages.length > 0) {
        // Filter out system errors so they don't persist
        const cleanMessages = messages.filter(m => !(m.role === 'model' && m.content.includes('⚠️ System Error')));
        if (cleanMessages.length > 0) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(cleanMessages));
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (e) {
      console.error("Failed to save chat history", e);
    }
  }, [messages, STORAGE_KEY]);

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

  const handleSend = async (overrideInput?: string) => {
    const textToSend = overrideInput || input;
    if (!textToSend.trim() || loading) return;

    const userMsg: Message = { role: 'user', content: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setLoading(true);
    setLoadingText("Routing query...");

    try {
      const historyForApi = [...messages, userMsg].slice(1).map(m => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.content
      }));

      // 1. Fast Intent Pass
      try {
        const intentRes = await fetch('/api/agribrain/intent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: userMsg.content,
            history: historyForApi
          })
        });
        const intentData = await intentRes.json();
        if (intentData.success && intentData.data) {
          const engines = intentData.data.engines || [];
          if (engines.length > 0) {
            setLoadingText(`Thinking: Routing to ${engines.join(", ")}...`);
          } else {
            setLoadingText("Thinking: Analyzing field context...");
          }
        }
      } catch (e) {
        console.warn("Intent fetch failed, proceeding anyway", e);
        setLoadingText("Executing analysis...");
      }

      // 2. Main LLM Pass
      const res = await fetch('/api/agribrain/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plotId: context?.plotId || context?.plot?.id,
          mode: 'chat',
          query: userMsg.content,
          history: historyForApi,
          experienceLevel: 'INTERMEDIATE',
          userMode: detailMode,
        })
      });
      
      const data = await res.json();
      
      if (data.error || data.success === false) {
        throw new Error(data.error || 'AgriBrain run failed');
      }

      // Extract chat-relevant fields from AgriBrainRun or ChatPayload
      const arf = data.arf || data.explanations?.arf;
      const modes = data.global_quality?.degradation_modes || [];
      const relScore = data.global_quality?.reliability || 0;

      // Build display text
      let md = "";
      let thinkingTrace = "";
      if (arf && arf.conversational_response) {
        let raw = arf.conversational_response;

        // DeepSeek R1: extract <think>...</think> block
        const dsMatch = raw.match(/<think>([\s\S]*?)<\/think>/i);
        if (dsMatch) {
          thinkingTrace = dsMatch[1].trim().replace(/^-\s*/gm, "• ");
          raw = raw.replace(dsMatch[0], "").trim();
        }

        // Nemotron fallback: > *Thinking:* block
        if (!thinkingTrace) {
          const match = raw.match(/(>\s*\*Thinking:\*[\s\S]*?)(?=\n\n|\n[A-Z]|\n<|$)/i);
          if (match) {
            thinkingTrace = match[0].replace(/>\s*\*Thinking:\*\s*/i, "").trim();
            thinkingTrace = thinkingTrace.replace(/^>\s*/gm, "").replace(/^-\s*/gm, "• ");
            raw = raw.replace(match[0], "").trim();
          }
        }

        md = raw;
      } else if (arf && !arf.error && (arf.headline || arf.direct_answer)) {
        md = `Here is the diagnostic analysis based on your request:`;
      } else {
        const headline = data.summary?.headline || data.explanations?.summary?.headline || "Analysis Complete";
        const body = arf?.error ? `**Error:** ${arf.error}` : (data.summary?.explanation || "");
        md = `### ${headline}\n\n${body}\n\n`;
      }

      if (modes.length > 0 && !(arf && arf.conversational_response)) {
        md += `\n> ⚠️ **Data Gaps:** ${modes.join(", ")} (Reliability: ${relScore.toFixed(2)})`;
      }

      const modelMsg: Message = {
        role: 'model',
        content: md || (arf ? "" : "I processed that."),
        toolCalls: data.toolCalls,
        metadata: { intent: data.assistant_mode || data.intent, evidence: modes },
        arf: (arf && arf.conversational_response) ? undefined : arf,
        thinkingTrace: thinkingTrace || undefined
      };
      
      // Forward zone data to map via parent callback
      const zones = data.zones || data.summary?.management_zones;
      const zoneSuitability = data.zoneSuitability || data.summary?.zone_suitability;
      if (onZoneUpdate && (zones || zoneSuitability)) {
        onZoneUpdate(zones, zoneSuitability);
      }
      
      setMessages(prev => [...prev, modelMsg]);
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'model', content: `⚠️ System Error: ${e instanceof Error ? e.message : String(e)}` }]);
    } finally {
      setLoading(false);
    }
  };

  const adjustTextareaHeight = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
    }
  };

  return (
    <div className="card fade-in flex flex-col h-full overflow-hidden border border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur-3xl shadow-xl">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/50 backdrop-blur-xl flex items-center gap-3 z-10 sticky top-0 shadow-sm">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-500 shadow-inner">
          <BrainCircuit className="w-5 h-5" />
        </div>
        <div>
          <h3 className="m-0 text-base font-semibold text-slate-800 dark:text-slate-200 tracking-tight">AgriBrain Assistant</h3>
          <div className="text-xs font-medium text-slate-500 dark:text-slate-400 flex items-center gap-1.5 mt-0.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Orchestrator Mode
          </div>
        </div>
        <div className="flex-1" />
        <button
          onClick={() => setMessages([])}
          className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 rounded-lg transition-colors group"
          title="Clear chat history"
        >
          <X className="w-4 h-4 transition-transform group-hover:rotate-90" />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-6 scroll-smooth scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700">
        <AnimatePresence initial={false}>
        {messages.map((msg, i) => (
          <motion.div 
            key={i} 
            layout
            initial={{ opacity: 0, y: 15, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
            className={`flex flex-col w-full max-w-[90%] ${msg.role === 'user' ? 'self-end items-end' : 'self-start items-start'}`}
          >
            
            {/* Tool Indicators */}
            {msg.toolCalls && msg.toolCalls.map((tool, idx) => (
              <div key={`tool-${idx}`} className="mb-2 w-full max-w-[90%] fade-in">
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
            
            {/* Thinking Trace */}
            {msg.thinkingTrace && (
               <details className="mb-3 w-full max-w-[90%] group">
                  <summary className="px-3 py-1.5 bg-slate-100/50 hover:bg-slate-100 dark:bg-slate-800/50 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-[11px] text-slate-600 dark:text-slate-400 font-mono inline-flex items-center gap-2 cursor-pointer transition-colors shadow-sm select-none list-none">
                    <ChevronRight className="w-3 h-3 transition-transform group-open:rotate-90" />
                    <span>Expert Architect Trace</span>
                  </summary>
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }} 
                    animate={{ height: "auto", opacity: 1 }} 
                    className="mt-2 bg-white/95 dark:bg-slate-900/95 border border-slate-200 dark:border-slate-700 rounded-xl p-4 shadow-sm text-[13px] text-slate-700 dark:text-slate-300 font-mono overflow-x-auto"
                  >
                    <ThinkingTraceRenderer trace={msg.thinkingTrace} />
                  </motion.div>
               </details>
            )}
            

            {/* Bubble */}
            <div 
              dir="ltr"
              className={`
              px-5 py-3.5 rounded-2xl shadow-sm text-sm text-left
              ${msg.role === 'user' 
                ? 'bg-gradient-to-br from-indigo-500 to-blue-600 text-white rounded-br-sm shadow-indigo-500/20' 
                : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-bl-sm'}
            `}>
              {msg.arf ? (
                  <div className="flex flex-col gap-3">
                     {msg.content && <div className="mb-1 text-[15px]"><ReactMarkdown>{msg.content}</ReactMarkdown></div>}
                     <ARFWidget arf={msg.arf} />
                  </div>
              ) : (
                  <ReactMarkdown 
                    components={{
                      p: ({children, ...props}) => <p className="m-0 leading-relaxed text-[15px]" {...props}><MetricHighlighter>{children}</MetricHighlighter></p>,
                      ul: ({children, ...props}) => <ul className="my-2 pl-4 list-disc marker:text-indigo-500/50" {...props}>{children}</ul>,
                      li: ({children, ...props}) => <li className="mb-1" {...props}><MetricHighlighter>{children}</MetricHighlighter></li>
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
              )}
            </div>
          </motion.div>
        ))}
        </AnimatePresence>
        
        {loading && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="bg-white dark:bg-slate-800/80 rounded-2xl p-4 max-w-[85%] border border-slate-200 dark:border-slate-700 shadow-sm flex flex-col gap-3 rounded-bl-sm">
              <div className="flex items-center gap-1.5">
                <motion.div className="w-1.5 h-1.5 bg-indigo-500 rounded-full" animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1, delay: 0 }} />
                <motion.div className="w-1.5 h-1.5 bg-indigo-500 rounded-full" animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1, delay: 0.2 }} />
                <motion.div className="w-1.5 h-1.5 bg-indigo-500 rounded-full" animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }} transition={{ repeat: Infinity, duration: 1, delay: 0.4 }} />
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                {loadingText}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/50 backdrop-blur-xl flex flex-col p-4 relative z-10">
        {suggestedQuery && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="absolute -top-10 left-4 right-4 flex justify-start">
            <button 
              onClick={() => handleSend(suggestedQuery.query)}
              className="text-xs font-semibold bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 border border-indigo-200 dark:border-indigo-500/30 shadow-sm px-4 py-2 rounded-full hover:bg-indigo-50 dark:hover:bg-indigo-900/30 flex items-center gap-2 transition-all hover:scale-105 active:scale-95"
            >
              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
              {suggestedQuery.label}
            </button>
          </motion.div>
        )}
        <div className="flex gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-sm rounded-2xl p-1 focus-within:ring-2 focus-within:ring-indigo-500/50 focus-within:border-indigo-500/50 transition-all">
          <textarea 
            ref={textareaRef}
            value={input}
            onChange={adjustTextareaHeight}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask about yield, weather, or crop status..."
            className="flex-1 max-h-[120px] min-h-[44px] py-3 px-4 bg-transparent text-sm text-slate-800 dark:text-slate-200 focus:outline-none resize-none leading-relaxed"
            rows={1}
          />
          <div className="flex items-end p-1">
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => handleSend()}
              disabled={loading || !input.trim()}
              className={`
                w-10 h-10 flex items-center justify-center rounded-xl transition-all
                ${loading || !input.trim() ? 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed' : 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'}
              `}
            >
              <SendHorizontal className="w-5 h-5" />
            </motion.button>
          </div>
        </div>
        <div className="text-center mt-2">
          <span className="text-[10px] text-slate-400 dark:text-slate-500">AgriBrain can make mistakes. Check critical farm decisions.</span>
        </div>
      </div>
    </div>
  );
}
