import { useCallback, useEffect, useRef, useState } from "react";
import {
  SendOutlined, DeleteOutline, AddOutlined, ChatBubbleOutlineOutlined, CloseOutlined, UploadOutlined,
} from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { useApi } from "../hooks/useApi";
import {
  sendChatMessage,
  getChatHistory,
  clearChatHistory,
  listChatSessions,
  deleteChatSession,
  saveChatMessage,
  uploadResumeForProfile,
} from "../lib/api";
import type { ChatMessage, ChatSession } from "../types";

/* ── Ai Chan avatar ───────────────────────────────────────────────────── */

function AiChanAvatar({ size = "sm" }: { size?: "sm" | "lg" }) {
  const dim = size === "lg" ? "h-20 w-20" : "h-7 w-7";
  return (
    <img
      src="/ai-chan-avatar.png"
      alt="Ai Chan"
      className={`${dim} shrink-0 rounded-full object-cover shadow-md`}
    />
  );
}

/* ── Greeting message ─────────────────────────────────────────────────── */

function makeGreeting(t: TFunction): ChatMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: t("jobSeekerHome.greeting"),
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
  const { t } = useTranslation();

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor(
      (now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
    );
    if (diffDays === 0) return t("common.today");
    if (diffDays === 1) return t("common.yesterday");
    if (diffDays < 7) return t("common.daysAgo", { count: diffDays });
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="flex w-64 flex-col rounded-xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 px-3 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          <AddOutlined className="h-4 w-4" />
          {t("jobSeekerHome.newChat")}
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-gray-400">
            {t("jobSeekerHome.noPastConversations")}
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
                <ChatBubbleOutlineOutlined className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.title}</p>
                  <p className="text-xs text-gray-400">{formatDate(s.updated_at)}</p>
                </div>
                <button
                  onClick={(e) => onDelete(s.id, e)}
                  className="mt-0.5 hidden shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 group-hover:block"
                  title={t("jobSeekerHome.deleteSession")}
                >
                  <CloseOutlined className="h-3.5 w-3.5" />
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
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [started, setStarted] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const didAutoSelect = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

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

  // Load messages when session changes — always prepend greeting
  useEffect(() => {
    if (!activeSessionId) return;
    getChatHistory(activeSessionId).then((msgs) => {
      const greeting = makeGreeting(t);
      setMessages([greeting, ...msgs]);
    });
  }, [activeSessionId, t]);

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
          content: t("jobSeekerHome.genericError"),
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  /* ── Resume upload ──────────────────────────────────────────────── */

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);

    if (!started) {
      setStarted(true);
    }

    const tempMsg: ChatMessage = {
      id: "upload-" + Date.now(),
      user_id: "",
      role: "user",
      content: t("jobSeekerHome.uploadingResume", { filename: file.name }),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempMsg]);

    try {
      const profile = await uploadResumeForProfile(file);
      const successMsg: ChatMessage = {
        id: "upload-success-" + Date.now(),
        user_id: "",
        role: "assistant",
        content:
          `${t("jobSeekerHome.resumeProcessed")}\n\n` +
          `**Name:** ${profile.name || "N/A"}\n` +
          `**Title:** ${profile.current_title || "N/A"}\n` +
          `**Company:** ${profile.current_company || "N/A"}\n` +
          `**Skills:** ${(profile.skills || []).slice(0, 8).join(", ") || "N/A"}\n` +
          `**Experience:** ${profile.experience_years ?? "N/A"} years\n` +
          `**Location:** ${profile.location || "N/A"}\n\n` +
          t("jobSeekerHome.viewProfile"),
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, successMsg]);

      if (activeSessionId) {
        saveChatMessage(activeSessionId, successMsg.content).catch(() => {});
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: "upload-error-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: t("jobSeekerHome.uploadError"),
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  /* ── Session handlers ────────────────────────────────────────────── */

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([makeGreeting(t)]);
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
              <h1 className="text-2xl font-bold text-gray-800">{t("jobSeekerHome.aiChan")}</h1>
              <p className="mt-2 text-gray-500">
                {t("jobSeekerHome.assistantReady")}
              </p>
            </div>
            <button
              onClick={handleNewChat}
              className="rounded-2xl bg-gradient-to-r from-pink-500 to-rose-500 px-10 py-3.5 text-lg font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl active:scale-100"
            >
              {t("jobSeekerHome.startChat")}
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
            <h2 className="text-lg font-semibold">{t("jobSeekerHome.aiChan")}</h2>
          </div>
          <button
            onClick={handleClearAll}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            <DeleteOutline className="h-3.5 w-3.5" /> {t("jobSeekerHome.clearAll")}
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
                <CircularProgress size={16} sx={{ color: 'rgb(156 163 175)' }} />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="pt-4">
          <div className="flex gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              onChange={handleResumeUpload}
              className="hidden"
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading || sending}
              className="flex items-center justify-center rounded-xl border border-gray-300 px-3
                text-gray-500 hover:bg-gray-50 hover:text-pink-500 disabled:opacity-50"
              title={t("jobSeekerHome.uploadResumeTitle")}
            >
              {uploading ? (
                <CircularProgress size={20} />
              ) : (
                <UploadOutlined className="h-5 w-5" />
              )}
            </button>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("jobSeekerHome.askAiChan")}
              rows={2}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="flex h-auto items-center justify-center rounded-xl bg-pink-500 px-4 text-white hover:bg-pink-600 disabled:opacity-50"
            >
              <SendOutlined className="h-5 w-5" />
            </button>
          </div>
          <p className="mt-1 text-center text-xs text-gray-400">
            {t("jobSeekerHome.inputHint")}
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
