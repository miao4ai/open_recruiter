import { useState } from "react";
import { AccessTimeOutlined, CheckOutlined, CloseOutlined, EventOutlined } from "@mui/icons-material";
import type { SchedulingApprovalBlock } from "../types";

interface Props {
  block: SchedulingApprovalBlock;
  onApprove: (workflowId: string, selectedSlot: { start: string; end: string; label: string }) => void;
  onCancel: (workflowId: string) => void;
  disabled?: boolean;
}

export default function SchedulingApprovalCard({ block, onApprove, onCancel, disabled }: Props) {
  const [selected, setSelected] = useState(0);
  const [decided, setDecided] = useState<"approved" | "cancelled" | null>(null);

  const handleApprove = () => {
    setDecided("approved");
    onApprove(block.workflow_id, block.slots[selected]);
  };

  const handleCancel = () => {
    setDecided("cancelled");
    onCancel(block.workflow_id);
  };

  const isDisabled = disabled || decided !== null;

  return (
    <div className="mt-2 rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100">
          <EventOutlined sx={{ fontSize: 14 }} className="text-blue-600" />
        </div>
        <div>
          <span className="text-sm font-semibold text-blue-900">
            Schedule interview with {block.candidate_name}
          </span>
          {block.job_title && (
            <span className="ml-1.5 text-xs text-gray-500">for {block.job_title}</span>
          )}
        </div>
      </div>

      {/* Time slots */}
      <div className="mb-3 space-y-1.5">
        {block.slots.map((slot, i) => (
          <label
            key={i}
            className={`flex cursor-pointer items-center gap-3 rounded-lg border p-2.5 transition-colors ${
              selected === i
                ? "border-blue-400 bg-blue-50"
                : "border-gray-200 bg-white hover:border-blue-200"
            } ${isDisabled ? "pointer-events-none opacity-60" : ""}`}
          >
            <input
              type="radio"
              name={`slot-${block.workflow_id}`}
              checked={selected === i}
              onChange={() => setSelected(i)}
              disabled={isDisabled}
              className="h-3.5 w-3.5 accent-blue-600"
            />
            <AccessTimeOutlined sx={{ fontSize: 14 }} className="text-gray-400" />
            <span className="text-xs font-medium text-gray-800">{slot.label}</span>
          </label>
        ))}
      </div>

      {/* Status or buttons */}
      {decided === "approved" ? (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-2 text-xs font-medium text-green-700">
          <CheckOutlined sx={{ fontSize: 14 }} />
          Interview scheduled — {block.slots[selected].label}
        </div>
      ) : decided === "cancelled" ? (
        <div className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2 text-xs font-medium text-gray-500">
          <CloseOutlined sx={{ fontSize: 14 }} />
          Cancelled
        </div>
      ) : (
        <div className="flex gap-2">
          <button
            onClick={handleApprove}
            disabled={isDisabled}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <CheckOutlined sx={{ fontSize: 14 }} />
            Confirm & Send Invite
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
