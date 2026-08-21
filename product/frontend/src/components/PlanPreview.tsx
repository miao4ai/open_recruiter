import {
  CheckOutlined,
  CloseOutlined,
  EditOutlined,
  AccountTreeOutlined,
  ArrowForwardOutlined,
  CallSplitOutlined,
  PanToolOutlined,
} from "@mui/icons-material";
import type { PlanPreviewBlock } from "../types";

interface Props {
  block: PlanPreviewBlock;
  onSendPrompt: (prompt: string) => void;
}

const AGENT_LABELS: Record<string, string> = {
  jd: "JD Parser",
  resume: "Resume Parser",
  matching: "Candidate Matching",
  communication: "Email Drafting",
  scheduling: "Interview Scheduling",
  pipeline: "Pipeline Cleanup",
};

const MODE_CONFIG: Record<string, { icon: typeof ArrowForwardOutlined; label: string; color: string }> = {
  sequential: { icon: ArrowForwardOutlined, label: "Sequential", color: "text-blue-600 bg-blue-50" },
  parallel: { icon: CallSplitOutlined, label: "Parallel", color: "text-purple-600 bg-purple-50" },
  interrupt: { icon: PanToolOutlined, label: "Approval", color: "text-amber-600 bg-amber-50" },
};

export default function PlanPreview({ block, onSendPrompt }: Props) {
  const { plan } = block;

  return (
    <div className="rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-100">
          <AccountTreeOutlined sx={{ fontSize: 12 }} className="text-blue-600" />
        </div>
        <span className="text-sm font-semibold text-blue-900">Execution Plan</span>
        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
          {plan.agents_required.length} agent{plan.agents_required.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Goal */}
      <p className="mb-3 text-xs leading-relaxed text-gray-700">{plan.goal}</p>

      {/* Steps */}
      <div className="mb-3 space-y-1.5">
        {plan.steps.map((step, i) => {
          const mode = MODE_CONFIG[step.mode] || MODE_CONFIG.sequential;
          const ModeIcon = mode.icon;
          return (
            <div
              key={i}
              className="flex items-center gap-2.5 rounded-lg border border-gray-100 bg-white px-3 py-2"
            >
              {/* Step number */}
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-gray-100 text-[10px] font-bold text-gray-600">
                {step.step}
              </span>

              {/* Agent + action */}
              <div className="min-w-0 flex-1">
                <span className="text-xs font-medium text-gray-900">
                  {AGENT_LABELS[step.agent] || step.agent}
                </span>
                <span className="ml-1.5 text-xs text-gray-500">
                  — {step.action}
                </span>
              </div>

              {/* Mode badge */}
              <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${mode.color}`}>
                <ModeIcon sx={{ fontSize: 10 }} />
                {mode.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Agents summary */}
      <div className="mb-3 flex flex-wrap gap-1">
        {plan.agents_required.map((agent) => (
          <span
            key={agent}
            className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-medium text-blue-700"
          >
            {AGENT_LABELS[agent] || agent}
          </span>
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onSendPrompt("approve")}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
        >
          <CheckOutlined sx={{ fontSize: 14 }} />
          Approve Plan
        </button>
        <button
          onClick={() => onSendPrompt("modify plan")}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <EditOutlined sx={{ fontSize: 14 }} />
          Modify
        </button>
        <button
          onClick={() => onSendPrompt("cancel")}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <CloseOutlined sx={{ fontSize: 14 }} />
          Cancel
        </button>
      </div>
    </div>
  );
}
