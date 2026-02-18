import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  BoltOutlined,
  PlayArrowOutlined,
  EditOutlined,
  DeleteOutline,
  AddOutlined,
  CloseOutlined,
  AutoAwesomeOutlined,
  MailOutline,
  ReplyOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CancelOutlined,
  AccessTimeOutlined,
} from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
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

const RULE_TYPE_ICONS: Record<
  AutomationRuleType,
  { icon: React.ElementType; color: string }
> = {
  auto_match: { icon: AutoAwesomeOutlined, color: "blue" },
  inbox_scan: { icon: MailOutline, color: "green" },
  auto_followup: { icon: ReplyOutlined, color: "amber" },
  pipeline_cleanup: { icon: DeleteOutlined, color: "red" },
};

function describeSchedule(
  rule: AutomationRule,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  try {
    const s = JSON.parse(rule.schedule_value || "{}");
    if (rule.trigger_type === "interval") {
      const parts: string[] = [];
      if (s.days) parts.push(`${s.days}d`);
      if (s.hours) parts.push(`${s.hours}h`);
      if (s.minutes) parts.push(`${s.minutes}m`);
      return parts.length ? t("automations.every", { schedule: parts.join(" ") }) : t("automations.every", { schedule: "30m" });
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

function formatRelativeTime(
  iso: string | null,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (!iso) return t("common.never");
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return t("common.justNow");
  if (mins < 60) return t("common.minutesAgo", { count: mins });
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return t("common.hoursAgo", { count: hrs });
  const days = Math.floor(hrs / 24);
  return t("common.daysAgo", { count: days });
}

export default function Automations() {
  const { t } = useTranslation();
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

  const RULE_TYPE_LABELS: Record<AutomationRuleType, string> = {
    auto_match: t("automations.ruleTypes.auto_match"),
    inbox_scan: t("automations.ruleTypes.inbox_scan"),
    auto_followup: t("automations.ruleTypes.auto_followup"),
    pipeline_cleanup: t("automations.ruleTypes.pipeline_cleanup"),
  };

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
    if (!confirm(t("automations.confirmDelete"))) return;
    await deleteAutomationRule(id);
    refreshRules();
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Scheduler Status */}
      <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-5 py-3">
        <BoltOutlined className="h-5 w-5 text-amber-500" />
        <span className="font-semibold text-sm">{t("automations.backgroundScheduler")}</span>
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
          {status?.running ? t("automations.running") : t("automations.stopped")}
        </span>
        <span className="ml-auto text-xs text-gray-500">
          {t("automations.activeJobs", { count: status?.active_jobs ?? 0 })}
        </span>
      </div>

      {/* Rules */}
      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">{t("automations.automationRules")}</h3>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            <AddOutlined className="h-3.5 w-3.5" /> {t("automations.addRule")}
          </button>
        </div>

        {!rules || rules.length === 0 ? (
          <p className="text-sm text-gray-400">{t("automations.noRules")}</p>
        ) : (
          <div className="space-y-3">
            {rules.map((rule) => {
              const meta = RULE_TYPE_ICONS[rule.rule_type] ?? RULE_TYPE_ICONS.auto_match;
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
                        {RULE_TYPE_LABELS[rule.rule_type]}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-400">
                      <span>{describeSchedule(rule, t)}</span>
                      <span>{t("automations.runs", { count: rule.run_count })}</span>
                      {rule.error_count > 0 && (
                        <span className="text-red-400">
                          {t("automations.errors", { count: rule.error_count })}
                        </span>
                      )}
                      <span>{t("automations.last", { time: formatRelativeTime(rule.last_run_at, t) })}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <button
                    onClick={() => handleRunNow(rule.id)}
                    disabled={runningId === rule.id}
                    title={t("automations.runNow")}
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50"
                  >
                    {runningId === rule.id ? (
                      <CircularProgress size={16} />
                    ) : (
                      <PlayArrowOutlined className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    onClick={() => setEditRule(rule)}
                    title={t("common.edit")}
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  >
                    <EditOutlined className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(rule.id)}
                    title={t("common.delete")}
                    className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-red-500"
                  >
                    <DeleteOutline className="h-4 w-4" />
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
        <h3 className="mb-4 font-semibold">{t("automations.executionHistory")}</h3>
        {!logs || logs.length === 0 ? (
          <p className="text-sm text-gray-400">
            {t("automations.noExecutions")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs font-medium text-gray-500">
                  <th className="pb-2 pr-3">{t("automations.time")}</th>
                  <th className="pb-2 pr-3">{t("automations.rule")}</th>
                  <th className="pb-2 pr-3">{t("automations.status")}</th>
                  <th className="pb-2 pr-3">{t("automations.duration")}</th>
                  <th className="pb-2">{t("automations.summary")}</th>
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
  const { t } = useTranslation();
  const statusIcon = {
    success: <CheckCircleOutlined className="h-3.5 w-3.5 text-green-500" />,
    error: <CancelOutlined className="h-3.5 w-3.5 text-red-500" />,
    running: <CircularProgress size={14} />,
    skipped: <AccessTimeOutlined className="h-3.5 w-3.5 text-gray-400" />,
  }[log.status];

  return (
    <tr className="border-b border-gray-50">
      <td className="py-2 pr-3 text-xs text-gray-500 whitespace-nowrap">
        {formatRelativeTime(log.started_at, t)}
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

/* -- Rule Create / Edit Modal ----------------------------------------------- */

function RuleModal({
  rule,
  onClose,
  onSaved,
}: {
  rule: AutomationRule | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
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
            {isEdit ? t("automations.editRule") : t("automations.createRule")}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <CloseOutlined className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3">
          <Field label={t("automations.name")}>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("automations.namePlaceholder")}
              className="input"
            />
          </Field>
          <Field label={t("automations.description")}>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("automations.descriptionPlaceholder")}
              className="input"
            />
          </Field>
          {!isEdit && (
            <Field label={t("automations.ruleType")}>
              <select
                value={ruleType}
                onChange={(e) =>
                  setRuleType(e.target.value as AutomationRuleType)
                }
                className="input"
              >
                <option value="auto_match">{t("automations.ruleTypes.auto_match")}</option>
                <option value="inbox_scan">{t("automations.ruleTypes.inbox_scan")}</option>
                <option value="auto_followup">{t("automations.ruleTypes.auto_followup")}</option>
                <option value="pipeline_cleanup">{t("automations.ruleTypes.pipeline_cleanup")}</option>
              </select>
            </Field>
          )}
          <Field label={t("automations.triggerType")}>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value as "interval" | "cron")}
              className="input"
            >
              <option value="interval">{t("automations.interval")}</option>
              <option value="cron">{t("automations.cron")}</option>
            </select>
          </Field>
          <Field label={t("automations.scheduleJson")}>
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
          <Field label={t("automations.conditionsJson")}>
            <textarea
              value={conditionsJson}
              onChange={(e) => setConditionsJson(e.target.value)}
              rows={2}
              className="input font-mono text-xs"
            />
          </Field>
          <Field label={t("automations.actionsJson")}>
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
            {t("common.cancel")}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !name}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? t("common.saving") : isEdit ? t("automations.update") : t("automations.create")}
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
