import { useState } from "react";
import { CheckOutlined, CloseOutlined, CleaningServicesOutlined, ReplayOutlined, ArchiveOutlined, BlockOutlined } from "@mui/icons-material";
import type { PipelineCleanupBlock } from "../types";

interface Props {
  block: PipelineCleanupBlock;
  onApprove: (workflowId: string, actions: PipelineCleanupBlock["actions"]) => void;
  onCancel: (workflowId: string) => void;
  disabled?: boolean;
}

const ACTION_CONFIG = {
  follow_up: { label: "Follow Up", icon: ReplayOutlined, color: "text-amber-700", bg: "bg-amber-50", border: "border-amber-200" },
  archive: { label: "Archive", icon: ArchiveOutlined, color: "text-blue-700", bg: "bg-blue-50", border: "border-blue-200" },
  reject: { label: "Reject", icon: BlockOutlined, color: "text-red-700", bg: "bg-red-50", border: "border-red-200" },
} as const;

export default function PipelineCleanupCard({ block, onApprove, onCancel, disabled }: Props) {
  const [checked, setChecked] = useState<Set<string>>(() => new Set(block.actions.map((a) => a.id)));
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
    const selected = block.actions.filter((a) => checked.has(a.id));
    setDecided("approved");
    onApprove(block.workflow_id, selected);
  };

  const handleCancel = () => {
    setDecided("cancelled");
    onCancel(block.workflow_id);
  };

  const isDisabled = disabled || decided !== null;

  const grouped = {
    follow_up: block.actions.filter((a) => a.action === "follow_up"),
    archive: block.actions.filter((a) => a.action === "archive"),
    reject: block.actions.filter((a) => a.action === "reject"),
  };

  return (
    <div className="mt-2 rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100">
          <CleaningServicesOutlined sx={{ fontSize: 14 }} className="text-amber-600" />
        </div>
        <span className="text-sm font-semibold text-amber-900">
          Pipeline Cleanup — {block.actions.length} candidates
        </span>
      </div>

      {/* Action groups */}
      <div className="mb-3 max-h-52 space-y-2 overflow-y-auto">
        {(["follow_up", "archive", "reject"] as const).map((actionType) => {
          const items = grouped[actionType];
          if (items.length === 0) return null;
          const cfg = ACTION_CONFIG[actionType];
          const Icon = cfg.icon;

          return (
            <div key={actionType}>
              <div className={`mb-1 flex items-center gap-1.5 text-xs font-semibold ${cfg.color}`}>
                <Icon sx={{ fontSize: 12 }} />
                {cfg.label} ({items.length})
              </div>
              <div className="space-y-1">
                {items.map((item) => (
                  <label
                    key={item.id}
                    className={`flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 text-xs transition-colors ${cfg.border} ${cfg.bg} ${
                      isDisabled ? "pointer-events-none opacity-60" : ""
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked.has(item.id)}
                      onChange={() => toggle(item.id)}
                      disabled={isDisabled}
                      className="h-3.5 w-3.5 accent-amber-600"
                    />
                    <span className="font-medium text-gray-800">{item.name}</span>
                    <span className="ml-auto text-gray-500">{item.days}d stale</span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Status or buttons */}
      {decided === "approved" ? (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-xs font-medium text-green-700">
          <CheckOutlined sx={{ fontSize: 14 }} />
          Cleanup executed — {checked.size} candidates processed
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
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            <CheckOutlined sx={{ fontSize: 14 }} />
            Execute ({checked.size})
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
