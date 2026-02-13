import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Trash2, Bot, Loader2, Mail, Check, X } from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  sendChatMessage,
  getChatHistory,
  clearChatHistory,
  sendEmail,
  deleteEmail,
  updateEmailDraft,
} from "../lib/api";
import type { ChatMessage, Email } from "../types";

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

/* ── Chat Page ─────────────────────────────────────────────────────────── */

export default function Chat() {
  const { data: history, refresh } = useApi(
    useCallback(() => getChatHistory(), [])
  );
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (history) setMessages(history);
  }, [history]);

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
      const response = await sendChatMessage(userMessage);
      const tempAssistantMsg: ChatMessage = {
        id: "temp-" + Date.now() + "-reply",
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
    // Find the current email data from message state (user may have edited)
    const msg = messages.find(
      (m) => m.action?.type === "compose_email" && m.action.email.id === emailId
    );
    const email = msg?.action?.type === "compose_email" ? msg.action.email : null;

    try {
      // Save any edits the user made before sending
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

      // Update action status to sent
      setMessages((prev) =>
        prev.map((m) =>
          m.action?.type === "compose_email" && m.action.email.id === emailId
            ? { ...m, actionStatus: "sent" as const }
            : m
        )
      );

      // Add congrats message
      const name = email?.candidate_name || "the candidate";
      setMessages((prev) => [
        ...prev,
        {
          id: "congrats-" + Date.now(),
          user_id: "",
          role: "assistant",
          content: `Congrats! Your email to ${name} has been sent successfully. Their status has been updated to "contacted" and you can track it in the Outreach page.`,
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
          content: "Failed to send the email. Please check your email configuration in Settings and try again.",
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

  /* ── Other handlers ────────────────────────────────────────────────── */

  const handleClear = async () => {
    await clearChatHistory();
    setMessages([]);
    refresh();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between pb-4">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-blue-500" />
          <h2 className="text-lg font-semibold">Recruiting Assistant</h2>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleClear}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
          >
            <Trash2 className="h-3.5 w-3.5" /> Clear Chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-gray-200 bg-white p-4">
        {messages.length === 0 && !sending && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <Bot className="h-12 w-12 text-gray-200" />
            <p className="mt-3 text-sm text-gray-400">
              Ask me about your candidates, jobs, or recruiting strategy.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {[
                "Which candidates have the highest match scores?",
                "Draft an email to [candidate name]",
                "Summarize my current pipeline",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-500 hover:bg-gray-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
          >
            {msg.role === "assistant" && (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100">
                <Bot className="h-4 w-4 text-blue-600" />
              </div>
            )}
            <div className="max-w-[80%]">
              {/* Text bubble */}
              <div
                className={`rounded-xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : "bg-gray-50 text-gray-800"
                }`}
              >
                <p className="whitespace-pre-wrap text-sm">{msg.content}</p>
              </div>

              {/* Inline email compose card */}
              {msg.action?.type === "compose_email" && (
                <EmailComposeCard
                  email={msg.action.email}
                  status={msg.actionStatus ?? "pending"}
                  onSend={handleEmailSend}
                  onCancel={handleEmailCancel}
                  onUpdateField={handleEmailFieldUpdate}
                />
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100">
              <Bot className="h-4 w-4 text-blue-600" />
            </div>
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
            placeholder="Ask about candidates, jobs, or say 'send email to [name]'..."
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
  );
}
