import { useCallback, useEffect, useRef, useState } from "react";
import {
  SendOutlined, DeleteOutline, AddOutlined, ChatBubbleOutlineOutlined, CloseOutlined, UploadOutlined,
  WorkOutlineOutlined, LocationOnOutlined, CheckCircleOutlined, WarningAmberOutlined,
  BookmarkBorderOutlined, SearchOutlined,
} from "@mui/icons-material";
import { CircularProgress, LinearProgress } from "@mui/material";
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
import type { ChatMessage, ChatSession, ChatResponse, JobSearchResultsBlock, JobMatchResultBlock, MessageBlock, Suggestion } from "../types";

/* ── Extended message with blocks & suggestions ──────────────────────── */

interface RichMessage extends ChatMessage {
  blocks?: MessageBlock[];
  suggestions?: Suggestion[];
}

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

function makeGreeting(t: TFunction): RichMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: t("jobSeekerHome.greeting"),
    created_at: new Date().toISOString(),
  };
}

/* ── Job Search Results Card ──────────────────────────────────────────── */

function JobSearchResultsCard({
  block,
  onSelectJob,
}: {
  block: JobSearchResultsBlock;
  onSelectJob: (index: number, title: string, company: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="mt-3 rounded-xl border border-pink-200 bg-pink-50/50 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-pink-700">
        <SearchOutlined className="h-4 w-4" />
        {t("jobSeekerHome.searchResults")} ({block.jobs.length})
      </div>
      <div className="space-y-2">
        {block.jobs.map((job) => (
          <div
            key={job.index}
            className="rounded-lg border border-gray-200 bg-white p-3 transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-pink-100 text-xs font-bold text-pink-600">
                    {job.index}
                  </span>
                  <h4 className="truncate text-sm font-semibold text-gray-800">
                    {job.title}
                  </h4>
                </div>
                {job.company && (
                  <p className="ml-7 text-xs text-gray-500">{job.company}</p>
                )}
                <div className="ml-7 mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
                  {job.location && (
                    <span className="flex items-center gap-0.5">
                      <LocationOnOutlined className="h-3 w-3" />
                      {job.location}
                    </span>
                  )}
                  {job.salary_range && (
                    <span className="flex items-center gap-0.5">
                      <WorkOutlineOutlined className="h-3 w-3" />
                      {job.salary_range}
                    </span>
                  )}
                  {job.source && (
                    <span className="text-gray-400">
                      {job.source}
                    </span>
                  )}
                </div>
                {job.snippet && (
                  <p className="ml-7 mt-1.5 line-clamp-2 text-xs leading-relaxed text-gray-600">
                    {job.snippet}
                  </p>
                )}
              </div>
              <div className="ml-3 flex shrink-0 flex-col items-end gap-1.5">
                <button
                  onClick={() => onSelectJob(job.index, job.title, job.company || "")}
                  className="rounded-lg bg-pink-500 px-3 py-1 text-xs font-medium text-white hover:bg-pink-600"
                >
                  {t("jobSeekerHome.viewDetails")}
                </button>
                {job.url && (
                  <a
                    href={job.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] text-pink-500 hover:underline"
                  >
                    {t("jobSeekerHome.openLink")}
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Job Match Result Card ────────────────────────────────────────────── */

function JobMatchResultCard({
  block,
  onSaveJob,
  onSearchMore,
}: {
  block: JobMatchResultBlock;
  onSaveJob: (title: string, company: string) => void;
  onSearchMore: () => void;
}) {
  const { t } = useTranslation();
  const score = Math.round(block.match.score * 100);

  return (
    <div className="mt-3 rounded-xl border border-blue-200 bg-blue-50/50 p-4">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-800">
          {block.job.title}{block.job.company ? ` @ ${block.job.company}` : ""}
        </h4>
        {block.job.location && (
          <p className="mt-0.5 text-xs text-gray-500">{block.job.location}</p>
        )}
        {block.job.url && (
          <a
            href={block.job.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-block text-xs text-pink-500 hover:underline"
          >
            {t("jobSeekerHome.openLink")}
          </a>
        )}
      </div>

      {/* Score bar */}
      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-gray-600">{t("jobSeekerHome.matchScore")}</span>
          <span className="font-bold text-blue-600">{score}%</span>
        </div>
        <LinearProgress
          variant="determinate"
          value={score}
          sx={{
            height: 8,
            borderRadius: 4,
            bgcolor: "rgb(219 234 254)",
            "& .MuiLinearProgress-bar": {
              borderRadius: 4,
              bgcolor: score >= 70 ? "rgb(34 197 94)" : score >= 40 ? "rgb(234 179 8)" : "rgb(239 68 68)",
            },
          }}
        />
      </div>

      {/* Strengths */}
      {block.match.strengths.length > 0 && (
        <div className="mb-2">
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-green-700">
            <CheckCircleOutlined className="h-3.5 w-3.5" />
            {t("jobSeekerHome.strengths")}
          </p>
          <ul className="ml-5 space-y-0.5 text-xs text-gray-700">
            {block.match.strengths.map((s, i) => (
              <li key={i} className="list-disc">{s}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Gaps */}
      {block.match.gaps.length > 0 && (
        <div className="mb-2">
          <p className="mb-1 flex items-center gap-1 text-xs font-medium text-amber-700">
            <WarningAmberOutlined className="h-3.5 w-3.5" />
            {t("jobSeekerHome.gaps")}
          </p>
          <ul className="ml-5 space-y-0.5 text-xs text-gray-700">
            {block.match.gaps.map((g, i) => (
              <li key={i} className="list-disc">{g}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Reasoning */}
      {block.match.reasoning && (
        <p className="mb-3 text-xs leading-relaxed text-gray-600">
          {block.match.reasoning}
        </p>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onSaveJob(block.job.title, block.job.company || "")}
          className="flex items-center gap-1 rounded-lg bg-pink-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-pink-600"
        >
          <BookmarkBorderOutlined className="h-3.5 w-3.5" />
          {t("jobSeekerHome.saveJob")}
        </button>
        <button
          onClick={onSearchMore}
          className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
        >
          <SearchOutlined className="h-3.5 w-3.5" />
          {t("jobSeekerHome.searchMore")}
        </button>
      </div>
    </div>
  );
}

/* ── Suggestion Chips ─────────────────────────────────────────────────── */

function SuggestionChips({
  suggestions,
  onSelect,
}: {
  suggestions: Suggestion[];
  onSelect: (prompt: string) => void;
}) {
  if (!suggestions || suggestions.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s.prompt)}
          className="rounded-full border border-pink-200 bg-pink-50 px-3 py-1 text-xs text-pink-700 transition-colors hover:bg-pink-100"
        >
          {s.label}
        </button>
      ))}
    </div>
  );
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
  const [messages, setMessages] = useState<RichMessage[]>([]);
  const [started, setStarted] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const didAutoSelect = useRef(false);
  const loadedSessionRef = useRef<string | null>(null);
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
  // Uses loadedSessionRef to skip reload when handleSend just created the session
  // (StrictMode-safe: ref check is idempotent across double-invocations)
  useEffect(() => {
    if (!activeSessionId) return;
    if (loadedSessionRef.current === activeSessionId) return;
    loadedSessionRef.current = activeSessionId;
    getChatHistory(activeSessionId).then((msgs) => {
      const greeting = makeGreeting(t);
      setMessages([greeting, ...msgs]);
    });
  }, [activeSessionId, t]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ── Send ─────────────────────────────────────────────────────────── */

  const handleSend = async (overrideMessage?: string) => {
    const userMessage = (overrideMessage ?? input).trim();
    if (!userMessage || sending) return;
    if (!overrideMessage) setInput("");
    setSending(true);

    if (!started) setStarted(true);

    const tempUser: RichMessage = {
      id: "temp-" + Date.now(),
      user_id: "",
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUser]);

    try {
      const res: ChatResponse = await sendChatMessage(userMessage, activeSessionId ?? undefined);
      if (!activeSessionId && res.session_id) {
        loadedSessionRef.current = res.session_id;
        setActiveSessionId(res.session_id);
      }
      refreshSessions();

      const assistantMsg: RichMessage = {
        id: res.message_id || "temp-reply-" + Date.now(),
        user_id: "",
        role: "assistant",
        content: res.reply,
        created_at: new Date().toISOString(),
        blocks: res.blocks,
        suggestions: res.suggestions,
      };
      setMessages((prev) => [...prev, assistantMsg]);
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

    const tempMsg: RichMessage = {
      id: "upload-" + Date.now(),
      user_id: "",
      role: "user",
      content: t("jobSeekerHome.uploadingResume", { filename: file.name }),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempMsg]);

    try {
      const profile = await uploadResumeForProfile(file);
      const successMsg: RichMessage = {
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
        suggestions: [
          { label: t("jobSeekerHome.searchJobs"), prompt: "帮我找适合我的工作" },
        ],
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
    loadedSessionRef.current = null;
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
      loadedSessionRef.current = null;
      setActiveSessionId(null);
      setMessages([]);
      setStarted(false);
    }
    refreshSessions();
  };

  const handleClearAll = async () => {
    await clearChatHistory();
    loadedSessionRef.current = null;
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

  /* ── Block interaction handlers ──────────────────────────────────── */

  const handleSelectJob = (index: number, title: string, company: string) => {
    handleSend(`帮我分析一下第${index}个职位: ${title}${company ? ` at ${company}` : ""}`);
  };

  const handleSaveJob = (title: string, company: string) => {
    handleSend(`我想保存这个职位: ${title}${company ? ` at ${company}` : ""}`);
  };

  const handleSearchMore = () => {
    handleSend("继续搜索其他职位");
  };

  /* ── Render blocks for a message ─────────────────────────────────── */

  const renderBlocks = (msg: RichMessage) => {
    if (!msg.blocks || msg.blocks.length === 0) return null;
    return msg.blocks.map((block, i) => {
      if (block.type === "job_search_results") {
        return (
          <JobSearchResultsCard
            key={`block-${i}`}
            block={block as JobSearchResultsBlock}
            onSelectJob={handleSelectJob}
          />
        );
      }
      if (block.type === "job_match_result") {
        return (
          <JobMatchResultCard
            key={`block-${i}`}
            block={block as JobMatchResultBlock}
            onSaveJob={handleSaveJob}
            onSearchMore={handleSearchMore}
          />
        );
      }
      return null;
    });
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
            <div key={msg.id}>
              <div
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
                  {/* Render blocks (search results, match analysis) */}
                  {msg.role === "assistant" && renderBlocks(msg)}
                  {/* Render suggestion chips */}
                  {msg.role === "assistant" && msg.suggestions && (
                    <SuggestionChips
                      suggestions={msg.suggestions}
                      onSelect={(prompt) => handleSend(prompt)}
                    />
                  )}
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
              onClick={() => handleSend()}
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
