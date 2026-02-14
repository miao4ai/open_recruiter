import { useCallback, useState } from "react";
import {
  Mail, Send, Check, Plus, X, Trash2, Pencil,
  RefreshCw, MessageSquareText, ChevronDown, ChevronUp,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  listEmails,
  approveEmail,
  sendEmail,
  composeEmail,
  updateEmailDraft,
  deleteEmail,
  markEmailReplied,
  checkReplies,
} from "../lib/api";
import type { Email, EmailType } from "../types";

// ── Email templates ──────────────────────────────────────────────────────

const EMAIL_TEMPLATES: Record<
  EmailType,
  { subject: string; body: string }
> = {
  outreach: {
    subject: "Exciting Career Opportunity — [Position Title]",
    body: `Hi [Candidate Name],

I hope this message finds you well. I came across your profile and was very impressed by your background and experience.

We are currently looking for talented professionals to join our team, and I believe your skills would be a great fit for a role we have open.

Here are a few highlights:
• Competitive compensation and benefits
• Collaborative and innovative team environment
• Opportunities for growth and career development

Would you be open to a brief conversation to learn more? I'd love to share the details and answer any questions you might have.

Looking forward to hearing from you!

Best regards`,
  },
  followup: {
    subject: "Following Up — Career Opportunity",
    body: `Hi [Candidate Name],

I wanted to follow up on my previous message regarding the opportunity I shared with you.

I understand you may be busy, but I wanted to reiterate my interest in connecting with you. The role is still available and I think it could be a great match for your experience.

Would you have 15 minutes this week for a quick call?

Best regards`,
  },
  interview_invite: {
    subject: "Interview Invitation — [Position Title]",
    body: `Hi [Candidate Name],

Thank you for your interest in the position. We were very impressed with your background and would like to invite you to an interview.

Here are the details:
• Date: [Date]
• Time: [Time]
• Format: [Video call / In-person]
• Duration: Approximately 45 minutes

Please let me know if this works for you, or if you'd prefer an alternative time.

Looking forward to speaking with you!

Best regards`,
  },
  rejection: {
    subject: "Update on Your Application",
    body: `Hi [Candidate Name],

Thank you for taking the time to speak with us about the opportunity. We truly appreciated learning about your experience and accomplishments.

After careful consideration, we have decided to move forward with other candidates whose qualifications more closely align with our current needs.

This decision was not easy, and we encourage you to apply for future openings that match your skills. We will keep your profile on file for future reference.

We wish you all the best in your career journey.

Warm regards`,
  },
};

const EMAIL_TYPE_LABELS: Record<EmailType, string> = {
  outreach: "Outreach",
  followup: "Follow-up",
  interview_invite: "Interview Invite",
  rejection: "Rejection",
};

// ── Compose / Edit Modal ─────────────────────────────────────────────────

interface ComposeModalProps {
  draft?: Email;
  onClose: () => void;
  onDone: () => void;
}

function ComposeModal({ draft, onClose, onDone }: ComposeModalProps) {
  const isEdit = !!draft;

  const [emailType, setEmailType] = useState<EmailType>(
    draft?.email_type ?? "outreach"
  );
  const [toEmail, setToEmail] = useState(draft?.to_email ?? "");
  const [subject, setSubject] = useState(
    draft?.subject ?? EMAIL_TEMPLATES.outreach.subject
  );
  const [body, setBody] = useState(
    draft?.body ?? EMAIL_TEMPLATES.outreach.body
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleTypeChange = (type: EmailType) => {
    setEmailType(type);
    // Only auto-fill template content for new emails
    if (!isEdit) {
      setSubject(EMAIL_TEMPLATES[type].subject);
      setBody(EMAIL_TEMPLATES[type].body);
    }
  };

  const handleSave = async (andSend: boolean) => {
    if (!toEmail.trim()) {
      setError("Recipient email is required");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const payload = {
        to_email: toEmail.trim(),
        subject,
        body,
        email_type: emailType,
      };

      let emailId: string;
      if (isEdit) {
        const updated = await updateEmailDraft(draft.id, payload);
        emailId = updated.id;
      } else {
        const created = await composeEmail(payload);
        emailId = created.id;
      }

      if (andSend) {
        await sendEmail(emailId);
      }
      onDone();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to save email";
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative mx-4 flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="text-lg font-semibold">
            {isEdit ? "Edit Draft" : "Compose Email"}
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Email Type */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Template
            </label>
            <div className="flex gap-2">
              {(Object.keys(EMAIL_TYPE_LABELS) as EmailType[]).map((type) => (
                <button
                  key={type}
                  onClick={() => handleTypeChange(type)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    emailType === type
                      ? "bg-blue-600 text-white"
                      : "border border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {EMAIL_TYPE_LABELS[type]}
                </button>
              ))}
            </div>
          </div>

          {/* To */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              To
            </label>
            <input
              type="email"
              value={toEmail}
              onChange={(e) => setToEmail(e.target.value)}
              placeholder="recipient@example.com"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Subject */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Subject
            </label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Body */}
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Body
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={14}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm leading-relaxed focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => handleSave(false)}
            disabled={saving}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {isEdit ? "Save Draft" : "Save as Draft"}
          </button>
          <button
            onClick={() => handleSave(true)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {saving ? "Sending..." : "Send Now"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────

export default function Outreach() {
  const { data: emails, refresh } = useApi(
    useCallback(() => listEmails(), [])
  );
  const [composeMode, setComposeMode] = useState<
    { open: false } | { open: true; draft?: Email }
  >({ open: false });

  const pending = emails?.filter((e) => !e.sent) ?? [];
  const sent = emails?.filter((e) => e.sent) ?? [];

  const handleApprove = async (id: string) => {
    await approveEmail(id);
    refresh();
  };

  const handleSend = async (id: string) => {
    try {
      await sendEmail(id);
      refresh();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to send";
      alert(msg);
    }
  };

  const handleDelete = async (id: string) => {
    await deleteEmail(id);
    refresh();
  };

  const handleMarkReplied = async (id: string) => {
    await markEmailReplied(id);
    refresh();
  };

  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<string | null>(null);
  const handleCheckReplies = async () => {
    setChecking(true);
    setCheckResult(null);
    try {
      const res = await checkReplies();
      setCheckResult(
        res.replies_found > 0
          ? `Found ${res.replies_found} new ${res.replies_found === 1 ? "reply" : "replies"}!`
          : "No new replies found."
      );
      refresh();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Failed to check replies";
      setCheckResult(msg);
    } finally {
      setChecking(false);
    }
  };

  // Track which sent emails are expanded
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {/* Compose / Edit modal */}
      {composeMode.open && (
        <ComposeModal
          draft={composeMode.draft}
          onClose={() => setComposeMode({ open: false })}
          onDone={() => {
            setComposeMode({ open: false });
            refresh();
          }}
        />
      )}

      {/* Header with compose button */}
      <div className="flex items-center justify-between">
        <div />
        <button
          onClick={() => setComposeMode({ open: true })}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" /> Compose Email
        </button>
      </div>

      {/* Pending queue */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">
          Pending{" "}
          <span className="text-sm font-normal text-gray-400">
            ({pending.length})
          </span>
        </h2>
        {pending.length > 0 ? (
          <div className="space-y-3">
            {pending.map((e) => (
              <div
                key={e.id}
                className="rounded-xl border border-gray-200 bg-white p-5"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium">{e.subject}</p>
                      {!e.approved && (
                        <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                          Draft
                        </span>
                      )}
                      {e.approved && (
                        <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          Approved
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-sm text-gray-500">
                      To: {e.to_email || e.candidate_name} &middot;{" "}
                      <span className="capitalize">
                        {e.email_type.replace(/_/g, " ")}
                      </span>
                    </p>
                  </div>
                  <div className="ml-4 flex shrink-0 gap-2">
                    <button
                      onClick={() =>
                        setComposeMode({ open: true, draft: e })
                      }
                      className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      title="Edit draft"
                    >
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </button>
                    {!e.approved && (
                      <button
                        onClick={() => handleApprove(e.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                      >
                        <Check className="h-3.5 w-3.5" /> Approve
                      </button>
                    )}
                    <button
                      onClick={() => handleSend(e.id)}
                      className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
                    >
                      <Send className="h-3.5 w-3.5" /> Send
                    </button>
                    <button
                      onClick={() => handleDelete(e.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                      title="Delete"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
                <div className="mt-3 whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                  {e.body}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center">
            <Mail className="mx-auto h-8 w-8 text-gray-300" />
            <p className="mt-2 text-sm text-gray-400">
              No pending emails. Click "Compose Email" to create one.
            </p>
          </div>
        )}
      </div>

      {/* Sent emails */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Sent{" "}
            <span className="text-sm font-normal text-gray-400">
              ({sent.length})
            </span>
          </h2>
          <div className="flex items-center gap-2">
            {checkResult && (
              <span className="text-xs text-gray-500">{checkResult}</span>
            )}
            <button
              onClick={handleCheckReplies}
              disabled={checking}
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${checking ? "animate-spin" : ""}`} />
              {checking ? "Checking..." : "Check for Replies"}
            </button>
          </div>
        </div>
        {sent.length > 0 ? (
          <div className="space-y-2">
            {sent.map((e) => {
              const isExpanded = expandedIds.has(e.id);
              return (
                <div
                  key={e.id}
                  className="rounded-lg border border-gray-200 bg-white text-sm"
                >
                  {/* Sent email row */}
                  <div className="flex items-center justify-between px-4 py-3">
                    <button
                      onClick={() => toggleExpand(e.id)}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 flex-shrink-0 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 flex-shrink-0 text-gray-400" />
                      )}
                      <span className="truncate font-medium">{e.subject}</span>
                      <span className="text-gray-400">
                        to {e.to_email || e.candidate_name}
                      </span>
                    </button>
                    <div className="ml-4 flex items-center gap-2 text-xs text-gray-400">
                      <span>
                        {e.sent_at
                          ? new Date(e.sent_at).toLocaleDateString()
                          : ""}
                      </span>
                      {e.reply_received ? (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700">
                          Replied
                        </span>
                      ) : (
                        <button
                          onClick={(ev) => { ev.stopPropagation(); handleMarkReplied(e.id); }}
                          className="inline-flex items-center gap-1 rounded-full border border-gray-200 px-2 py-0.5 font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700"
                          title="Mark as replied"
                        >
                          <MessageSquareText className="h-3 w-3" />
                          Mark Replied
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expanded: email body + reply */}
                  {isExpanded && (
                    <div className="border-t border-gray-100 px-4 py-3 space-y-3">
                      <div className="whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
                        {e.body}
                      </div>
                      {e.reply_received && e.reply_body && (
                        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                          <div className="mb-1 flex items-center gap-1 text-xs font-medium text-emerald-700">
                            <MessageSquareText className="h-3.5 w-3.5" />
                            Reply received
                            {e.replied_at && (
                              <span className="ml-1 font-normal text-emerald-600">
                                — {new Date(e.replied_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                          <div className="whitespace-pre-wrap text-sm text-gray-700">
                            {e.reply_body}
                          </div>
                        </div>
                      )}
                      {e.reply_received && !e.reply_body && (
                        <div className="flex items-center gap-1 text-xs text-emerald-600">
                          <MessageSquareText className="h-3.5 w-3.5" />
                          Reply received (manually marked)
                          {e.replied_at && (
                            <span className="text-emerald-500">
                              — {new Date(e.replied_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No sent emails yet.</p>
        )}
      </div>
    </div>
  );
}
