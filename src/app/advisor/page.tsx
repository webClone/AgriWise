"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";

// Icons
const HomeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25" />
  </svg>
);

const FarmIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
  </svg>
);

const CalendarIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
  </svg>
);

const WeatherIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z" />
  </svg>
);

const UserIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
  </svg>
);

interface Message {
  role: "user" | "model";
  content: string;
  timestamp: Date;
}

export default function AIAdvisorPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiAvailable, setAiAvailable] = useState<boolean | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check AI availability on mount
  useEffect(() => {
    checkAIAvailability();
    // Add welcome message
    setMessages([{
      role: "model",
      content: "مرحباً! أنا مستشارك الزراعي الخبير. 🌱\n\nيمكنني مساعدتك في:\n• إدارة المحاصيل والتربة\n• أنظمة الري والتسميد\n• مكافحة الآفات والأمراض\n• الزراعة الذكية والمستدامة\n• تحسين الإنتاجية والجودة\n\nاسألني أي سؤال!",
      timestamp: new Date(),
    }]);
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const checkAIAvailability = async () => {
    try {
      const response = await fetch("/api/ai/chat");
      const data = await response.json();
      setAiAvailable(data.available);
    } catch {
      setAiAvailable(false);
    }
  };

  const sendMessage = async (messageText?: string) => {
    const text = messageText || input.trim();
    if (!text || loading) return;

    // Add user message
    const userMessage: Message = {
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          chatHistory: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
        }),
      });

      const data = await response.json();
      
      const aiMessage: Message = {
        role: "model",
        content: data.success ? data.response : (data.error || "عذراً، حدث خطأ. حاول مرة أخرى."),
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch {
      setMessages(prev => [...prev, {
        role: "model",
        content: "عذراً، لم أتمكن من الاتصال. تحقق من اتصالك بالإنترنت.",
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([{
      role: "model",
      content: "تم مسح المحادثة. كيف يمكنني مساعدتك؟",
      timestamp: new Date(),
    }]);
  };

  return (
    <main className="page" style={{ display: "flex", flexDirection: "column", height: "100vh", paddingBottom: "140px" }}>
      {/* Header */}
      <header className="page-header" style={{ flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <h1 className="page-title">🧑‍🌾 المستشار الزراعي</h1>
            <p className="page-subtitle">خبير زراعي بالذكاء الاصطناعي</p>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            {aiAvailable === false && (
              <span style={{ 
                padding: "0.25rem 0.5rem", 
                background: "rgba(239, 68, 68, 0.1)", 
                color: "var(--color-error-500)",
                borderRadius: "var(--radius-full)",
                fontSize: "0.75rem",
              }}>
                API مطلوب
              </span>
            )}
            <button
              onClick={clearChat}
              style={{
                padding: "0.4rem 0.6rem",
                background: "var(--background-secondary)",
                border: "1px solid var(--background-tertiary)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                fontSize: "0.8rem",
              }}
            >
              🗑️ مسح
            </button>
          </div>
        </div>
      </header>

      {/* Chat Messages */}
      <div style={{ flex: 1, overflowY: "auto", marginBottom: "1rem" }}>
        {messages.map((message, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: message.role === "user" ? "flex-end" : "flex-start",
              marginBottom: "0.75rem",
            }}
          >
            <div
              style={{
                maxWidth: "85%",
                padding: "0.75rem 1rem",
                borderRadius: message.role === "user" ? "var(--radius-lg) var(--radius-lg) 0 var(--radius-lg)" : "var(--radius-lg) var(--radius-lg) var(--radius-lg) 0",
                background: message.role === "user" ? "var(--color-primary-500)" : "var(--background-secondary)",
                color: message.role === "user" ? "white" : "inherit",
              }}
            >
              {message.role === "model" && (
                <div style={{ fontSize: "0.75rem", marginBottom: "0.25rem", opacity: 0.7 }}>🧑‍🌾 الخبير</div>
              )}
              <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>{message.content}</div>
            </div>
          </div>
        ))}
        
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "0.75rem" }}>
            <div style={{ padding: "0.75rem 1rem", background: "var(--background-secondary)", borderRadius: "var(--radius-lg)" }}>
              <div className="spinner" style={{ width: "20px", height: "20px" }} />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div style={{ 
        flexShrink: 0, 
        position: "fixed", 
        bottom: "70px", 
        left: 0, 
        right: 0, 
        padding: "1rem", 
        background: "var(--background-primary)",
        borderTop: "1px solid var(--background-tertiary)",
      }}>
        <div style={{ display: "flex", gap: "0.5rem", maxWidth: "600px", margin: "0 auto" }}>
          <input
            type="text"
            className="input"
            placeholder="اسأل عن أي موضوع زراعي..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            disabled={loading}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn-primary"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            style={{ padding: "0.5rem 1rem" }}
          >
            إرسال
          </button>
        </div>
      </div>

      {/* Bottom Navigation */}
      <nav className="nav-bottom">
        <Link href="/" className="nav-item"><HomeIcon /><span>الرئيسية</span></Link>
        <Link href="/farm" className="nav-item"><FarmIcon /><span>المزارع</span></Link>
        <Link href="/calendar" className="nav-item"><CalendarIcon /><span>التقويم</span></Link>
        <Link href="/weather" className="nav-item"><WeatherIcon /><span>الطقس</span></Link>
        <Link href="/profile" className="nav-item"><UserIcon /><span>حسابي</span></Link>
      </nav>
    </main>
  );
}
