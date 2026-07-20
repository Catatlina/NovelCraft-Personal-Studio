import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";
import { EmptyState } from "./ui";

interface Message { role: "user" | "assistant"; content: string }

export function AIChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const userMsg: Message = { role: "user", content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput(""); setStreaming(true);

    const assistantMsg: Message = { role: "assistant", content: "" };
    setMessages(prev => [...prev, assistantMsg]);

    try {
      const token = localStorage.getItem("nc_token") || "";
      const resp = await fetch("/api/v1/engine/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` },
        body: JSON.stringify({ messages: [...messages, userMsg], model: "deepseek-chat" }),
      });
      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "delta") {
                setMessages(prev => {
                  const next = [...prev];
                  next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + data.content };
                  return next;
                });
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], content: "请求失败，请重试。" };
        return next;
      });
    }
    setStreaming(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 100px)" }}>
      <div className="breadcrumb"><b>星禾AI</b> › AI 对话</div>
      <div className="page-head">
        <h1>AI 对话</h1>
        <p>通用 AI 助手，支持多模型对话</p>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 0" }}>
        {messages.length === 0 ? (
          <EmptyState icon={<Bot size={32} />} title="开始对话" description="输入消息与 AI 助手交流" />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                <div style={{ width: 28, height: 28, borderRadius: "var(--radius-md)", background: m.role === "user" ? "var(--bg-muted)" : "var(--brand-50)", color: m.role === "user" ? "var(--text-secondary)" : "var(--brand-500)", display: "grid", placeItems: "center", flexShrink: 0 }}>
                  {m.role === "user" ? <User size={14} /> : <Bot size={14} />}
                </div>
                <div style={{ flex: 1, fontSize: 14, lineHeight: 1.7, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                  {m.content}
                  {i === messages.length - 1 && streaming && !m.content && <Loader2 size={14} className="nc-animate-pulse" style={{ color: "var(--text-muted)" }} />}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, padding: "12px 0", borderTop: "1px solid var(--border-subtle)" }}>
        <input
          className="nc-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="输入消息，Enter 发送..."
          disabled={streaming}
          style={{ flex: 1 }}
        />
        <button className="btn-primary" onClick={send} disabled={streaming || !input.trim()} style={{ padding: "8px 16px", gap: 6 }}>
          {streaming ? <Loader2 size={14} className="nc-animate-pulse" /> : <Send size={14} />}
          发送
        </button>
      </div>
    </div>
  );
}
