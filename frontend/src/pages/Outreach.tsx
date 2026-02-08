import { useCallback } from "react";
import { Mail, Send, Check } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { listEmails, approveEmail, sendEmail } from "../lib/api";

export default function Outreach() {
  const { data: emails, refresh } = useApi(
    useCallback(() => listEmails(), [])
  );

  const pending = emails?.filter((e) => !e.sent) ?? [];
  const sent = emails?.filter((e) => e.sent) ?? [];

  const handleApprove = async (id: string) => {
    await approveEmail(id);
    refresh();
  };

  const handleSend = async (id: string) => {
    await sendEmail(id);
    refresh();
  };

  return (
    <div className="space-y-6">
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
                  <div>
                    <p className="font-medium">{e.subject}</p>
                    <p className="mt-0.5 text-sm text-gray-500">
                      To: {e.to_email || e.candidate_name} &middot;{" "}
                      <span className="capitalize">
                        {e.email_type.replace(/_/g, " ")}
                      </span>
                    </p>
                  </div>
                  <div className="flex gap-2">
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
              No pending emails. Draft emails from the Candidates page.
            </p>
          </div>
        )}
      </div>

      {/* Sent emails */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">
          Sent{" "}
          <span className="text-sm font-normal text-gray-400">
            ({sent.length})
          </span>
        </h2>
        {sent.length > 0 ? (
          <div className="space-y-2">
            {sent.map((e) => (
              <div
                key={e.id}
                className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm"
              >
                <div>
                  <span className="font-medium">{e.subject}</span>
                  <span className="ml-2 text-gray-400">
                    to {e.to_email || e.candidate_name}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>{e.sent_at ? new Date(e.sent_at).toLocaleDateString() : ""}</span>
                  {e.reply_received && (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-emerald-700">
                      Replied
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No sent emails yet.</p>
        )}
      </div>
    </div>
  );
}
