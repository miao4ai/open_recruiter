import { useState } from "react";
import { CheckOutlined, CloseOutlined, SendOutlined, ExpandMoreOutlined, ExpandLessOutlined } from "@mui/icons-material";
import type { BulkOutreachBlock } from "../types";

interface Props {
  block: BulkOutreachBlock;
  onApprove: (workflowId: string, drafts: BulkOutreachBlock["drafts"]) => void;
  onCancel: (workflowId: string) => void;
  disabled?: boolean;
}

export default function BulkOutreachCard({ block, onApprove, onCancel, disabled }: Props) {
  const [checked, setChecked] = useState<Set<string>>(() => new Set(block.drafts.map((d) => d.candidate_id)));
  const [expanded, setExpanded] = useState<string | null>(null);
  const [decided, setDecided] = useState<"approved" | "cancelled" | null>(null);

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleApprove = () => {
    const selected = block.drafts.filter((d) => checked.has(d.candidate_id));
    setDecided("approved");
    onApprove(block.workflow_id, selected);
  };

  const handleCancel = () => {
    setDecided("cancelled");
    onCancel(block.workflow_id);
  };

  const isDisabled = disabled || decided !== null;

  return (
    <div className="mt-2 rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100">
          <SendOutlined sx={{ fontSize: 14 }} className="text-indigo-600" />
        </div>
        <span className="text-sm font-semibold text-indigo-900">
          Send {block.drafts.length} outreach emails
        </span>
        {block.job_title && (
          <span className="text-xs text-gray-500">— {block.job_title}</span>
        )}
      </div>

      {/* Email drafts */}
      <div className="mb-3 max-h-64 space-y-1.5 overflow-y-auto">
        {block.drafts.map((draft) => {
          const isExpanded = expanded === draft.candidate_id;
          const scorePct = Math.round(draft.match_score * 100);

          return (
            <div
              key={draft.candidate_id}
              className={`rounded-lg border bg-white transition-colors ${
                checked.has(draft.candidate_id) ? "border-indigo-300" : "border-gray-200"
              } ${isDisabled ? "opacity-60" : ""}`}
            >
              <div className="flex items-center gap-2.5 px-3 py-2">
                <input
                  type="checkbox"
                  checked={checked.has(draft.candidate_id)}
                  onChange={() => toggle(draft.candidate_id)}
                  disabled={isDisabled}
                  className="h-3.5 w-3.5 accent-indigo-600"
                />
                <div className="min-w-0 flex-1">
                  <span className="text-xs font-medium text-gray-800">{draft.candidate_name}</span>
                  <span className="ml-2 text-[10px] text-gray-400">{scorePct}% match</span>
                </div>
                <button
                  onClick={() => setExpanded(isExpanded ? null : draft.candidate_id)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  {isExpanded ? (
                    <ExpandLessOutlined sx={{ fontSize: 16 }} />
                  ) : (
                    <ExpandMoreOutlined sx={{ fontSize: 16 }} />
                  )}
                </button>
              </div>

              {isExpanded && (
                <div className="border-t border-gray-100 px-3 py-2">
                  <div className="mb-1 text-[10px] font-semibold text-gray-500">Subject</div>
                  <div className="mb-2 text-xs text-gray-800">{draft.subject}</div>
                  <div className="mb-1 text-[10px] font-semibold text-gray-500">Preview</div>
                  <div className="max-h-20 overflow-y-auto text-xs leading-relaxed text-gray-600">
                    {draft.preview}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Status or buttons */}
      {decided === "approved" ? (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-xs font-medium text-green-700">
          <CheckOutlined sx={{ fontSize: 14 }} />
          {checked.size} emails sent
        </div>
      ) : decided === "cancelled" ? (
        <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs font-medium text-gray-500">
          <CloseOutlined sx={{ fontSize: 14 }} />
          Cancelled
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <button
            onClick={handleApprove}
            disabled={isDisabled || checked.size === 0}
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <SendOutlined sx={{ fontSize: 14 }} />
            Send All ({checked.size})
          </button>
          <button
            onClick={handleCancel}
            disabled={isDisabled}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <CloseOutlined sx={{ fontSize: 14 }} />
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
