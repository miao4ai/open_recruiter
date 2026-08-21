import {
  ShieldOutlined,
  WarningAmberOutlined,
  BlockOutlined,
  CheckCircleOutline,
  LightbulbOutlined,
} from "@mui/icons-material";
import type { GuardrailWarningBlock, GuardrailSeverity } from "../types";

interface Props {
  block: GuardrailWarningBlock;
  onSendPrompt: (prompt: string) => void;
}

const SEVERITY_CONFIG: Record<GuardrailSeverity, {
  icon: typeof ShieldOutlined;
  border: string;
  bg: string;
  iconBg: string;
  iconColor: string;
  titleColor: string;
  label: string;
}> = {
  pass: {
    icon: CheckCircleOutline,
    border: "border-green-200",
    bg: "from-green-50/80 to-white",
    iconBg: "bg-green-100",
    iconColor: "text-green-600",
    titleColor: "text-green-900",
    label: "Passed",
  },
  warning: {
    icon: WarningAmberOutlined,
    border: "border-amber-200",
    bg: "from-amber-50/80 to-white",
    iconBg: "bg-amber-100",
    iconColor: "text-amber-600",
    titleColor: "text-amber-900",
    label: "Warning",
  },
  blocked: {
    icon: BlockOutlined,
    border: "border-red-200",
    bg: "from-red-50/80 to-white",
    iconBg: "bg-red-100",
    iconColor: "text-red-600",
    titleColor: "text-red-900",
    label: "Blocked",
  },
};

const CHECK_LABELS: Record<string, string> = {
  input_length: "Input Length",
  injection_detection: "Prompt Injection",
  pii_detection: "PII Detection",
  output_safety: "Output Safety",
  output_length: "Output Length",
  json_format: "Response Format",
  hallucination: "Hallucination Check",
  action_permission: "Action Permission",
  batch_cap: "Batch Limit",
  email_rate: "Email Rate Limit",
  status_change_rate: "Status Change Rate",
  llm_cost: "LLM Cost Limit",
};

export default function GuardrailWarning({ block, onSendPrompt }: Props) {
  const config = SEVERITY_CONFIG[block.severity] || SEVERITY_CONFIG.warning;
  const SeverityIcon = config.icon;

  return (
    <div className={`rounded-xl border ${config.border} bg-gradient-to-br ${config.bg} p-4`}>
      {/* Header */}
      <div className="mb-2 flex items-center gap-2">
        <div className={`flex h-5 w-5 items-center justify-center rounded-full ${config.iconBg}`}>
          <ShieldOutlined sx={{ fontSize: 12 }} className={config.iconColor} />
        </div>
        <span className={`text-sm font-semibold ${config.titleColor}`}>
          {CHECK_LABELS[block.check_name] || block.check_name}
        </span>
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${config.iconBg} ${config.iconColor}`}>
          <SeverityIcon sx={{ fontSize: 10 }} />
          {config.label}
        </span>
      </div>

      {/* Message */}
      <p className="mb-2 text-xs leading-relaxed text-gray-700">{block.message}</p>

      {/* Details */}
      {block.details && (
        <div className={`mb-2 rounded-lg border ${config.border} bg-white px-3 py-2`}>
          <p className="text-[11px] leading-relaxed text-gray-600">{block.details}</p>
        </div>
      )}

      {/* Suggestions */}
      {block.suggestions && block.suggestions.length > 0 && (
        <div className="mb-2">
          <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-gray-500">
            <LightbulbOutlined sx={{ fontSize: 10 }} />
            Suggestions
          </div>
          <ul className="space-y-0.5">
            {block.suggestions.map((s, i) => (
              <li key={i} className="text-[11px] leading-relaxed text-gray-600">
                <span className="mr-1 text-gray-400">-</span>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions for blocked */}
      {block.severity === "blocked" && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => onSendPrompt("Let me rephrase my request")}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            Rephrase
          </button>
        </div>
      )}
    </div>
  );
}
