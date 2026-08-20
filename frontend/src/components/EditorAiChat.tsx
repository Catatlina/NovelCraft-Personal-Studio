import React, { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, UserRound } from "lucide-react";
import { api } from "../lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type Props = {
  chapterId: string;
  selection: string;
  busy?: boolean;
  suggestions?: string[];
  onRequestEdit: (instruction: string, targetText: string) => Promise<{ text?: string } | null | undefined> | { text?: string } | null | undefined;
};

function newMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return { id: crypto.randomUUID(), role, content };
}

export function EditorAiChat({ chapterId, selection, busy = false, suggestions = [], onRequestEdit }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const sessionPromiseRef = useRef<Promise<any> | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const target = selection.trim();

  async function loadOrCreateSession(): Promise<any> {
    if (sessionId) return { id: sessionId, messages: [] };
    if (sessionPromiseRef.current) return sessionPromiseRef.current;
    const pending = (async () => {
      let session = await api<any>(`/api/v1/authoring/sessions/current?content_id=${encodeURIComponent(chapterId)}`);
      if (!session) {
        session = await api<any>("/api/v1/authoring/sessions", {
          method: "POST",
          body: JSON.stringify({ content_id: chapterId, role_key: "scene_expander" }),
        });
      }
      const id = String(session.id || "");
      if (!id) throw new Error("创作会话未建立");
      setSessionId(id);
      return { ...session, id };
    })();
    sessionPromiseRef.current = pending;
    try {
      return await pending;
    } finally {
      if (sessionPromiseRef.current === pending) sessionPromiseRef.current = null;
    }
  }

  useEffect(() => {
    let active = true;
    setMessages([]);
    setInput("");
    setSessionId("");
    setSessionError("");
    setSessionLoading(true);
    (async () => {
      try {
        const session = await loadOrCreateSession();
        if (!active) return;
        setSessionId(String(session.id || ""));
        const restored = (session.messages || []).map((message: any) => ({
          id: String(message.id || crypto.randomUUID()),
          role: message.role === "user" ? "user" : "assistant",
          content: String(message.content || ""),
        }));
        setMessages(previous => previous.length ? previous : restored);
      } catch (caught) {
        if (!active) return;
        setSessionError(caught instanceof Error ? caught.message : "会话暂时无法恢复");
      } finally {
        if (active) setSessionLoading(false);
      }
    })();
    return () => { active = false; };
  }, [chapterId]);

  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages, busy]);

  async function submit() {
    const instruction = input.trim();
    if (!instruction || busy) return;
    const scope = target ? `选区（${target.length} 字）` : "整章";
    const mutationId = crypto.randomUUID();
    setMessages(previous => [...previous, newMessage("user", instruction)]);
    setInput("");
    try {
      const session = await loadOrCreateSession();
      const currentSessionId = String(session.id);
      await api(`/api/v1/authoring/sessions/${currentSessionId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          role: "user",
          content: instruction,
          message_kind: "instruction",
          metadata: { scope, selection_chars: target.length, client_mutation_id: mutationId },
        }),
      });
      const result = await onRequestEdit(instruction, target);
      if (result?.text) {
        const assistantText = `候选已生成（${result.text.length} 字），请在预览区确认后应用。`;
        setMessages(previous => [...previous, newMessage("assistant", assistantText)]);
        await api(`/api/v1/authoring/sessions/${currentSessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "assistant",
            content: assistantText,
            message_kind: "candidate",
            candidate: { text: result.text, requires_human_confirmation: true },
            metadata: { client_mutation_id: mutationId, scope },
          }),
        });
      } else {
        const failure = "未返回可用候选，原文未改变";
        setMessages(previous => [...previous, newMessage("assistant", failure)]);
        await api(`/api/v1/authoring/sessions/${currentSessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "assistant",
            content: failure,
            message_kind: "error",
            candidate: { provider_verified: false, original_unchanged: true },
            metadata: { client_mutation_id: mutationId, scope, error: failure },
          }),
        });
      }
    } catch (caught) {
      const failure = caught instanceof Error ? caught.message : "本次 AI 操作失败，原文未改变";
      setMessages(previous => [...previous, newMessage("assistant", `本次操作未完成：${failure}`)]);
      try {
        const session = await loadOrCreateSession();
        const currentSessionId = String(session.id);
        await api(`/api/v1/authoring/sessions/${currentSessionId}/messages`, {
          method: "POST",
          body: JSON.stringify({
            role: "assistant",
            content: `本次操作未完成：${failure}`,
            message_kind: "error",
            candidate: { provider_verified: false },
            metadata: { client_mutation_id: mutationId, error: failure },
          }),
        });
      } catch {
        setSessionError("AI 失败状态未能写入会话，请稍后刷新重试");
      }
    }
  }

  function useSuggestion(suggestion: string) {
    setInput(`请根据这条审阅意见修改：${suggestion}`);
  }

  return (
    <section className="editor-ai-chat" aria-label="AI 修改会话">
      <div className="editor-ai-chat-context">
        <div>
          <span className="editor-ai-chat-kicker">修改范围</span>
          <strong>{target ? `已选文字 · ${target.length} 字` : "整章正文"}</strong>
        </div>
        <span className="editor-ai-chat-status">{busy ? "生成中" : sessionLoading ? "恢复中" : sessionError ? "记录异常" : "可对话"}</span>
      </div>

      {sessionError ? <div className="editor-ai-chat-error" role="alert">{sessionError}</div> : null}

      <div className="editor-ai-chat-messages" role="log" aria-live="polite">
        {!messages.length && !busy ? <p className="editor-ai-chat-empty">这里会保留本章的真实 AI 会话。先告诉 AI 你想推进哪一处。</p> : null}
        {messages.map(message => (
          <div key={message.id} className={`editor-ai-chat-message ${message.role}`}>
            <span className="editor-ai-chat-avatar" aria-hidden="true">
              {message.role === "user" ? <UserRound size={13} /> : <Bot size={13} />}
            </span>
            <p>{message.content}</p>
          </div>
        ))}
        {busy ? (
          <div className="editor-ai-chat-message assistant" role="status">
            <span className="editor-ai-chat-avatar" aria-hidden="true"><Bot size={13} /></span>
            <p className="editor-ai-chat-loading"><Loader2 size={13} /> 正在生成候选，原文不会被直接覆盖…</p>
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {suggestions.length > 0 ? (
        <div className="editor-ai-chat-suggestions" aria-label="审阅意见快捷带入">
          <span>把审阅意见带入会话</span>
          {suggestions.slice(0, 3).map((suggestion, index) => (
            <button key={`${suggestion}-${index}`} type="button" onClick={() => useSuggestion(suggestion)} disabled={busy}>
              {suggestion}
            </button>
          ))}
        </div>
      ) : null}

      <div className="editor-ai-chat-compose">
        <textarea
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder={target ? "例如：把这段写得更紧、更爽，保留事实和人物关系" : "例如：加强本章冲突和章末钩子，保留现有剧情"}
          aria-label="输入修改意见"
          maxLength={1000}
          disabled={busy}
          rows={3}
        />
        <div className="editor-ai-chat-compose-footer">
          <small>Enter 发送 · Shift+Enter 换行</small>
          <button type="button" className="btn-primary" onClick={submit} disabled={busy || !input.trim()}>
            {busy ? <Loader2 size={14} className="nc-animate-pulse" /> : <Send size={14} />}
            生成修改
          </button>
        </div>
      </div>
    </section>
  );
}
