import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  CloseOutlined,
  PeopleOutlined,
  WorkOutline,
  CalendarTodayOutlined,
  MailOutline,
  LocationOnOutlined,
  BusinessOutlined,
  Star as StarIcon,
  AccessTimeOutlined,
  ChevronRightOutlined,
  DescriptionOutlined,
  TrendingUpOutlined,
  WarningAmberOutlined,
  NotificationsOutlined,
  AutoAwesomeOutlined,
  ArrowForwardOutlined,
  PersonOutlined,
} from "@mui/icons-material";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  useDroppable,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { useApi } from "../hooks/useApi";
import {
  getCandidate, getJob, listCandidates, listEmails, listEvents, listJobs,
  getNotifications, updateCandidate, listPipelineEntries, updatePipelineStatus,
} from "../lib/api";
import type { Candidate, CandidateStatus, ContextView, CalendarEvent, Notification, PipelineEntry, PipelineViewMode } from "../types";
import { PIPELINE_COLUMNS } from "../types";
import DraggableCandidateCard from "./DraggableCandidateCard";

interface Props {
  view: ContextView | null;
  onClose: () => void;
  onViewCandidate: (id: string) => void;
  onViewJob: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}

export default function ContextPanel({ view, onClose, onViewCandidate, onViewJob, onSendPrompt }: Props) {
  const { t } = useTranslation();
  if (!view) return null;

  return (
    <div className="flex w-80 flex-col rounded-xl border border-gray-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-800">
          {view.type === "briefing" && t("contextPanel.dailyBriefing")}
          {view.type === "candidate" && t("contextPanel.candidate")}
          {view.type === "job" && t("contextPanel.jobDetails")}
          {view.type === "pipeline_stage" && t("contextPanel.pipelineStage")}
          {view.type === "events" && t("contextPanel.upcomingEvents")}
          {view.type === "comparison" && t("contextPanel.compareCandidates")}
        </h3>
        <button
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <CloseOutlined sx={{ fontSize: 16 }} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {view.type === "briefing" && (
          <BriefingView onViewCandidate={onViewCandidate} onSendPrompt={onSendPrompt} />
        )}
        {view.type === "candidate" && (
          <CandidateView id={view.id} onViewJob={onViewJob} onSendPrompt={onSendPrompt} />
        )}
        {view.type === "job" && (
          <JobView id={view.id} onViewCandidate={onViewCandidate} onSendPrompt={onSendPrompt} />
        )}
        {view.type === "pipeline_stage" && (
          <PipelineStageView stage={view.stage} viewMode={view.viewMode} onViewCandidate={onViewCandidate} onViewJob={onViewJob} onSendPrompt={onSendPrompt} />
        )}
        {view.type === "events" && (
          <EventsView onSendPrompt={onSendPrompt} />
        )}
        {view.type === "comparison" && (
          <ComparisonView candidateIds={view.candidate_ids} onViewCandidate={onViewCandidate} onSendPrompt={onSendPrompt} />
        )}
      </div>
    </div>
  );
}

/* ── Briefing View ───────────────────────────────────────────────────────── */

function BriefingView({
  onViewCandidate,
  onSendPrompt,
}: {
  onViewCandidate: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}) {
  const { t } = useTranslation();
  const { data: candidates } = useApi(useCallback(() => listCandidates(), []));
  const { data: emails } = useApi(useCallback(() => listEmails(), []));
  const { data: events } = useApi(useCallback(() => listEvents(), []));
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Fetch notifications with polling every 60s
  useEffect(() => {
    let mounted = true;
    const fetchNotifs = () => {
      getNotifications()
        .then((n) => { if (mounted) setNotifications(n); })
        .catch(() => {});
    };
    fetchNotifs();
    const interval = setInterval(fetchNotifs, 60000);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const stats = useMemo(() => {
    if (!candidates) return null;
    const newCount = candidates.filter((c) => c.status === "new").length;
    const contacted = candidates.filter((c) => c.status === "contacted");
    const pendingEmails = (emails || []).filter((e) => !e.sent && !e.approved);
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayEvents = (events || []).filter((e) => e.start_time?.startsWith(todayStr));
    const interviews = candidates.filter((c) => c.status === "interview_scheduled");
    return { newCount, contacted, pendingEmails, todayEvents, interviews, total: candidates.length, jobCount: (jobs || []).length };
  }, [candidates, emails, events, jobs]);

  if (!stats) return <LoadingDots />;

  return (
    <div className="space-y-4">
      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2">
        <StatCard icon={<PeopleOutlined sx={{ fontSize: 16 }} />} label={t("contextPanel.candidates")} value={stats.total} color="blue" />
        <StatCard icon={<WorkOutline sx={{ fontSize: 16 }} />} label={t("contextPanel.activeJobs")} value={stats.jobCount} color="purple" />
        <StatCard icon={<MailOutline sx={{ fontSize: 16 }} />} label={t("contextPanel.pendingEmails")} value={stats.pendingEmails.length} color="amber" />
        <StatCard icon={<CalendarTodayOutlined sx={{ fontSize: 16 }} />} label={t("contextPanel.todaysEvents")} value={stats.todayEvents.length} color="green" />
      </div>

      {/* Proactive Notifications */}
      {notifications.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <NotificationsOutlined sx={{ fontSize: 14 }} /> {t("contextPanel.alerts", { count: notifications.length })}
          </h4>
          <div className="space-y-1.5">
            {notifications.slice(0, 5).map((n) => (
              <NotificationCard key={n.id} notification={n} onAction={onSendPrompt} onViewCandidate={onViewCandidate} />
            ))}
          </div>
        </div>
      )}

      {/* Awaiting reply */}
      {stats.contacted.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <AccessTimeOutlined sx={{ fontSize: 14 }} /> {t("contextPanel.awaitingReply", { count: stats.contacted.length })}
          </h4>
          <div className="space-y-1.5">
            {stats.contacted.slice(0, 5).map((c) => (
              <button
                key={c.id}
                onClick={() => onViewCandidate(c.id)}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-gray-50"
              >
                <span className="h-2 w-2 rounded-full bg-blue-400" />
                <span className="flex-1 truncate font-medium text-gray-700">{c.name}</span>
                <span className="text-xs text-gray-400">{c.current_title || ""}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Today's events */}
      {stats.todayEvents.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <CalendarTodayOutlined sx={{ fontSize: 14 }} /> {t("contextPanel.today")}
          </h4>
          <div className="space-y-1.5">
            {stats.todayEvents.map((e: CalendarEvent) => (
              <div key={e.id} className="rounded-lg border border-gray-100 px-3 py-2">
                <p className="text-sm font-medium text-gray-700">{e.title}</p>
                <p className="text-xs text-gray-400">
                  {e.start_time?.slice(11, 16)} {e.candidate_name && `• ${e.candidate_name}`}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* New candidates */}
      {stats.newCount > 0 && (
        <button
          onClick={() => onSendPrompt("Review the new candidates in the pipeline")}
          className="flex w-full items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700 hover:bg-blue-100"
        >
          <TrendingUpOutlined sx={{ fontSize: 16 }} />
          {t("contextPanel.newCandidatesToReview", { count: stats.newCount })}
          <ChevronRightOutlined className="ml-auto" sx={{ fontSize: 16 }} />
        </button>
      )}
    </div>
  );
}

/* ── Candidate View ──────────────────────────────────────────────────────── */

function CandidateView({
  id,
  onViewJob,
  onSendPrompt,
}: {
  id: string;
  onViewJob: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}) {
  const { t } = useTranslation();
  const { data: candidate } = useApi(useCallback(() => getCandidate(id), [id]));
  const { data: emails } = useApi(useCallback(() => listEmails(id), [id]));

  if (!candidate) return <LoadingDots />;

  const statusColor = STATUS_COLORS[candidate.status] || "bg-gray-100 text-gray-700";

  return (
    <div className="space-y-4">
      {/* Profile header */}
      <div>
        <h4 className="text-base font-semibold text-gray-900">{candidate.name}</h4>
        {candidate.current_title && (
          <p className="text-sm text-gray-500">
            {candidate.current_title}
            {candidate.current_company && ` ${t("contextPanel.atCompany", { company: candidate.current_company })}`}
          </p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}>
            {candidate.status.replace("_", " ")}
          </span>
          {candidate.match_score > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <StarIcon sx={{ fontSize: 12 }} />
              {t("contextPanel.matchPercent", { percent: Math.round(candidate.match_score * 100) })}
            </span>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="space-y-1.5 text-sm">
        {candidate.email && (
          <div className="flex items-center gap-2 text-gray-600">
            <MailOutline className="text-gray-400" sx={{ fontSize: 14 }} /> {candidate.email}
          </div>
        )}
        {candidate.location && (
          <div className="flex items-center gap-2 text-gray-600">
            <LocationOnOutlined className="text-gray-400" sx={{ fontSize: 14 }} /> {candidate.location}
          </div>
        )}
        {candidate.experience_years != null && (
          <div className="flex items-center gap-2 text-gray-600">
            <BusinessOutlined className="text-gray-400" sx={{ fontSize: 14 }} /> {t("contextPanel.yearsPlus", { years: candidate.experience_years })}
          </div>
        )}
      </div>

      {/* Skills */}
      {candidate.skills.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {candidate.skills.slice(0, 8).map((s) => (
            <span key={s} className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">
              {s}
            </span>
          ))}
          {candidate.skills.length > 8 && (
            <span className="text-xs text-gray-400">+{candidate.skills.length - 8}</span>
          )}
        </div>
      )}

      {/* Resume summary */}
      {candidate.resume_summary && (
        <div>
          <h5 className="mb-1 flex items-center gap-1 text-xs font-semibold text-gray-500">
            <DescriptionOutlined sx={{ fontSize: 12 }} /> {t("contextPanel.resumeSummary")}
          </h5>
          <p className="text-xs leading-relaxed text-gray-600">{candidate.resume_summary}</p>
        </div>
      )}

      {/* Top jobs */}
      {candidate.top_jobs && candidate.top_jobs.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.topMatchingJobs")}</h5>
          <div className="space-y-1">
            {candidate.top_jobs.slice(0, 3).map((tj) => (
              <button
                key={tj.job_id}
                onClick={() => onViewJob(tj.job_id)}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-gray-50"
              >
                <span className="flex-1 truncate font-medium text-gray-700">
                  {tj.title} — {tj.company}
                </span>
                <span className={`font-semibold ${tj.score >= 0.7 ? "text-green-600" : tj.score >= 0.4 ? "text-amber-600" : "text-red-500"}`}>
                  {Math.round(tj.score * 100)}%
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Recent emails */}
      {emails && emails.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">
            {t("contextPanel.emailHistory", { count: emails.length })}
          </h5>
          <div className="space-y-1">
            {emails.slice(0, 3).map((e) => (
              <div key={e.id} className="rounded border border-gray-100 px-2 py-1.5">
                <p className="truncate text-xs font-medium text-gray-700">{e.subject}</p>
                <p className="text-[10px] text-gray-400">
                  {e.sent ? t("contextPanel.sent") : e.approved ? t("contextPanel.approved") : t("contextPanel.draft")} • {e.email_type}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="space-y-2 border-t border-gray-100 pt-3">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onSendPrompt(`Draft an outreach email to ${candidate.name}`)}
            className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
          >
            {t("contextPanel.draftEmail")}
          </button>
          <button
            onClick={() => onSendPrompt(`What jobs match ${candidate.name}?`)}
            className="rounded-lg bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"
          >
            {t("contextPanel.matchJobs")}
          </button>
        </div>

        <StageSelector
          currentStatus={candidate.status}
          onSelect={(stage) =>
            onSendPrompt(`Move ${candidate.name} to the ${stage.replace("_", " ")} stage`)
          }
        />

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onSendPrompt(`Schedule an interview with ${candidate.name}`)}
            className="rounded-lg bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100"
          >
            {t("contextPanel.scheduleInterview")}
          </button>
          <button
            onClick={() => onSendPrompt(`Show the match report for ${candidate.name}`)}
            className="rounded-lg bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
          >
            {t("contextPanel.matchReport")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Stage Selector ──────────────────────────────────────────────────────── */

function StageSelector({
  currentStatus,
  onSelect,
}: {
  currentStatus: string;
  onSelect: (stage: string) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const stages = PIPELINE_COLUMNS.filter((p) => p.key !== currentStatus);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
      >
        <span className="flex items-center gap-1.5">
          <ArrowForwardOutlined sx={{ fontSize: 12 }} />
          {t("contextPanel.moveToStage")}
        </span>
        <ChevronRightOutlined className={`transition-transform ${open ? "rotate-90" : ""}`} sx={{ fontSize: 12 }} />
      </button>
      {open && (
        <div className="absolute left-0 right-0 z-10 mt-1 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
          {stages.map((s) => (
            <button
              key={s.key}
              onClick={() => { onSelect(s.key); setOpen(false); }}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${STATUS_COLORS[s.key]?.split(" ")[0] || "bg-gray-300"}`} />
              {t(s.labelKey)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Job View ────────────────────────────────────────────────────────────── */

function JobView({
  id,
  onViewCandidate,
  onSendPrompt,
}: {
  id: string;
  onViewCandidate: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}) {
  const { t } = useTranslation();
  const { data: job } = useApi(useCallback(() => getJob(id), [id]));
  const { data: allCandidates } = useApi(useCallback(() => listCandidates(), []));

  const jobCandidates = useMemo(
    () => (allCandidates || []).filter((c) => c.job_id === id),
    [allCandidates, id]
  );

  if (!job) return <LoadingDots />;

  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-base font-semibold text-gray-900">{job.title}</h4>
        <p className="text-sm text-gray-500">{job.company}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-gray-500">
          {job.location && (
            <span className="flex items-center gap-1"><LocationOnOutlined sx={{ fontSize: 12 }} /> {job.location}</span>
          )}
          {job.remote && <span className="rounded bg-green-50 px-1.5 py-0.5 text-green-700">{t("contextPanel.remote")}</span>}
          {job.salary_range && <span>{job.salary_range}</span>}
        </div>
      </div>

      {/* Skills */}
      {job.required_skills.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.requiredSkills")}</h5>
          <div className="flex flex-wrap gap-1">
            {job.required_skills.map((s) => (
              <span key={s} className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Summary */}
      {job.summary && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.summary")}</h5>
          <p className="text-xs leading-relaxed text-gray-600">{job.summary}</p>
        </div>
      )}

      {/* Candidates */}
      <div>
        <h5 className="mb-1 text-xs font-semibold text-gray-500">
          {t("contextPanel.candidatesCount", { count: jobCandidates.length })}
        </h5>
        {jobCandidates.length > 0 ? (
          <div className="space-y-1">
            {jobCandidates.slice(0, 6).map((c) => (
              <button
                key={c.id}
                onClick={() => onViewCandidate(c.id)}
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-gray-50"
              >
                <span className="flex-1 truncate font-medium text-gray-700">{c.name}</span>
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${STATUS_COLORS[c.status] || ""}`}>
                  {c.status.replace("_", " ")}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">{t("contextPanel.noCandidatesYet")}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
        <button
          onClick={() => onSendPrompt(`Upload a resume for the ${job.title} position`)}
          className="rounded-lg bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"
        >
          {t("contextPanel.uploadResume")}
        </button>
        <button
          onClick={() => onSendPrompt(`Find top candidates for the ${job.title} role`)}
          className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
        >
          {t("contextPanel.findCandidates")}
        </button>
        <button
          onClick={() => onSendPrompt(`Generate a summary for the ${job.title} job description`)}
          className="rounded-lg bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100"
        >
          {t("contextPanel.jdSummary")}
        </button>
      </div>
    </div>
  );
}

/* ── Pipeline Stage View (with Drag-and-Drop) ────────────────────────────── */

function StageDropTarget({ stageKey, label }: { stageKey: string; label: string }) {
  const { isOver, setNodeRef } = useDroppable({ id: stageKey });

  return (
    <div
      ref={setNodeRef}
      className={`rounded-lg border-2 border-dashed px-3 py-2 text-center text-xs font-medium transition-colors ${
        isOver
          ? "border-blue-400 bg-blue-50 text-blue-700"
          : "border-gray-200 text-gray-400 hover:border-gray-300"
      }`}
    >
      {label}
    </div>
  );
}

function PipelineStageView({
  stage,
  viewMode,
  onViewCandidate,
  onViewJob,
  onSendPrompt,
}: {
  stage: CandidateStatus;
  viewMode?: PipelineViewMode;
  onViewCandidate: (id: string) => void;
  onViewJob: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}) {
  const { data: allCandidates, refresh: refreshCandidates } = useApi(useCallback(() => listCandidates(), []));
  const { data: pipelineEntries, refresh: refreshPipeline } = useApi(useCallback(() => listPipelineEntries(), []));
  const [activeDragId, setActiveDragId] = useState<string | null>(null);
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set());

  const refresh = () => { refreshCandidates(); refreshPipeline(); };

  // Use pipeline entries (per-job) if available, fall back to candidates
  // Filter out placeholder entries (jobs with no candidates) in candidate view
  const stageEntries = useMemo(
    () => (pipelineEntries || []).filter((e: PipelineEntry) =>
      e.pipeline_status === stage && (viewMode === "jobs" || e.candidate_id)
    ),
    [pipelineEntries, stage, viewMode]
  );

  const stageCandidates = useMemo(
    () => (allCandidates || []).filter((c) => c.status === stage),
    [allCandidates, stage]
  );

  // Prefer pipeline entries, fall back to candidates if no entries exist at all
  const hasPipelineEntries = pipelineEntries && pipelineEntries.length > 0;

  // Jobs view: group entries by job
  const jobGroups = useMemo(() => {
    if (viewMode !== "jobs" || !hasPipelineEntries) return [];
    const map = new Map<string, { job_id: string; job_title: string; job_company: string; candidates: PipelineEntry[] }>();
    for (const entry of stageEntries) {
      if (!map.has(entry.job_id)) {
        map.set(entry.job_id, {
          job_id: entry.job_id,
          job_title: entry.job_title,
          job_company: entry.job_company,
          candidates: [],
        });
      }
      // Skip placeholder entries (jobs with no candidates yet)
      if (entry.candidate_id) {
        map.get(entry.job_id)!.candidates.push(entry);
      }
    }
    return Array.from(map.values());
  }, [viewMode, hasPipelineEntries, stageEntries]);

  const displayCount = viewMode === "jobs" && hasPipelineEntries
    ? jobGroups.length
    : hasPipelineEntries ? stageEntries.length : stageCandidates.length;

  const { t } = useTranslation();
  const stageLabel = PIPELINE_COLUMNS.find((p) => p.key === stage)?.labelKey
    ? t(PIPELINE_COLUMNS.find((p) => p.key === stage)!.labelKey)
    : stage;
  const targetStages = PIPELINE_COLUMNS.filter((p) => p.key !== stage);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const activeDragEntry = useMemo(
    () => hasPipelineEntries
      ? stageEntries.find((e: PipelineEntry) => `${e.candidate_id}:${e.job_id}` === activeDragId)
      : null,
    [stageEntries, activeDragId, hasPipelineEntries]
  );

  const activeDragCandidate = useMemo(
    () => stageCandidates.find((c) => c.id === activeDragId),
    [stageCandidates, activeDragId]
  );

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveDragId(null);
    const { active, over } = event;
    if (!over) return;

    const targetStage = over.id as string;
    const dragId = active.id as string;
    if (targetStage === stage) return;

    // Pipeline entry drag (candidate:job pair)
    if (hasPipelineEntries && dragId.includes(":")) {
      const [candidateId, jobId] = dragId.split(":");
      const entry = stageEntries.find((e: PipelineEntry) => e.candidate_id === candidateId && e.job_id === jobId);
      if (!entry) return;
      try {
        await updatePipelineStatus(candidateId, jobId, targetStage);
        refresh();
      } catch { /* feedback handled by chat */ }
      const name = entry.candidate_name;
      if (targetStage === "contacted") {
        onSendPrompt(`I moved ${name} to Contacted. Draft an outreach email for ${name}?`);
      } else if (targetStage === "interview_scheduled") {
        onSendPrompt(`I moved ${name} to Interview Scheduled. When should I schedule the interview with ${name}?`);
      } else if (targetStage === "rejected") {
        onSendPrompt(`I moved ${name} to Rejected. Should I send a rejection email to ${name}?`);
      } else if (targetStage === "offer_sent") {
        onSendPrompt(`I moved ${name} to Offer Sent. Should I draft an offer email for ${name}?`);
      } else {
        onSendPrompt(`I've moved ${name} to the ${targetStage.replace("_", " ")} stage.`);
      }
      return;
    }

    // Legacy: single candidate drag
    const candidate = stageCandidates.find((c) => c.id === dragId);
    if (!candidate) return;
    try {
      await updateCandidate(dragId, { status: targetStage });
      refresh();
    } catch { /* feedback handled by chat */ }
    const name = candidate.name;
    if (targetStage === "contacted") {
      onSendPrompt(`I moved ${name} to Contacted. Draft an outreach email for ${name}?`);
    } else if (targetStage === "interview_scheduled") {
      onSendPrompt(`I moved ${name} to Interview Scheduled. When should I schedule the interview with ${name}?`);
    } else if (targetStage === "rejected") {
      onSendPrompt(`I moved ${name} to Rejected. Should I send a rejection email to ${name}?`);
    } else if (targetStage === "offer_sent") {
      onSendPrompt(`I moved ${name} to Offer Sent. Should I draft an offer email for ${name}?`);
    } else {
      onSendPrompt(`I've moved ${name} to the ${targetStage.replace("_", " ")} stage.`);
    }
  };

  const toggleJobExpand = (jobId: string) => {
    setExpandedJobs((prev) => {
      const next = new Set(prev);
      if (next.has(jobId)) next.delete(jobId);
      else next.add(jobId);
      return next;
    });
  };

  if (!allCandidates && !pipelineEntries) return <LoadingDots />;

  // ── Jobs view ──────────────────────────────────────────────────────────
  if (viewMode === "jobs" && hasPipelineEntries) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-500">
          {t("pipeline.jobsInStage", { count: jobGroups.length })}{" "}
          <span className="font-semibold text-gray-700">{stageLabel}</span>
        </p>

        {jobGroups.length > 0 ? (
          <div className="space-y-2">
            {jobGroups.map((group) => {
              const isExpanded = expandedJobs.has(group.job_id);
              return (
                <div key={group.job_id} className="rounded-lg border border-gray-200 bg-white">
                  {/* Job header */}
                  <button
                    onClick={() => toggleJobExpand(group.job_id)}
                    className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-gray-50"
                  >
                    <WorkOutline sx={{ fontSize: 16 }} className="text-blue-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-gray-800">{group.job_title}</p>
                      {group.job_company && (
                        <p className="truncate text-xs text-gray-400">{group.job_company}</p>
                      )}
                    </div>
                    <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-600">
                      {group.candidates.length}
                    </span>
                    <ChevronRightOutlined
                      sx={{ fontSize: 14 }}
                      className={`text-gray-300 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                    />
                  </button>

                  {/* Candidate list (expandable) */}
                  {isExpanded && (
                    <div className="border-t border-gray-100 px-3 py-2">
                      <div className="max-h-48 space-y-1 overflow-y-auto">
                        {group.candidates.map((entry) => (
                          <button
                            key={`${entry.candidate_id}:${entry.job_id}`}
                            onClick={() => onViewCandidate(entry.candidate_id)}
                            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs hover:bg-gray-50"
                          >
                            <PersonOutlined sx={{ fontSize: 14 }} className="text-gray-400" />
                            <span className="min-w-0 flex-1 truncate font-medium text-gray-700">
                              {entry.candidate_name}
                            </span>
                            {entry.match_score > 0 && (
                              <span className={`text-[10px] font-semibold ${
                                entry.match_score >= 0.7 ? "text-green-600" : entry.match_score >= 0.4 ? "text-amber-600" : "text-red-500"
                              }`}>
                                {Math.round(entry.match_score * 100)}%
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                      <button
                        onClick={() => onViewJob(group.job_id)}
                        className="mt-2 w-full rounded-md bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-600 hover:bg-blue-100"
                      >
                        {t("pipeline.viewJobDetails")}
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-gray-400">{t("pipeline.noJobsInStage")}</p>
        )}
      </div>
    );
  }

  // ── Candidate view (default) ───────────────────────────────────────────
  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        {t("pipeline.candidatesInStage", { count: displayCount })}{" "}
        <span className="font-semibold text-gray-700">{stageLabel}</span>
      </p>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={(event) => setActiveDragId(event.active.id as string)}
        onDragEnd={handleDragEnd}
      >
        {hasPipelineEntries ? (
          stageEntries.length > 0 ? (
            <div className="space-y-2">
              {stageEntries.map((entry: PipelineEntry) => (
                <DraggableCandidateCard
                  key={`${entry.candidate_id}:${entry.job_id}`}
                  candidate={{ id: entry.candidate_id, name: entry.candidate_name, current_title: entry.candidate_title, status: entry.pipeline_status } as Candidate}
                  dragId={`${entry.candidate_id}:${entry.job_id}`}
                  jobLabel={`${entry.job_title}${entry.job_company ? ` · ${entry.job_company}` : ""}`}
                  onViewCandidate={onViewCandidate}
                />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-gray-400">{t("pipeline.noCandidatesInStage")}</p>
          )
        ) : (
          stageCandidates.length > 0 ? (
            <div className="space-y-2">
              {stageCandidates.map((c) => (
                <DraggableCandidateCard
                  key={c.id}
                  candidate={c}
                  onViewCandidate={onViewCandidate}
                />
              ))}
            </div>
          ) : (
            <p className="py-6 text-center text-sm text-gray-400">{t("pipeline.noCandidatesInStage")}</p>
          )
        )}

        {/* Drop zone: stage targets (visible during drag) */}
        {activeDragId && (
          <div className="mt-4 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              {t("pipeline.dropToMove")}
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {targetStages.map((s) => (
                <StageDropTarget key={s.key} stageKey={s.key} label={t(s.labelKey)} />
              ))}
            </div>
          </div>
        )}

        {/* Drag overlay */}
        <DragOverlay>
          {activeDragEntry ? (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 shadow-lg">
              <p className="text-sm font-semibold text-blue-900">{activeDragEntry.candidate_name}</p>
              <p className="text-xs text-blue-600">{activeDragEntry.job_title}{activeDragEntry.job_company ? ` · ${activeDragEntry.job_company}` : ""}</p>
            </div>
          ) : activeDragCandidate ? (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 shadow-lg">
              <p className="text-sm font-semibold text-blue-900">{activeDragCandidate.name}</p>
              <p className="text-xs text-blue-600">{activeDragCandidate.current_title}</p>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Stage-specific actions */}
      <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
        {stage === "new" && displayCount > 0 && (
          <button
            onClick={() => onSendPrompt("Send outreach emails to all new candidates")}
            className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
          >
            {t("pipeline.outreachAllNew")}
          </button>
        )}
        {stage === "contacted" && displayCount > 0 && (
          <button
            onClick={() => onSendPrompt("Follow up with stale contacted candidates")}
            className="rounded-lg bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100"
          >
            {t("pipeline.followUpStale")}
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Events View ─────────────────────────────────────────────────────────── */

function EventsView({ onSendPrompt }: { onSendPrompt: (prompt: string) => void }) {
  const { t } = useTranslation();
  const { data: events } = useApi(useCallback(() => listEvents(), []));

  const upcoming = useMemo(() => {
    if (!events) return [];
    const now = new Date();
    const weekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
    return events
      .filter((e) => {
        const d = new Date(e.start_time);
        return d >= now && d <= weekLater;
      })
      .sort((a, b) => a.start_time.localeCompare(b.start_time));
  }, [events]);

  if (!events) return <LoadingDots />;

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        {t("contextPanel.eventsInNext7Days", { count: upcoming.length })}
      </p>

      {upcoming.length > 0 ? (
        <div className="space-y-2">
          {upcoming.map((e) => {
            const dateStr = new Date(e.start_time).toLocaleDateString("en-US", {
              weekday: "short", month: "short", day: "numeric",
            });
            const timeStr = e.start_time?.slice(11, 16);
            const who = e.candidate_name || "the candidate";
            return (
              <div key={e.id} className="rounded-lg border border-gray-100 p-3">
                <div className="flex items-start justify-between">
                  <p className="text-sm font-medium text-gray-900">{e.title}</p>
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${EVENT_COLORS[e.event_type] || EVENT_COLORS.other}`}>
                    {e.event_type.replace("_", " ")}
                  </span>
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {dateStr} {timeStr && `at ${timeStr}`}
                </p>
                {e.candidate_name && (
                  <p className="text-xs text-gray-400">{t("contextPanel.with", { name: e.candidate_name })}</p>
                )}
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => onSendPrompt(`Reschedule the ${e.event_type.replace("_", " ")} with ${who}`)}
                    className="text-[10px] font-medium text-blue-600 hover:underline"
                  >
                    {t("contextPanel.reschedule")}
                  </button>
                  <button
                    onClick={() => onSendPrompt(`Send a reminder about the ${e.event_type.replace("_", " ")} with ${who}`)}
                    className="text-[10px] font-medium text-green-600 hover:underline"
                  >
                    {t("contextPanel.remind")}
                  </button>
                  <button
                    onClick={() => onSendPrompt(`Cancel the ${e.event_type.replace("_", " ")} with ${who}`)}
                    className="text-[10px] font-medium text-red-500 hover:underline"
                  >
                    {t("contextPanel.cancel")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-6 text-center">
          <CalendarTodayOutlined className="mx-auto text-gray-300" sx={{ fontSize: 32 }} />
          <p className="mt-2 text-sm text-gray-400">{t("contextPanel.noUpcomingEvents")}</p>
          <button
            onClick={() => onSendPrompt("Schedule an interview")}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            {t("contextPanel.scheduleOne")}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Comparison View ─────────────────────────────────────────────────────── */

function ComparisonView({
  candidateIds,
  onViewCandidate,
  onSendPrompt,
}: {
  candidateIds: [string, string];
  onViewCandidate: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}) {
  const { t } = useTranslation();
  const { data: c1 } = useApi(useCallback(() => getCandidate(candidateIds[0]), [candidateIds[0]]));
  const { data: c2 } = useApi(useCallback(() => getCandidate(candidateIds[1]), [candidateIds[1]]));

  if (!c1 || !c2) return <LoadingDots />;

  const s1 = new Set(c1.skills.map((s) => s.toLowerCase()));
  const s2 = new Set(c2.skills.map((s) => s.toLowerCase()));
  const shared = c1.skills.filter((s) => s2.has(s.toLowerCase()));
  const only1 = c1.skills.filter((s) => !s2.has(s.toLowerCase()));
  const only2 = c2.skills.filter((s) => !s1.has(s.toLowerCase()));

  return (
    <div className="space-y-3">
      {/* Compact profile cards */}
      {[c1, c2].map((c) => (
        <button
          key={c.id}
          onClick={() => onViewCandidate(c.id)}
          className="w-full rounded-lg border border-gray-100 p-3 text-left hover:border-gray-200"
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold text-gray-900">{c.name}</p>
              <p className="text-xs text-gray-500">{c.current_title}</p>
            </div>
            {c.match_score > 0 && (
              <span className="text-xs font-semibold text-amber-600">
                {Math.round(c.match_score * 100)}%
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-400">
            {c.experience_years != null && <span>{c.experience_years}+ yrs</span>}
            {c.location && <span>{c.location}</span>}
          </div>
        </button>
      ))}

      {/* Skills comparison */}
      {shared.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.sharedSkills", { count: shared.length })}</h5>
          <div className="flex flex-wrap gap-1">
            {shared.slice(0, 6).map((s) => (
              <span key={s} className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] text-green-700">{s}</span>
            ))}
          </div>
        </div>
      )}

      {only1.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.onlySkills", { name: c1.name })}</h5>
          <div className="flex flex-wrap gap-1">
            {only1.slice(0, 4).map((s) => (
              <span key={s} className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-blue-700">{s}</span>
            ))}
          </div>
        </div>
      )}

      {only2.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">{t("contextPanel.onlySkills", { name: c2.name })}</h5>
          <div className="flex flex-wrap gap-1">
            {only2.slice(0, 4).map((s) => (
              <span key={s} className="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] text-purple-700">{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Quick comparison */}
      <div className="rounded-lg border border-gray-100 p-3">
        <h5 className="mb-2 text-xs font-semibold text-gray-500">{t("contextPanel.quickComparison")}</h5>
        <div className="space-y-1">
          <CompareRow
            label={t("contextPanel.matchLabel")}
            v1={c1.match_score > 0 ? `${Math.round(c1.match_score * 100)}%` : t("common.na")}
            v2={c2.match_score > 0 ? `${Math.round(c2.match_score * 100)}%` : t("common.na")}
            winner={c1.match_score > c2.match_score ? 1 : c2.match_score > c1.match_score ? 2 : 0}
          />
          <CompareRow
            label={t("contextPanel.experienceLabel")}
            v1={c1.experience_years != null ? `${c1.experience_years} yrs` : t("common.na")}
            v2={c2.experience_years != null ? `${c2.experience_years} yrs` : t("common.na")}
            winner={
              c1.experience_years != null && c2.experience_years != null
                ? c1.experience_years > c2.experience_years ? 1 : c2.experience_years > c1.experience_years ? 2 : 0
                : 0
            }
          />
          <CompareRow
            label={t("contextPanel.skillsLabel")}
            v1={`${c1.skills.length}`}
            v2={`${c2.skills.length}`}
            winner={c1.skills.length > c2.skills.length ? 1 : c2.skills.length > c1.skills.length ? 2 : 0}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
        <button
          onClick={() => onSendPrompt(`Draft email to ${c1.name}`)}
          className="rounded-lg bg-blue-50 px-2.5 py-1.5 text-[10px] font-medium text-blue-700 hover:bg-blue-100"
        >
          Email {c1.name.split(" ")[0]}
        </button>
        <button
          onClick={() => onSendPrompt(`Draft email to ${c2.name}`)}
          className="rounded-lg bg-blue-50 px-2.5 py-1.5 text-[10px] font-medium text-blue-700 hover:bg-blue-100"
        >
          Email {c2.name.split(" ")[0]}
        </button>
      </div>
    </div>
  );
}

function CompareRow({ label, v1, v2, winner }: {
  label: string; v1: string; v2: string; winner: 0 | 1 | 2;
}) {
  return (
    <div className="flex items-center gap-2 py-1 text-xs">
      <span className="w-20 text-gray-400">{label}</span>
      <span className={`flex-1 text-center ${winner === 1 ? "font-semibold text-green-700" : "text-gray-600"}`}>{v1}</span>
      <span className={`flex-1 text-center ${winner === 2 ? "font-semibold text-green-700" : "text-gray-600"}`}>{v2}</span>
    </div>
  );
}

/* ── Notification Card ────────────────────────────────────────────────────── */

function NotificationCard({
  notification: n,
  onAction,
  onViewCandidate,
}: {
  notification: Notification;
  onAction: (prompt: string) => void;
  onViewCandidate: (id: string) => void;
}) {
  const { t } = useTranslation();
  const severityStyles = {
    warning: "border-amber-200 bg-amber-50",
    success: "border-green-200 bg-green-50",
    info: "border-blue-200 bg-blue-50",
  };
  const iconStyles = {
    warning: "text-amber-500",
    success: "text-green-500",
    info: "text-blue-500",
  };
  const SeverityIcon = n.severity === "warning" ? WarningAmberOutlined
    : n.severity === "success" ? AutoAwesomeOutlined : NotificationsOutlined;

  return (
    <div className={`rounded-lg border p-2.5 ${severityStyles[n.severity]}`}>
      <div className="flex items-start gap-2">
        <SeverityIcon className={`mt-0.5 shrink-0 ${iconStyles[n.severity]}`} sx={{ fontSize: 14 }} />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-800">{n.title}</p>
          <p className="mt-0.5 text-[10px] text-gray-500">{n.description}</p>
          <div className="mt-1.5 flex gap-2">
            <button
              onClick={() => onAction(n.action_prompt)}
              className="text-[10px] font-medium text-blue-600 hover:underline"
            >
              {n.action_label}
            </button>
            {n.candidate_id && (
              <button
                onClick={() => onViewCandidate(n.candidate_id!)}
                className="text-[10px] text-gray-400 hover:text-gray-600"
              >
                {t("contextPanel.viewProfile")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function StatCard({
  icon, label, value, color,
}: {
  icon: React.ReactNode; label: string; value: number; color: string;
}) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    purple: "bg-purple-50 text-purple-600",
    amber: "bg-amber-50 text-amber-600",
    green: "bg-green-50 text-green-600",
  };
  return (
    <div className="rounded-lg border border-gray-100 p-3">
      <div className={`mb-1 inline-flex rounded-lg p-1.5 ${colors[color] || ""}`}>{icon}</div>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      <p className="text-[10px] font-medium uppercase tracking-wider text-gray-400">{label}</p>
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="flex gap-1">
        <span className="h-2 w-2 animate-bounce rounded-full bg-gray-300 [animation-delay:0ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-gray-300 [animation-delay:150ms]" />
        <span className="h-2 w-2 animate-bounce rounded-full bg-gray-300 [animation-delay:300ms]" />
      </div>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-slate-100 text-slate-700",
  contacted: "bg-blue-100 text-blue-700",
  replied: "bg-emerald-100 text-emerald-700",
  screening: "bg-amber-100 text-amber-700",
  interview_scheduled: "bg-purple-100 text-purple-700",
  interviewed: "bg-indigo-100 text-indigo-700",
  offer_sent: "bg-pink-100 text-pink-700",
  hired: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  withdrawn: "bg-gray-100 text-gray-700",
};

const EVENT_COLORS: Record<string, string> = {
  interview: "bg-purple-100 text-purple-700",
  follow_up: "bg-blue-100 text-blue-700",
  offer: "bg-green-100 text-green-700",
  screening: "bg-amber-100 text-amber-700",
  other: "bg-gray-100 text-gray-700",
};
