import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Send, Trash2, Loader2, Mail, Check, X,
  Plus, MessageSquare, Upload, FileText,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  streamChatMessage,
  getChatHistory,
  clearChatHistory,
  sendEmail,
  deleteEmail,
  updateEmailDraft,
  uploadResume,
  uploadJd,
  listChatSessions,
  deleteChatSession,
  listJobs,
  listCandidates,
  updateChatMessageStatus,
  saveChatMessage,
} from "../lib/api";
import PipelineBar from "../components/PipelineBar";
import ContextPanel from "../components/ContextPanel";
import SmartActionBar from "../components/SmartActionBar";
import MessageBlocks from "../components/MessageBlocks";
import WorkflowTracker from "../components/WorkflowTracker";
import type {
  ActiveWorkflow, Candidate, CandidateStatus, ChatMessage, ChatSession,
  ContextView, Email, Job, MessageBlock, Suggestion, WorkflowStepEvent,
} from "../types";

/* ── Greeting / Daily Briefing ──────────────────────────────────────────── */

function makeBriefing(candidates: Candidate[]): ChatMessage {
  const dateStr = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });
  const total = candidates.length;
  const newCount = candidates.filter((c) => c.status === "new").length;
  const contacted = candidates.filter((c) => c.status === "contacted");
  const interviews = candidates.filter((c) => c.status === "interview_scheduled");

  const lines = [`Good morning! Today is ${dateStr}. Here's your recruiting brief:\n`];

  lines.push(`**Pipeline**: ${total} candidate${total !== 1 ? "s" : ""} total`);
  if (newCount > 0) lines.push(`  • ${newCount} new — ready for review`);
  if (contacted.length > 0)
    lines.push(`  • ${contacted.length} awaiting reply (${contacted.slice(0, 3).map((c) => c.name).join(", ")}${contacted.length > 3 ? "..." : ""})`);
  if (interviews.length > 0)
    lines.push(`  • ${interviews.length} interview${interviews.length !== 1 ? "s" : ""} scheduled`);

  lines.push("\nHow can I help you today?");

  return {
    id: "briefing-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: lines.join("\n"),
    created_at: new Date().toISOString(),
  };
}

function makeSimpleGreeting(): ChatMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: `Hi! Welcome to Open Recruiter — I'm Erika, your recruiting assistant. How can I help you today?`,
    created_at: new Date().toISOString(),
  };
}

/* ── Suggestion Builder ─────────────────────────────────────────────────── */

function buildSuggestions(
  messages: ChatMessage[],
  candidates: Candidate[] | null,
  lastAction?: ChatMessage["action"],
): Suggestion[] {
  const result: Suggestion[] = [];

  if (lastAction?.type === "compose_email" || lastAction?.type === "upload_resume") {
    return [];
  }

  if (candidates) {
    const contacted = candidates.filter((c) => c.status === "contacted");
    const newOnes = candidates.filter((c) => c.status === "new");

    if (contacted.length > 0) {
      result.push({ label: "Check for replies", prompt: "Have any contacted candidates replied?", icon: "📩" });
    }
    if (newOnes.length > 0 && newOnes.length <= 5) {
      result.push({ label: `Review ${newOnes[0].name}`, prompt: `What jobs match ${newOnes[0].name}?`, icon: "📊" });
    }
  }

  if (messages.length <= 2) {
    result.push({ label: "Upload resume", prompt: "Upload a resume", icon: "📄" });
    result.push({ label: "Upload JD", prompt: "Upload a job description", icon: "📋" });
  }

  if (result.length === 0) {
    result.push({ label: "Pipeline status", prompt: "What's the pipeline status today?", icon: "📊" });
    result.push({ label: "Upload resume", prompt: "Upload a resume", icon: "📄" });
  }

  return result.slice(0, 4);
}

/* ── Inline Email Compose Card ──────────────────────────────────────────── */

function EmailComposeCard({
  email, status, onSend, onCancel, onUpdateField,
}: {
  email: Email;
  status: "pending" | "sent" | "cancelled";
  onSend: (emailId: string) => void;
  onCancel: (emailId: string) => void;
  onUpdateField: (emailId: string, field: string, value: string) => void;
}) {
  const [sending, setSending] = useState(false);

  if (status === "sent") {
    return (
      <div className="mt-2 rounded-xl border border-green-200 bg-green-50 p-4">
        <div className="flex items-center gap-2 text-green-700"><Check className="h-5 w-5" /><span className="font-medium">Email sent!</span></div>
        <p className="mt-1 text-sm text-green-600">Sent to {email.to_email} ({email.candidate_name})</p>
      </div>
    );
  }
  if (status === "cancelled") {
    return <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3"><p className="text-sm italic text-gray-500">Email draft cancelled.</p></div>;
  }

  const handleSend = async () => {
    setSending(true);
    try { await onSend(email.id); } finally { setSending(false); }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-blue-200 bg-blue-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-blue-700"><Mail className="h-4 w-4" /> Email Draft</div>
      <div className="text-sm">
        <span className="text-gray-500">To:</span> <span className="font-medium">{email.to_email}</span>
        {email.candidate_name && <span className="ml-1 text-gray-400">({email.candidate_name})</span>}
      </div>
      <div>
        <label className="mb-1 block text-xs text-gray-500">Subject</label>
        <input type="text" value={email.subject} onChange={(e) => onUpdateField(email.id, "subject", e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div>
        <label className="mb-1 block text-xs text-gray-500">Body</label>
        <textarea value={email.body} onChange={(e) => onUpdateField(email.id, "body", e.target.value)} rows={8}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={() => onCancel(email.id)} disabled={sending}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button onClick={handleSend} disabled={sending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50">
          {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
          {sending ? "Sending..." : "Send Email"}
        </button>
      </div>
    </div>
  );
}

/* ── Inline Resume Upload Card ──────────────────────────────────────────── */

function ResumeUploadCard({
  status, defaultJobId, uploadedCandidate, onUpload, onCancel,
}: {
  status: "pending" | "uploaded" | "cancelled";
  defaultJobId?: string;
  uploadedCandidate?: Candidate;
  onUpload: (file: File, jobId: string) => void;
  onCancel: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState(defaultJobId || "");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));

  if (status === "uploaded" && uploadedCandidate) {
    return (
      <div className="mt-2 rounded-xl border border-green-200 bg-green-50 p-4">
        <div className="flex items-center gap-2 text-green-700"><Check className="h-5 w-5" /><span className="font-medium">Resume uploaded!</span></div>
        <div className="mt-2 space-y-1 text-sm text-green-700">
          <p><span className="font-medium">Name:</span> {uploadedCandidate.name}</p>
          {uploadedCandidate.current_title && <p><span className="font-medium">Title:</span> {uploadedCandidate.current_title}</p>}
          {uploadedCandidate.skills.length > 0 && <p><span className="font-medium">Skills:</span> {uploadedCandidate.skills.slice(0, 5).join(", ")}</p>}
        </div>
      </div>
    );
  }
  if (status === "cancelled") {
    return <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3"><p className="text-sm italic text-gray-500">Upload cancelled.</p></div>;
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError("");
    try { await onUpload(file, jobId); }
    catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number } };
      setError(axiosErr?.response?.status === 409 ? "Duplicate candidate." : (err instanceof Error ? err.message : "Upload failed"));
    } finally { setUploading(false); }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-purple-200 bg-purple-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-purple-700"><Upload className="h-4 w-4" /> Resume Upload</div>
      <div>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setError(""); }} className="hidden" />
        <button onClick={() => fileRef.current?.click()}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500 hover:border-purple-400 hover:text-purple-600">
          <FileText className="h-4 w-4" /> {file ? file.name : "Click to select a resume (PDF, DOCX, TXT)"}
        </button>
      </div>
      {jobs && jobs.length > 0 && (
        <div>
          <label className="mb-1 block text-xs text-gray-500">Associate with job (optional)</label>
          <select value={jobId} onChange={(e) => setJobId(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500">
            <option value="">No specific job</option>
            {jobs.map((j: Job) => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}
          </select>
        </div>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} disabled={uploading}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button onClick={handleUpload} disabled={uploading || !file}
          className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50">
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? "Uploading..." : "Upload Resume"}
        </button>
      </div>
    </div>
  );
}

/* ── Inline JD Upload Card ──────────────────────────────────────────────── */

function JdUploadCard({
  status, uploadedJob, onUpload, onCancel,
}: {
  status: "pending" | "uploaded" | "cancelled";
  uploadedJob?: Job;
  onUpload: (file: File) => void;
  onCancel: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  if (status === "uploaded" && uploadedJob) {
    return (
      <div className="mt-2 rounded-xl border border-green-200 bg-green-50 p-4">
        <div className="flex items-center gap-2 text-green-700"><Check className="h-5 w-5" /><span className="font-medium">JD uploaded!</span></div>
        <div className="mt-2 space-y-1 text-sm text-green-700">
          <p><span className="font-medium">Title:</span> {uploadedJob.title}</p>
          {uploadedJob.company && <p><span className="font-medium">Company:</span> {uploadedJob.company}</p>}
          {uploadedJob.required_skills?.length > 0 && <p><span className="font-medium">Skills:</span> {uploadedJob.required_skills.slice(0, 5).join(", ")}</p>}
        </div>
      </div>
    );
  }
  if (status === "cancelled") {
    return <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3"><p className="text-sm italic text-gray-500">Upload cancelled.</p></div>;
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError("");
    try { await onUpload(file); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Upload failed"); }
    finally { setUploading(false); }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-orange-200 bg-orange-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-orange-700"><FileText className="h-4 w-4" /> Job Description Upload</div>
      <div>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setError(""); }} className="hidden" />
        <button onClick={() => fileRef.current?.click()}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500 hover:border-orange-400 hover:text-orange-600">
          <FileText className="h-4 w-4" /> {file ? file.name : "Click to select a JD file (PDF, DOCX, TXT)"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} disabled={uploading}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button onClick={handleUpload} disabled={uploading || !file}
          className="inline-flex items-center gap-1.5 rounded-lg bg-orange-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-50">
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? "Uploading..." : "Upload JD"}
        </button>
      </div>
    </div>
  );
}

/* ── Session Sidebar ────────────────────────────────────────────────────── */

function SessionSidebar({
  sessions, activeSessionId, onSelect, onDelete, onNewChat,
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
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <div className="flex w-56 flex-col rounded-xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 p-2.5">
        <button onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-3 py-2 text-xs font-medium text-white hover:opacity-90">
          <Plus className="h-3.5 w-3.5" /> New Chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-1.5">
        {sessions.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-gray-400">No conversations yet</p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => (
              <button key={s.id} onClick={() => onSelect(s)}
                className={`group flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                  activeSessionId === s.id ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-50"
                }`}>
                <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.title}</p>
                  <p className="text-[10px] text-gray-400">{formatDate(s.updated_at)}</p>
                </div>
                <button onClick={(e) => onDelete(s.id, e)}
                  className="mt-0.5 hidden shrink-0 rounded p-0.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600 group-hover:block"
                  title="Delete">
                  <X className="h-3 w-3" />
                </button>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Control Center (Chat Page) ─────────────────────────────────────────── */

export default function Chat() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [contextView, setContextView] = useState<ContextView | null>({ type: "briefing" });
  const [pipelineStage, setPipelineStage] = useState<CandidateStatus | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [backendSuggestions, setBackendSuggestions] = useState<Suggestion[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<ActiveWorkflow | null>(null);
  const didAutoSelect = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: sessions, refresh: refreshSessions } = useApi(useCallback(() => listChatSessions(), []));
  const { data: candidates, refresh: refreshCandidates } = useApi(useCallback(() => listCandidates(), []));

  // Auto-select most recent session
  useEffect(() => {
    if (didAutoSelect.current || !sessions) return;
    didAutoSelect.current = true;
    if (sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    } else {
      setMessages([candidates ? makeBriefing(candidates) : makeSimpleGreeting()]);
    }
  }, [sessions, candidates]);

  // Load messages when session changes
  useEffect(() => {
    if (!activeSessionId) return;
    getChatHistory(activeSessionId).then((msgs) => {
      if (msgs.length === 0) {
        setMessages([candidates ? makeBriefing(candidates) : makeSimpleGreeting()]);
      } else {
        setMessages(msgs);
      }
    });
  }, [activeSessionId, candidates]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Derive last action for context panel auto-switch
  const lastAction = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].action) return messages[i].action;
    }
    return undefined;
  }, [messages]);

  // Context auto-switch is now handled by backend context_hint in handleSend

  const suggestions = useMemo(
    () => backendSuggestions.length > 0
      ? backendSuggestions
      : buildSuggestions(messages, candidates ?? null, lastAction),
    [messages, candidates, lastAction, backendSuggestions],
  );

  /* ── Send ──────────────────────────────────────────────────────────────── */

  const handleSend = async (overrideMessage?: string) => {
    const text = overrideMessage || input.trim();
    if (!text || sending) return;
    if (!overrideMessage) setInput("");
    setSending(true);
    setStreamingText("");

    setMessages((prev) => [...prev, {
      id: "temp-" + Date.now(), user_id: "", role: "user",
      content: text, created_at: new Date().toISOString(),
    }]);

    // Accumulate streamed JSON and extract the "message" field progressively
    let accumulated = "";
    const extractMessage = (raw: string): string => {
      const match = raw.match(/"message"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)/);
      if (!match) return "";
      return match[1]
        .replace(/\\n/g, "\n")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, "\\");
    };

    try {
      const response = await streamChatMessage(
        text,
        activeSessionId ?? undefined,
        (token) => {
          accumulated += token;
          const msg = extractMessage(accumulated);
          if (msg) setStreamingText(msg);
        },
        (stepEvent: WorkflowStepEvent) => {
          setActiveWorkflow((prev) => {
            const steps = prev?.steps ?? [];
            // Build updated steps array from the event
            const updated = [...steps];
            while (updated.length <= stepEvent.step_index) {
              updated.push({ label: "", status: "pending" });
            }
            updated[stepEvent.step_index] = {
              label: stepEvent.label,
              status: stepEvent.status as "pending" | "running" | "done" | "skipped",
            };
            return {
              workflow_id: stepEvent.workflow_id,
              workflow_type: prev?.workflow_type ?? "bulk_outreach",
              status: "running",
              current_step: stepEvent.step_index,
              total_steps: stepEvent.total_steps,
              steps: updated,
            };
          });
        },
      );

      setStreamingText("");
      if (!activeSessionId && response.session_id) setActiveSessionId(response.session_id);
      refreshSessions();
      refreshCandidates();

      // Handle workflow status from done event
      if (response.workflow_id && response.workflow_status) {
        if (response.workflow_status === "done" || response.workflow_status === "cancelled") {
          // Clear tracker after a short delay so user sees the final state
          setTimeout(() => setActiveWorkflow(null), 3000);
          setActiveWorkflow((prev) =>
            prev ? { ...prev, status: response.workflow_status! } : null
          );
        } else if (response.workflow_status === "paused") {
          // Workflow paused at approval — clear the tracker (approval block shows in chat)
          setActiveWorkflow(null);
        }
      }

      setMessages((prev) => [...prev, {
        id: response.message_id || "reply-" + Date.now(),
        user_id: "", role: "assistant", content: response.reply,
        created_at: new Date().toISOString(),
        action: response.action, actionStatus: response.action ? "pending" : undefined,
        blocks: response.blocks,
      }]);

      // Apply backend suggestions and context hint
      if (response.suggestions && response.suggestions.length > 0) {
        setBackendSuggestions(response.suggestions);
      } else {
        setBackendSuggestions([]);
      }
      if (response.context_hint) {
        setContextView(response.context_hint);
        setPipelineStage(null);
      }
    } catch {
      setStreamingText("");
      setMessages((prev) => [...prev, {
        id: "error-" + Date.now(), user_id: "", role: "assistant",
        content: "Sorry, I encountered an error. Please try again.",
        created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  };

  /* ── Email handlers ────────────────────────────────────────────────────── */

  const handleEmailSend = async (emailId: string) => {
    const msg = messages.find((m) => m.action?.type === "compose_email" && m.action.email.id === emailId);
    const email = msg?.action?.type === "compose_email" ? msg.action.email : null;
    try {
      if (email) {
        await updateEmailDraft(emailId, {
          to_email: email.to_email, subject: email.subject, body: email.body,
          email_type: email.email_type, candidate_id: email.candidate_id,
          candidate_name: email.candidate_name,
        });
      }
      await sendEmail(emailId);
      if (msg) updateChatMessageStatus(msg.id, "sent").catch(() => {});
      setMessages((prev) => prev.map((m) =>
        m.action?.type === "compose_email" && m.action.email.id === emailId
          ? { ...m, actionStatus: "sent" as const } : m));
      const name = email?.candidate_name || "the candidate";
      const content = `Great news! Your email to ${name} has been sent successfully. Is there anything else?`;
      if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
      setMessages((prev) => [...prev, { id: "congrats-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
      refreshCandidates();
    } catch {
      const content = "Failed to send the email. Please check your email configuration in Settings.";
      if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
      setMessages((prev) => [...prev, { id: "error-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    }
  };

  const handleEmailCancel = async (emailId: string) => {
    try { await deleteEmail(emailId); } catch { /* ignore */ }
    const msg = messages.find((m) => m.action?.type === "compose_email" && m.action.email.id === emailId);
    if (msg) updateChatMessageStatus(msg.id, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.action?.type === "compose_email" && m.action.email.id === emailId
        ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  const handleEmailFieldUpdate = (emailId: string, field: string, value: string) => {
    setMessages((prev) => prev.map((m) => {
      if (m.action?.type === "compose_email" && m.action.email.id === emailId) {
        return { ...m, action: { ...m.action, email: { ...m.action.email, [field]: value } } };
      }
      return m;
    }));
  };

  /* ── Resume upload handlers ────────────────────────────────────────────── */

  const handleResumeUpload = async (msgId: string, file: File, jobId: string) => {
    const candidate: Candidate = await uploadResume(file, jobId);
    updateChatMessageStatus(msgId, "uploaded").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, actionStatus: "uploaded" as const, uploadedCandidate: candidate } : m));
    const skills = candidate.skills?.slice(0, 3).join(", ") || "N/A";
    const content = `${candidate.name}'s resume has been uploaded!\n\n- Title: ${candidate.current_title || "N/A"}\n- Skills: ${skills}\n- Experience: ${candidate.experience_years ?? "N/A"} years\n\nWould you like me to match them to a job or draft an outreach email?`;
    if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
    setMessages((prev) => [...prev, { id: "resume-ok-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    refreshCandidates();
    setContextView({ type: "candidate", id: candidate.id });
  };

  const handleResumeCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  /* ── JD upload handlers ────────────────────────────────────────────────── */

  const handleJdUpload = async (msgId: string, file: File) => {
    const job: Job = await uploadJd(file);
    updateChatMessageStatus(msgId, "uploaded").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, actionStatus: "uploaded" as const, uploadedJob: job } : m));
    const skills = job.required_skills?.slice(0, 3).join(", ") || "N/A";
    const content = `**${job.title}**${job.company ? ` at ${job.company}` : ""} has been uploaded!\n\n- Skills: ${skills}\n- Experience: ${job.experience_years ?? "N/A"} years\n- Location: ${job.location || "N/A"}${job.remote ? " (Remote)" : ""}\n\nWould you like me to match candidates to this job?`;
    if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
    setMessages((prev) => [...prev, { id: "jd-ok-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    setContextView({ type: "job", id: job.id });
  };

  const handleJdCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  /* ── Session handlers ──────────────────────────────────────────────────── */

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([candidates ? makeBriefing(candidates) : makeSimpleGreeting()]);
    setContextView({ type: "briefing" });
    setPipelineStage(null);
  };

  const handleSelectSession = (s: ChatSession) => setActiveSessionId(s.id);

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteChatSession(id);
    if (activeSessionId === id) { setActiveSessionId(null); setMessages([]); }
    refreshSessions();
  };

  const handleClearAll = async () => {
    await clearChatHistory();
    setMessages([]); setActiveSessionId(null); refreshSessions();
  };

  /* ── Pipeline + Context ────────────────────────────────────────────────── */

  const handleStageClick = (stage: CandidateStatus) => {
    if (pipelineStage === stage) {
      setPipelineStage(null); setContextView({ type: "briefing" });
    } else {
      setPipelineStage(stage); setContextView({ type: "pipeline_stage", stage });
    }
  };

  const handleViewCandidate = (id: string) => { setContextView({ type: "candidate", id }); setPipelineStage(null); };
  const handleViewJob = (id: string) => { setContextView({ type: "job", id }); setPipelineStage(null); };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  /* ── Render ────────────────────────────────────────────────────────────── */

  return (
    <div className="flex h-full flex-col gap-3">
      {/* Pipeline Bar */}
      <PipelineBar candidates={candidates ?? []} activeStage={pipelineStage} onStageClick={handleStageClick} />

      {/* Workflow Tracker */}
      {activeWorkflow && (
        <WorkflowTracker
          workflow={activeWorkflow}
          onCancel={() => {
            setActiveWorkflow(null);
            handleSend("cancel workflow");
          }}
        />
      )}

      {/* Main: sessions + chat + context */}
      <div className="flex min-h-0 flex-1 gap-3">
        {/* Sessions */}
        <SessionSidebar sessions={sessions ?? []} activeSessionId={activeSessionId}
          onSelect={handleSelectSession} onDelete={handleDeleteSession} onNewChat={handleNewChat} />

        {/* Chat */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between pb-2">
            <div className="flex items-center gap-2">
              <img src="/ai-chan-avatar.png" alt="Erika Chan" className="h-7 w-7 rounded-full object-cover" />
              <h2 className="text-sm font-semibold text-gray-800">Erika Chan</h2>
            </div>
            <button onClick={handleClearAll}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1 text-[10px] font-medium text-gray-500 hover:bg-gray-50">
              <Trash2 className="h-3 w-3" /> Clear
            </button>
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex gap-2.5 ${msg.role === "user" ? "justify-end" : ""}`}>
                {msg.role === "assistant" && (
                  <img src="/ai-chan-avatar.png" alt="Erika" className="h-6 w-6 shrink-0 rounded-full object-cover" />
                )}
                <div className="max-w-[85%]">
                  <div className={`rounded-xl px-3.5 py-2.5 ${
                    msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-50 text-gray-800"
                  }`}>
                    <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                  </div>

                  {msg.action?.type === "compose_email" && (
                    <EmailComposeCard email={msg.action.email}
                      status={(msg.actionStatus ?? "pending") as "pending" | "sent" | "cancelled"}
                      onSend={handleEmailSend} onCancel={handleEmailCancel} onUpdateField={handleEmailFieldUpdate} />
                  )}
                  {msg.action?.type === "upload_resume" && (
                    <ResumeUploadCard
                      status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                      defaultJobId={msg.action.job_id}
                      uploadedCandidate={(msg as ChatMessage & { uploadedCandidate?: Candidate }).uploadedCandidate}
                      onUpload={(file, jobId) => handleResumeUpload(msg.id, file, jobId)}
                      onCancel={() => handleResumeCancel(msg.id)} />
                  )}
                  {msg.action?.type === "upload_jd" && (
                    <JdUploadCard
                      status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                      uploadedJob={(msg as ChatMessage & { uploadedJob?: Job }).uploadedJob}
                      onUpload={(file) => handleJdUpload(msg.id, file)}
                      onCancel={() => handleJdCancel(msg.id)} />
                  )}

                  {msg.blocks && msg.blocks.length > 0 && (
                    <MessageBlocks
                      blocks={msg.blocks}
                      onSendPrompt={(p) => handleSend(p)}
                      onViewCandidate={handleViewCandidate}
                      onViewJob={handleViewJob}
                    />
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex gap-2.5">
                <img src="/ai-chan-avatar.png" alt="Erika" className="h-6 w-6 shrink-0 rounded-full object-cover" />
                <div className="max-w-[85%]">
                  <div className="rounded-xl bg-gray-50 px-3.5 py-2.5 text-gray-800">
                    {streamingText ? (
                      <p className="whitespace-pre-wrap text-sm">{streamingText}<span className="ml-0.5 inline-block h-4 w-1 animate-pulse bg-gray-400" /></p>
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                    )}
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <SmartActionBar suggestions={suggestions} onSelect={(p) => handleSend(p)} />

          <div className="flex gap-2 pt-1">
            <textarea value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown} placeholder="Ask Erika anything..." rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            <button onClick={() => handleSend()} disabled={sending || !input.trim()}
              className="flex items-center justify-center rounded-xl bg-blue-600 px-4 text-white hover:bg-blue-700 disabled:opacity-50">
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Context Panel */}
        <ContextPanel view={contextView}
          onClose={() => { setContextView(null); setPipelineStage(null); }}
          onViewCandidate={handleViewCandidate} onViewJob={handleViewJob}
          onSendPrompt={(p) => handleSend(p)} />
      </div>
    </div>
  );
}
