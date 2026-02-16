import { useCallback, useEffect, useRef, useState } from "react";
import {
  Send, Trash2, Loader2, Mail, Check, X,
  Plus, MessageSquare, Upload, FileText,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  sendChatMessage,
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
  updateChatMessageStatus,
  saveChatMessage,
} from "../lib/api";
import type { Candidate, ChatMessage, ChatSession, Email, Job } from "../types";

/* ── Helper: format today's date for Erika's greeting ──────────────────── */

function formatGreetingDate(): string {
  return new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function makeGreetingMessage(): ChatMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: `Hi! Today is ${formatGreetingDate()}. Welcome to Open Recruiter — I'm Erika, your recruiting assistant.`,
    created_at: new Date().toISOString(),
  };
}

/* ── Inline Email Compose Card ─────────────────────────────────────────── */

function EmailComposeCard({
  email,
  status,
  onSend,
  onCancel,
  onUpdateField,
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
        <div className="flex items-center gap-2 text-green-700">
          <Check className="h-5 w-5" />
          <span className="font-medium">Email sent successfully!</span>
        </div>
        <p className="mt-1 text-sm text-green-600">
          Sent to {email.to_email} ({email.candidate_name})
        </p>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
        <p className="text-sm italic text-gray-500">Email draft cancelled.</p>
      </div>
    );
  }

  const handleSend = async () => {
    setSending(true);
    try {
      await onSend(email.id);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-blue-200 bg-blue-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-blue-700">
        <Mail className="h-4 w-4" />
        Email Draft
      </div>

      {/* To (read-only) */}
      <div className="text-sm">
        <span className="text-gray-500">To:</span>{" "}
        <span className="font-medium">{email.to_email}</span>
        {email.candidate_name && (
          <span className="ml-1 text-gray-400">({email.candidate_name})</span>
        )}
      </div>

      {/* Editable subject */}
      <div>
        <label className="mb-1 block text-xs text-gray-500">Subject</label>
        <input
          type="text"
          value={email.subject}
          onChange={(e) => onUpdateField(email.id, "subject", e.target.value)}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Editable body */}
      <div>
        <label className="mb-1 block text-xs text-gray-500">Body</label>
        <textarea
          value={email.body}
          onChange={(e) => onUpdateField(email.id, "body", e.target.value)}
          rows={8}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <button
          onClick={() => onCancel(email.id)}
          disabled={sending}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button
          onClick={handleSend}
          disabled={sending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {sending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
          {sending ? "Sending..." : "Send Email"}
        </button>
      </div>
    </div>
  );
}

/* ── Inline Resume Upload Card ────────────────────────────────────────── */

function ResumeUploadCard({
  status,
  defaultJobId,
  uploadedCandidate,
  onUpload,
  onCancel,
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
        <div className="flex items-center gap-2 text-green-700">
          <Check className="h-5 w-5" />
          <span className="font-medium">Resume uploaded successfully!</span>
        </div>
        <div className="mt-2 space-y-1 text-sm text-green-700">
          <p><span className="font-medium">Name:</span> {uploadedCandidate.name}</p>
          {uploadedCandidate.current_title && (
            <p><span className="font-medium">Title:</span> {uploadedCandidate.current_title}</p>
          )}
          {uploadedCandidate.skills.length > 0 && (
            <p><span className="font-medium">Skills:</span> {uploadedCandidate.skills.slice(0, 5).join(", ")}</p>
          )}
        </div>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
        <p className="text-sm italic text-gray-500">Resume upload cancelled.</p>
      </div>
    );
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await onUpload(file, jobId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      if (typeof err === "object" && err !== null && "response" in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 409) {
          setError("A candidate with this name and email already exists.");
        } else {
          setError(msg);
        }
      } else {
        setError(msg);
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-purple-200 bg-purple-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-purple-700">
        <Upload className="h-4 w-4" />
        Resume Upload
      </div>

      {/* File picker */}
      <div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setError("");
          }}
          className="hidden"
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500 hover:border-purple-400 hover:text-purple-600"
        >
          <FileText className="h-4 w-4" />
          {file ? file.name : "Click to select a resume (PDF, DOCX, TXT)"}
        </button>
      </div>

      {/* Job selector */}
      {jobs && jobs.length > 0 && (
        <div>
          <label className="mb-1 block text-xs text-gray-500">Associate with job (optional)</label>
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
          >
            <option value="">No specific job</option>
            {jobs.map((j: Job) => (
              <option key={j.id} value={j.id}>
                {j.title} — {j.company}
              </option>
            ))}
          </select>
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          disabled={uploading}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button
          onClick={handleUpload}
          disabled={uploading || !file}
          className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          {uploading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Upload className="h-3.5 w-3.5" />
          )}
          {uploading ? "Uploading..." : "Upload Resume"}
        </button>
      </div>
    </div>
  );
}

/* ── Inline JD Upload Card ───────────────────────────────────────────── */

function JdUploadCard({
  status,
  uploadedJob,
  onUpload,
  onCancel,
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
        <div className="flex items-center gap-2 text-green-700">
          <Check className="h-5 w-5" />
          <span className="font-medium">JD uploaded successfully!</span>
        </div>
        <div className="mt-2 space-y-1 text-sm text-green-700">
          <p><span className="font-medium">Title:</span> {uploadedJob.title}</p>
          {uploadedJob.company && (
            <p><span className="font-medium">Company:</span> {uploadedJob.company}</p>
          )}
          {uploadedJob.required_skills && uploadedJob.required_skills.length > 0 && (
            <p><span className="font-medium">Required Skills:</span> {uploadedJob.required_skills.slice(0, 5).join(", ")}</p>
          )}
          {uploadedJob.location && (
            <p><span className="font-medium">Location:</span> {uploadedJob.location}</p>
          )}
        </div>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3">
        <p className="text-sm italic text-gray-500">JD upload cancelled.</p>
      </div>
    );
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      await onUpload(file);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="mt-2 space-y-3 rounded-xl border border-orange-200 bg-orange-50/50 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-orange-700">
        <FileText className="h-4 w-4" />
        Job Description Upload
      </div>

      {/* File picker */}
      <div>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setError("");
          }}
          className="hidden"
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-white px-4 py-3 text-sm text-gray-500 hover:border-orange-400 hover:text-orange-600"
        >
          <FileText className="h-4 w-4" />
          {file ? file.name : "Click to select a JD file (PDF, DOCX, TXT)"}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Action buttons */}
      <div className="flex justify-end gap-2">
        <button
          onClick={onCancel}
          disabled={uploading}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          <X className="h-3.5 w-3.5" /> Cancel
        </button>
        <button
          onClick={handleUpload}
          disabled={uploading || !file}
          className="inline-flex items-center gap-1.5 rounded-lg bg-orange-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-orange-700 disabled:opacity-50"
        >
          {uploading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Upload className="h-3.5 w-3.5" />
          )}
          {uploading ? "Uploading..." : "Upload JD"}
        </button>
      </div>
    </div>
  );
}

/* ── Chat Page ─────────────────────────────────────────────────────────── */

export default function Chat() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [started, setStarted] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const didAutoSelect = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load sessions list
  const { data: sessions, refresh: refreshSessions } = useApi(
    useCallback(() => listChatSessions(), [])
  );

  // On initial load only, auto-select the most recent session
  useEffect(() => {
    if (didAutoSelect.current) return;
    if (sessions && sessions.length > 0) {
      didAutoSelect.current = true;
      const latest = sessions[0]; // sorted by updated_at DESC
      setActiveSessionId(latest.id);
      setStarted(true);
    } else if (sessions) {
      didAutoSelect.current = true;
    }
  }, [sessions]);

  // Load messages when active session changes
  useEffect(() => {
    if (!activeSessionId) return;
    getChatHistory(activeSessionId).then((msgs) => {
      setMessages(msgs);
    });
  }, [activeSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ── Send message ──────────────────────────────────────────────────── */

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const userMessage = input.trim();
    setInput("");
    setSending(true);

    const tempUserMsg: ChatMessage = {
      id: "temp-" + Date.now(),
      user_id: "",
      role: "user",
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await sendChatMessage(userMessage, activeSessionId ?? undefined);

      // If this was a new session (no activeSessionId), capture the returned session_id
      if (!activeSessionId && response.session_id) {
        setActiveSessionId(response.session_id);
        refreshSessions();
      } else {
        // Refresh sessions to update timestamps / titles
        refreshSessions();
      }

      const tempAssistantMsg: ChatMessage = {
        id: response.message_id || "temp-" + Date.now() + "-reply",
        user_id: "",
        role: "assistant",
        content: response.reply,
        created_at: new Date().toISOString(),
        action: response.action,
        actionStatus: response.action ? "pending" : undefined,
      };
      setMessages((prev) => [...prev, tempAssistantMsg]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: "error-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  /* ── Email action handlers ─────────────────────────────────────────── */

  const handleEmailSend = async (emailId: string) => {
    const msg = messages.find(
      (m) => m.action?.type === "compose_email" && m.action.email.id === emailId
    );
    const email = msg?.action?.type === "compose_email" ? msg.action.email : null;

    try {
      if (email) {
        await updateEmailDraft(emailId, {
          to_email: email.to_email,
          subject: email.subject,
          body: email.body,
          email_type: email.email_type,
          candidate_id: email.candidate_id,
          candidate_name: email.candidate_name,
        });
      }
      await sendEmail(emailId);

      // Persist action status to backend
      if (msg) {
        updateChatMessageStatus(msg.id, "sent").catch(() => {});
      }

      setMessages((prev) =>
        prev.map((m) =>
          m.action?.type === "compose_email" && m.action.email.id === emailId
            ? { ...m, actionStatus: "sent" as const }
            : m
        )
      );

      const name = email?.candidate_name || "the candidate";
      const congratsContent = `Great news! Your email to ${name} has been sent successfully and their status has been updated to "contacted". Is there anything else you'd like me to help with? For example, I can draft emails to other candidates, schedule interviews, or review your pipeline.`;

      // Save congratulatory message to backend
      if (activeSessionId) {
        saveChatMessage(activeSessionId, congratsContent).catch(() => {});
      }

      setMessages((prev) => [
        ...prev,
        {
          id: "congrats-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: congratsContent,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch {
      const errorContent = "Failed to send the email. Please check your email configuration in Settings and try again.";

      if (activeSessionId) {
        saveChatMessage(activeSessionId, errorContent).catch(() => {});
      }

      setMessages((prev) => [
        ...prev,
        {
          id: "error-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: errorContent,
          created_at: new Date().toISOString(),
        },
      ]);
    }
  };

  const handleEmailCancel = async (emailId: string) => {
    try {
      await deleteEmail(emailId);
    } catch {
      // Ignore — draft may already be gone
    }
    // Find the message and persist cancel status
    const msg = messages.find(
      (m) => m.action?.type === "compose_email" && m.action.email.id === emailId
    );
    if (msg) {
      updateChatMessageStatus(msg.id, "cancelled").catch(() => {});
    }
    setMessages((prev) =>
      prev.map((m) =>
        m.action?.type === "compose_email" && m.action.email.id === emailId
          ? { ...m, actionStatus: "cancelled" as const }
          : m
      )
    );
  };

  const handleEmailFieldUpdate = (
    emailId: string,
    field: string,
    value: string
  ) => {
    setMessages((prev) =>
      prev.map((m) => {
        if (
          m.action?.type === "compose_email" &&
          m.action.email.id === emailId
        ) {
          return {
            ...m,
            action: {
              ...m.action,
              email: { ...m.action.email, [field]: value },
            },
          };
        }
        return m;
      })
    );
  };

  /* ── Resume upload handlers ──────────────────────────────────────────── */

  const handleResumeUpload = async (msgId: string, file: File, jobId: string) => {
    try {
      const candidate: Candidate = await uploadResume(file, jobId);

      // Persist action status to backend
      updateChatMessageStatus(msgId, "uploaded").catch(() => {});

      // Update the message with uploaded status + candidate data
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, actionStatus: "uploaded" as const, uploadedCandidate: candidate }
            : m
        )
      );

      // Append congratulatory message
      const skills = candidate.skills?.slice(0, 3).join(", ") || "N/A";
      const congratsContent = `${candidate.name}'s resume has been uploaded and processed! Here's a quick summary:\n\n- Title: ${candidate.current_title || "N/A"}\n- Skills: ${skills}\n- Experience: ${candidate.experience_years ?? "N/A"} years\n\nWould you like me to draft an outreach email, match them to a job, or upload another resume?`;

      // Save to backend
      if (activeSessionId) {
        saveChatMessage(activeSessionId, congratsContent).catch(() => {});
      }

      setMessages((prev) => [
        ...prev,
        {
          id: "resume-success-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: congratsContent,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      throw err; // Let ResumeUploadCard handle the error display
    }
  };

  const handleResumeCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? { ...m, actionStatus: "cancelled" as const }
          : m
      )
    );
  };

  /* ── JD upload handlers ──────────────────────────────────────────────── */

  const handleJdUpload = async (msgId: string, file: File) => {
    try {
      const job: Job = await uploadJd(file);

      updateChatMessageStatus(msgId, "uploaded").catch(() => {});

      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, actionStatus: "uploaded" as const, uploadedJob: job }
            : m
        )
      );

      const skills = job.required_skills?.slice(0, 3).join(", ") || "N/A";
      const congratsContent = `The job description for **${job.title}**${job.company ? ` at ${job.company}` : ""} has been uploaded and processed! Here's a quick summary:\n\n- Required Skills: ${skills}\n- Experience: ${job.experience_years ?? "N/A"} years\n- Location: ${job.location || "N/A"}${job.remote ? " (Remote)" : ""}\n\nWould you like me to match candidates to this job, or upload another JD?`;

      if (activeSessionId) {
        saveChatMessage(activeSessionId, congratsContent).catch(() => {});
      }

      setMessages((prev) => [
        ...prev,
        {
          id: "jd-success-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: congratsContent,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      throw err;
    }
  };

  const handleJdCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId
          ? { ...m, actionStatus: "cancelled" as const }
          : m
      )
    );
  };

  /* ── Session handlers ───────────────────────────────────────────────── */

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([makeGreetingMessage()]);
    setStarted(true);
  };

  const handleSelectSession = (session: ChatSession) => {
    setActiveSessionId(session.id);
    setStarted(true);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteChatSession(sessionId);
    if (activeSessionId === sessionId) {
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

  const handleStart = () => {
    setStarted(true);
    setMessages([makeGreetingMessage()]);
  };

  /* ── Helper: format session date ─────────────────────────────────────── */

  const formatSessionDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  /* ── Start screen ────────────────────────────────────────────────────── */

  if (!started) {
    return (
      <div className="flex h-full">
        {/* Main area — start screen */}
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="flex flex-col items-center gap-6">
            <img
              src="/ai-chan-avatar.png"
              alt="Erika Chan"
              className="h-24 w-24 rounded-full object-cover shadow-lg"
            />
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-800">Open Recruiter</h1>
              <p className="mt-2 text-gray-500">
                Your AI recruiting assistant Erika is ready
              </p>
            </div>
            <button
              onClick={handleStart}
              className="rounded-2xl bg-gradient-to-r from-blue-600 to-purple-600 px-10 py-3.5 text-lg font-semibold text-white shadow-lg transition-all hover:scale-105 hover:shadow-xl active:scale-100"
            >
              Start Chat
            </button>
          </div>
        </div>

        {/* Right sidebar — past sessions */}
        {sessions && sessions.length > 0 && (
          <SessionSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={handleSelectSession}
            onDelete={handleDeleteSession}
            onNewChat={handleNewChat}
            formatDate={formatSessionDate}
          />
        )}
      </div>
    );
  }

  /* ── Chat interface ──────────────────────────────────────────────────── */

  return (
    <div className="flex h-full gap-4">
      {/* Main chat area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4">
          <div className="flex items-center gap-2">
            <img
              src="/ai-chan-avatar.png"
              alt="Erika Chan"
              className="h-8 w-8 rounded-full object-cover"
            />
            <h2 className="text-lg font-semibold">Erika Chan</h2>
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
              {msg.role === "assistant" && (
                <img
                  src="/ai-chan-avatar.png"
                  alt="Erika Chan"
                  className="h-7 w-7 shrink-0 rounded-full object-cover"
                />
              )}
              <div className="max-w-[80%]">
                <div
                  className={`rounded-xl px-4 py-3 ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-50 text-gray-800"
                  }`}
                >
                  <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
                </div>

                {msg.action?.type === "compose_email" && (
                  <EmailComposeCard
                    email={msg.action.email}
                    status={(msg.actionStatus ?? "pending") as "pending" | "sent" | "cancelled"}
                    onSend={handleEmailSend}
                    onCancel={handleEmailCancel}
                    onUpdateField={handleEmailFieldUpdate}
                  />
                )}

                {msg.action?.type === "upload_resume" && (
                  <ResumeUploadCard
                    status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                    defaultJobId={msg.action.job_id}
                    uploadedCandidate={(msg as ChatMessage & { uploadedCandidate?: Candidate }).uploadedCandidate}
                    onUpload={(file, jobId) => handleResumeUpload(msg.id, file, jobId)}
                    onCancel={() => handleResumeCancel(msg.id)}
                  />
                )}

                {msg.action?.type === "upload_jd" && (
                  <JdUploadCard
                    status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                    uploadedJob={(msg as ChatMessage & { uploadedJob?: Job }).uploadedJob}
                    onUpload={(file) => handleJdUpload(msg.id, file)}
                    onCancel={() => handleJdCancel(msg.id)}
                  />
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex gap-3">
              <img
                src="/ai-chan-avatar.png"
                alt="Erika Chan"
                className="h-7 w-7 shrink-0 rounded-full object-cover"
              />
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
              placeholder="Ask Erika anything..."
              rows={2}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className="flex h-auto items-center justify-center rounded-xl bg-blue-600 px-4 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
          <p className="mt-1 text-center text-xs text-gray-400">
            Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Right sidebar — sessions */}
      <SessionSidebar
        sessions={sessions ?? []}
        activeSessionId={activeSessionId}
        onSelect={handleSelectSession}
        onDelete={handleDeleteSession}
        onNewChat={handleNewChat}
        formatDate={formatSessionDate}
      />
    </div>
  );
}

/* ── Session Sidebar Component ─────────────────────────────────────────── */

function SessionSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onNewChat,
  formatDate,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (s: ChatSession) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onNewChat: () => void;
  formatDate: (d: string) => string;
}) {
  return (
    <div className="flex w-64 flex-col rounded-xl border border-gray-200 bg-white">
      {/* New Chat button */}
      <div className="border-b border-gray-100 p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 px-3 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      {/* Session list */}
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
                    ? "bg-blue-50 text-blue-700"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{s.title}</p>
                  <p className="text-xs text-gray-400">
                    {formatDate(s.updated_at)}
                  </p>
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
