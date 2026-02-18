import { CheckCircleOutlined, CircleOutlined, CloseOutlined } from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
import type { ActiveWorkflow } from "../types";

interface Props {
  workflow: ActiveWorkflow;
  onCancel: () => void;
}

export default function WorkflowTracker({ workflow, onCancel }: Props) {
  const { steps, current_step, total_steps, status } = workflow;
  const progress = total_steps > 0 ? ((current_step + (status === "done" ? 1 : 0)) / total_steps) * 100 : 0;
  const isDone = status === "done";

  return (
    <div className="rounded-xl border border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50 px-4 py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-blue-800">
          {isDone ? "Workflow Complete" : "Workflow in Progress"}
        </span>
        {!isDone && (
          <button
            onClick={onCancel}
            className="rounded p-0.5 text-gray-400 hover:bg-white/60 hover:text-gray-600"
            title="Cancel workflow"
          >
            <CloseOutlined sx={{ fontSize: 14 }} />
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-2.5 h-1.5 overflow-hidden rounded-full bg-blue-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            isDone ? "bg-green-500" : "bg-blue-500"
          }`}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {/* Steps */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {step.status === "done" ? (
              <CheckCircleOutlined sx={{ fontSize: 14 }} className="text-green-600" />
            ) : step.status === "running" ? (
              <CircularProgress size={14} className="text-blue-600" />
            ) : (
              <CircleOutlined sx={{ fontSize: 14 }} className="text-gray-300" />
            )}
            <span
              className={`text-[11px] ${
                step.status === "done"
                  ? "text-green-700"
                  : step.status === "running"
                    ? "font-medium text-blue-700"
                    : "text-gray-400"
              }`}
            >
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
