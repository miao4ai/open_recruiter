import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send, Trash2, Loader2, Plus, MessageSquare, X, Heart,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  sendChatMessage,
  getChatHistory,
  clearChatHistory,
  listChatSessions,
  deleteChatSession,
} from "../lib/api";
import type { ChatMessage, ChatSession } from "../types";

/* ── Ai Chan avatar ───────────────────────────────────────────────────── */

function AiChanAvatar({ size = "sm" }: { size?: "sm" | "lg" }) {
  const dim = size === "lg" ? "h-20 w-20" : "h-7 w-7";
  const icon = size === "lg" ? "h-10 w-10" : "h-3.5 w-3.5";
  return (
    <div className={`flex ${dim} shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-pink-400 to-rose-500 shadow-md`}>
      <Heart className={`${icon} text-white`} fill="white" />
    </div>
  );
}

/* ── Greeting message ─────────────────────────────────────────────────── */

function makeGreeting(): ChatMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content:
      "Hi there! I'm Ai Chan, your Job Seeker Assistant. How can I help you today?\n\nI can help you with things like:\n- Preparing for interviews\n- Reviewing your resume\n- Exploring career options\n- Answering questions about job searching",
    created_at: new Date().toISOString(),
  };
}

/* ── Session Sidebar ──────────────────────────────────────────────────── */

function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onNewChat,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (s: ChatSession) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onNewChat: () => void;
}) {
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor(
      (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
    );
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="flex w-64 flex-col rounded-xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 px-3 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-gray-400">
            No past conversations
          </p>
        ) : (
          <div className="space-y-1">
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => onSelect(s)}
                className={`group flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  activeSessionId === s.id
                    ? "bg-pink-50 text-pink-700"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.title}</p>
                  <p className="text-xs text-gray-400">{formatDate(s.updated_at)}</p>
                </div>
                <button
                  onClick={(e) => onDelete(s.id, e)}
                  className="mt-0.5 hidden shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 group-hover:block"
                  title="Delete session"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Chat Page ───────────────────────────────────────────────────── */

export default function JobSeekerHome() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [started, setStarted] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const didAutoSelect = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: sessions, refresh: refreshSessions } = useApi(
    useCallback(() => listChatSessions(), [])
  );

  // Auto-select most recent session on load
  useEffect(() => {
    if (didAutoSelect.current) return;
    if (sessions && sessions.length > 0) {
      didAutoSelect.current = true;
      setActiveSessionId(sessions[0].id);
      setStarted(true);
    } else if (sessions) {
      didAutoSelect.current = true;
    }
  }, [sessions]);

  // Load messages when session changes
  useEffect(() => {
    if (!activeSessionId) return;
    getChatHistory(activeSessionId).then((msgs) => setMessages(msgs));
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ── Send ─────────────────────────────────────────────────────────── */

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const userMessage = input.trim();
    setInput("");
    setSending(true);

    const tempUser: ChatMessage = {
      id: "temp-" + Date.now(),
      user_id: "",
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUser]);

    try {
      const res = await sendChatMessage(userMessage, activeSessionId ?? undefined);
      if (!activeSessionId && res.session_id) {
        setActiveSessionId(res.session_id);
      }
      refreshSessions();

      setMessages((prev) => [
        ...prev,
        {
          id: res.message_id || "temp-reply-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: res.reply,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: "error-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: "Sorry, something went wrong. Please try again.",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  /* ── Session handlers ────────────────────────────────────────────── */

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([makeGreeting()]);
    setStarted(true);
  };

  const handleSelectSession = (s: ChatSession) => {
    setActiveSessionId(s.id);
    setStarted(true);
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteChatSession(id);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setMessages([]);
      setStarted(false);
    }
    refreshSessions();
  };

  const handleClearAll = async () => {
    await clearChatHistory();
    setMessages([]);
    setActiveSessionId(null);
    setStarted(false);
    refreshSessions();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ── Start screen ────────────────────────────────────────────────── */

  if (!started) {
    return (
      <div className="flex h-full p-6">
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="flex flex-col items-center gap-6">
            <AiChanAvatar size="lg" />
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-800">Ai Chan</h1>
              <p className="mt-2 text-gray-500">
                Your Job Seeker Assistant is ready to help
              </p>
            </div>
            <button
              onClick={handleNewChat}
              className="rounded-2xl bg-gradient-to-r from-pink-500 to-rose-500 px-10 py-3.5 text-lg font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl active:scale-100"
            >
              Start Chat
            </button>
          </div>
        </div>

        {sessions && sessions.length > 0 && (
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            onDelete={handleDeleteSession}
            onNewChat={handleNewChat}
          />
        )}
      </div>
    );
  }

  /* ── Chat UI ─────────────────────────────────────────────────────── */

  return (
    <div className="flex h-full gap-4 p-6">
      {/* Main chat */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div className="flex items-center gap-2">
            <AiChanAvatar />
            <h2 className="text-lg font-semibold">Ai Chan</h2>
          </div>
          <button
            onClick={handleClearAll}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear All
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
            >
              {msg.role === "assistant" && <AiChanAvatar />}
              <div className="max-w-[80%]">
                <div
                  className={`rounded-xl px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-pink-500 text-white"
                      : "bg-gray-50 text-gray-800"
                  }`}
                >
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                </div>
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex gap-3">
              <AiChanAvatar />
              <div className="rounded-xl bg-gray-50 px-4 py-3">
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="pt-4">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Ai Chan anything..."
              rows={2}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="flex h-auto items-center justify-center rounded-xl bg-pink-500 px-4 text-white hover:bg-pink-600 disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
          <p className="mt-1 text-center text-xs text-gray-400">
            Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Sessions sidebar */}
      <SessionSidebar
        sessions={sessions ?? []}
        activeSessionId={activeSessionId}
        onSelect={handleSelectSession}
        onDelete={handleDeleteSession}
        onNewChat={handleNewChat}
      />
    </div>
  );
}
