import React, { useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, UserRound } from "lucide-react";

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
  onRequestEdit: (instruction: string, targetText: string) => void;
};

const INITIAL_MESSAGE = "告诉我你想怎么改。我会结合当前正文、跨章状态和审阅证据生成修改候选，先预览，确认后才应用。";

function newMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return { id: crypto.randomUUID(), role, content };
}

export function EditorAiChat({ chapterId, selection, busy = false, suggestions = [], onRequestEdit }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [newMessage("assistant", INITIAL_MESSAGE)]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const target = selection.trim();

  useEffect(() => {
    setMessages([newMessage("assistant", INITIAL_MESSAGE)]);
    setInput("");
  }, [chapterId]);

  useEffect(() => {
    if (typeof bottomRef.current?.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages, busy]);

  function submit() {
    const instruction = input.trim();
    if (!instruction || busy) return;
    const scope = target ? `选区（${target.length} 字）` : "整章";
    setMessages(previous => [
      ...previous,
      newMessage("user", instruction),
      newMessage("assistant", `收到。我会按「${scope}」生成修改候选，完成后会出现在上方预览区。`),
    ]);
    setInput("");
    onRequestEdit(instruction, target);
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
        <span className="editor-ai-chat-status">{busy ? "生成中" : "可对话"}</span>
      </div>

      <div className="editor-ai-chat-messages" role="log" aria-live="polite">
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
