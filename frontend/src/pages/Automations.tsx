import { useCallback, useState } from "react";
import {
  Zap,
  Play,
  Pencil,
  Trash2,
  Plus,
  X,
  Sparkles,
  Mail,
  Reply,
  Trash,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  listAutomationRules,
  listAutomationLogs,
  getSchedulerStatus,
  toggleAutomationRule,
  runAutomationRule,
  deleteAutomationRule,
  createAutomationRule,
  updateAutomationRule,
} from "../lib/api";
import type {
  AutomationRule,
  AutomationRuleType,
  AutomationLog,
} from "../types";

const RULE_TYPE_META: Record<
  AutomationRuleType,
  { label: string; icon: typeof Sparkles; color: string }
> = {
  auto_match: { label: "Auto-Match", icon: Sparkles, color: "blue" },
  inbox_scan: { label: "Inbox Scanner", icon: Mail, color: "green" },
  auto_followup: { label: "Auto Follow-Up", icon: Reply, color: "amber" },
  pipeline_cleanup: { label: "Pipeline Cleanup", icon: Trash, color: "red" },
};

function describeSchedule(rule: AutomationRule): string {
  try {
    const s = JSON.parse(rule.schedule_value || "{}");
    if (rule.trigger_type === "interval") {
      const parts: string[] = [];
      if (s.days) parts.push(`${s.days}d`);
      if (s.hours) parts.push(`${s.hours}h`);
      if (s.minutes) parts.push(`${s.minutes}m`);
      return parts.length ? `Every ${parts.join(" ")}` : "Every 30m";
    }
    if (rule.trigger_type === "cron") {
      const parts: string[] = [];
      if (s.day_of_week) parts.push(s.day_of_week);
      const h = s.hour ?? 9;
      const m = s.minute ?? 0;
      parts.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
      return parts.join(" at ");
    }
  } catch {
    /* ignore */
  }
  return rule.trigger_type;
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function Automations() {
  const {
    data: rules,
    refresh: refreshRules,
  } = useApi(useCallback(() => listAutomationRules(), []));
  const {
    data: logs,
    refresh: refreshLogs,
  } = useApi(useCallback(() => listAutomationLogs(undefined, 50), []));
  const { data: status } = useApi(
    useCallback(() => getSchedulerStatus(), [])
  );

  const [runningId, setRunningId] = useState<string | null>(null);
  const [editRule, setEditRule] = useState<AutomationRule | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const handleToggle = async (id: string) => {
    await toggleAutomationRule(id);
    refreshRules();
  };

  const handleRunNow = async (id: string) => {
    setRunningId(id);
    try {
      await runAutomationRule(id);
      refreshRules();
      refreshLogs();
    } finally {
      setRunningId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this automation rule?")) return;
    await deleteAutomationRule(id);
    refreshRules();
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Scheduler Status */}
      <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-5 py-3">
        <Zap className="h-5 w-5 text-amber-500" />
        <span className="font-semibold text-sm">Background Scheduler</span>
        <span
          className={`ml-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
            status?.running
              ? "bg-green-100 text-green-700"
              : "bg-gray-100 text-gray-500"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              status?.running ? "bg-green-500" : "bg-gray-400"
            }`}
          />
          {status?.running ? "Running" : "Stopped"}
        </span>
        <span className="ml-auto text-xs text-gray-500">
          {status?.active_jobs ?? 0} active jobs
        </span>
      </div>

      {/* Rules */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">Automation Rules</h3>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" /> Add Rule
          </button>
        </div>

        {!rules || rules.length === 0 ? (
          <p className="text-sm text-gray-400">No automation rules yet.</p>
        ) : (
          <div className="space-y-3">
            {rules.map((rule) => {
              const meta = RULE_TYPE_META[rule.rule_type] ?? RULE_TYPE_META.auto_match;
              const Icon = meta.icon;
              return (
                <div
                  key={rule.id}
                  className="flex items-center gap-3 rounded-lg border border-gray-100 p-3"
                >
                  <Icon className={`h-5 w-5 text-${meta.color}-500 shrink-0`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">
                        {rule.name}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium bg-${meta.color}-100 text-${meta.color}-700`}
                      >
                        {meta.label}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-400">
                      <span>{describeSchedule(rule)}</span>
                      <span>Runs: {rule.run_count}</span>
                      {rule.error_count > 0 && (
                        <span className="text-red-400">
                          Errors: {rule.error_count}
                        </span>
                      )}
                      <span>Last: {formatRelativeTime(rule.last_run_at)}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <button
                    onClick={() => handleRunNow(rule.id)}
                    disabled={runningId === rule.id}
                    title="Run Now"
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
                  >
                    {runningId === rule.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={() => setEditRule(rule)}
                    title="Edit"
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(rule.id)}
                    title="Delete"
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-red-500"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                  {/* Toggle */}
                  <button
                    onClick={() => handleToggle(rule.id)}
                    className={`relative h-6 w-11 rounded-full transition-colors ${
                      rule.enabled ? "bg-blue-600" : "bg-gray-300"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                        rule.enabled ? "translate-x-5" : ""
                      }`}
                    />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Execution Logs */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <h3 className="mb-4 font-semibold">Execution History</h3>
        {!logs || logs.length === 0 ? (
          <p className="text-sm text-gray-400">
            No executions yet. Enable a rule or click "Run Now".
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-medium text-gray-500">
                  <th className="pb-2 pr-3">Time</th>
                  <th className="pb-2 pr-3">Rule</th>
                  <th className="pb-2 pr-3">Status</th>
                  <th className="pb-2 pr-3">Duration</th>
                  <th className="pb-2">Summary</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <LogRow key={log.id} log={log} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create / Edit Modal */}
      {(showCreate || editRule) && (
        <RuleModal
          rule={editRule}
          onClose={() => {
            setShowCreate(false);
            setEditRule(null);
          }}
          onSaved={() => {
            setShowCreate(false);
            setEditRule(null);
            refreshRules();
          }}
        />
      )}
    </div>
  );
}

function LogRow({ log }: { log: AutomationLog }) {
  const statusIcon = {
    success: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
    error: <XCircle className="h-3.5 w-3.5 text-red-500" />,
    running: <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />,
    skipped: <Clock className="h-3.5 w-3.5 text-gray-400" />,
  }[log.status];

  return (
    <tr className="border-b border-gray-50">
      <td className="py-2 pr-3 text-xs text-gray-500 whitespace-nowrap">
        {formatRelativeTime(log.started_at)}
      </td>
      <td className="py-2 pr-3 font-medium whitespace-nowrap">
        {log.rule_name || log.rule_id}
      </td>
      <td className="py-2 pr-3">
        <span className="inline-flex items-center gap-1">
          {statusIcon}
          <span className="text-xs">{log.status}</span>
        </span>
      </td>
      <td className="py-2 pr-3 text-xs text-gray-500 whitespace-nowrap">
        {log.duration_ms > 0 ? `${(log.duration_ms / 1000).toFixed(1)}s` : "-"}
      </td>
      <td className="py-2 text-xs text-gray-600 max-w-xs truncate">
        {log.error_message || log.summary || "-"}
      </td>
    </tr>
  );
}

/* ── Rule Create / Edit Modal ────────────────────────────────────────── */

function RuleModal({
  rule,
  onClose,
  onSaved,
}: {
  rule: AutomationRule | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!rule;
  const [name, setName] = useState(rule?.name ?? "");
  const [description, setDescription] = useState(rule?.description ?? "");
  const [ruleType, setRuleType] = useState<AutomationRuleType>(
    rule?.rule_type ?? "auto_match"
  );
  const [triggerType, setTriggerType] = useState(
    rule?.trigger_type ?? "interval"
  );
  const [scheduleValue, setScheduleValue] = useState(
    rule?.schedule_value ?? '{"minutes":30}'
  );
  const [conditionsJson, setConditionsJson] = useState(
    rule?.conditions_json ?? "{}"
  );
  const [actionsJson, setActionsJson] = useState(rule?.actions_json ?? "{}");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isEdit && rule) {
        await updateAutomationRule(rule.id, {
          name,
          description,
          trigger_type: triggerType as "interval" | "cron",
          schedule_value: scheduleValue,
          conditions_json: conditionsJson,
          actions_json: actionsJson,
        });
      } else {
        await createAutomationRule({
          name,
          description,
          rule_type: ruleType,
          trigger_type: triggerType,
          schedule_value: scheduleValue,
          conditions_json: conditionsJson,
          actions_json: actionsJson,
          enabled: false,
        });
      }
      onSaved();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">
            {isEdit ? "Edit Rule" : "Create Rule"}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3">
          <Field label="Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Auto-Match New Candidates"
              className="input"
            />
          </Field>
          <Field label="Description">
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this rule do?"
              className="input"
            />
          </Field>
          {!isEdit && (
            <Field label="Rule Type">
              <select
                value={ruleType}
                onChange={(e) =>
                  setRuleType(e.target.value as AutomationRuleType)
                }
                className="input"
              >
                <option value="auto_match">Auto-Match</option>
                <option value="inbox_scan">Inbox Scanner</option>
                <option value="auto_followup">Auto Follow-Up</option>
                <option value="pipeline_cleanup">Pipeline Cleanup</option>
              </select>
            </Field>
          )}
          <Field label="Trigger Type">
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as "interval" | "cron")}
              className="input"
            >
              <option value="interval">Interval</option>
              <option value="cron">Cron</option>
            </select>
          </Field>
          <Field label="Schedule (JSON)">
            <input
              value={scheduleValue}
              onChange={(e) => setScheduleValue(e.target.value)}
              placeholder='e.g. {"minutes":30} or {"hour":9,"minute":0}'
              className="input font-mono text-xs"
            />
            <p className="mt-1 text-[10px] text-gray-400">
              Interval: {`{"minutes":30}`} | Cron: {`{"hour":9,"minute":0,"day_of_week":"mon"}`}
            </p>
          </Field>
          <Field label="Conditions (JSON)">
            <textarea
              value={conditionsJson}
              onChange={(e) => setConditionsJson(e.target.value)}
              rows={2}
              className="input font-mono text-xs"
            />
          </Field>
          <Field label="Actions (JSON)">
            <textarea
              value={actionsJson}
              onChange={(e) => setActionsJson(e.target.value)}
              rows={2}
              className="input font-mono text-xs"
            />
          </Field>
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : isEdit ? "Update" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-gray-700">
        {label}
      </label>
      {children}
    </div>
  );
}
