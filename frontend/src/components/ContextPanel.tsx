import { useCallback, useEffect, useMemo, useState } from "react";
import {
  X, Users, Briefcase, Calendar, Mail, MapPin, Building2,
  Star, Clock, ChevronRight, FileText, TrendingUp,
  AlertTriangle, Bell, Sparkles,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  getCandidate, getJob, listCandidates, listEmails, listEvents, listJobs,
  getNotifications,
} from "../lib/api";
import type { Candidate, CandidateStatus, ContextView, CalendarEvent, Notification } from "../types";
import { PIPELINE_COLUMNS } from "../types";

interface Props {
  view: ContextView | null;
  onClose: () => void;
  onViewCandidate: (id: string) => void;
  onViewJob: (id: string) => void;
  onSendPrompt: (prompt: string) => void;
}

export default function ContextPanel({ view, onClose, onViewCandidate, onViewJob, onSendPrompt }: Props) {
  if (!view) return null;

  return (
    <div className="flex w-80 flex-col rounded-xl border border-gray-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-800">
          {view.type === "briefing" && "Daily Briefing"}
          {view.type === "candidate" && "Candidate"}
          {view.type === "job" && "Job Details"}
          {view.type === "pipeline_stage" && "Pipeline Stage"}
          {view.type === "events" && "Upcoming Events"}
        </h3>
        <button
          onClick={onClose}
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
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
          <PipelineStageView stage={view.stage} onViewCandidate={onViewCandidate} />
        )}
        {view.type === "events" && (
          <EventsView onSendPrompt={onSendPrompt} />
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
        <StatCard icon={<Users className="h-4 w-4" />} label="Candidates" value={stats.total} color="blue" />
        <StatCard icon={<Briefcase className="h-4 w-4" />} label="Active Jobs" value={stats.jobCount} color="purple" />
        <StatCard icon={<Mail className="h-4 w-4" />} label="Pending Emails" value={stats.pendingEmails.length} color="amber" />
        <StatCard icon={<Calendar className="h-4 w-4" />} label="Today's Events" value={stats.todayEvents.length} color="green" />
      </div>

      {/* Proactive Notifications */}
      {notifications.length > 0 && (
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <Bell className="h-3.5 w-3.5" /> Alerts ({notifications.length})
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
            <Clock className="h-3.5 w-3.5" /> Awaiting Reply ({stats.contacted.length})
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
            <Calendar className="h-3.5 w-3.5" /> Today
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
          <TrendingUp className="h-4 w-4" />
          {stats.newCount} new candidate{stats.newCount !== 1 ? "s" : ""} to review
          <ChevronRight className="ml-auto h-4 w-4" />
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
            {candidate.current_company && ` at ${candidate.current_company}`}
          </p>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}>
            {candidate.status.replace("_", " ")}
          </span>
          {candidate.match_score > 0 && (
            <span className="flex items-center gap-1 text-xs text-amber-600">
              <Star className="h-3 w-3" fill="currentColor" />
              {Math.round(candidate.match_score * 100)}% match
            </span>
          )}
        </div>
      </div>

      {/* Details */}
      <div className="space-y-1.5 text-sm">
        {candidate.email && (
          <div className="flex items-center gap-2 text-gray-600">
            <Mail className="h-3.5 w-3.5 text-gray-400" /> {candidate.email}
          </div>
        )}
        {candidate.location && (
          <div className="flex items-center gap-2 text-gray-600">
            <MapPin className="h-3.5 w-3.5 text-gray-400" /> {candidate.location}
          </div>
        )}
        {candidate.experience_years != null && (
          <div className="flex items-center gap-2 text-gray-600">
            <Building2 className="h-3.5 w-3.5 text-gray-400" /> {candidate.experience_years}+ years
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
            <FileText className="h-3 w-3" /> Resume Summary
          </h5>
          <p className="text-xs leading-relaxed text-gray-600">{candidate.resume_summary}</p>
        </div>
      )}

      {/* Top jobs */}
      {candidate.top_jobs && candidate.top_jobs.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">Top Matching Jobs</h5>
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
            Email History ({emails.length})
          </h5>
          <div className="space-y-1">
            {emails.slice(0, 3).map((e) => (
              <div key={e.id} className="rounded border border-gray-100 px-2 py-1.5">
                <p className="truncate text-xs font-medium text-gray-700">{e.subject}</p>
                <p className="text-[10px] text-gray-400">
                  {e.sent ? "Sent" : e.approved ? "Approved" : "Draft"} • {e.email_type}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-3">
        <button
          onClick={() => onSendPrompt(`Draft an outreach email to ${candidate.name}`)}
          className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100"
        >
          Draft Email
        </button>
        <button
          onClick={() => onSendPrompt(`What jobs match ${candidate.name}?`)}
          className="rounded-lg bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"
        >
          Match Jobs
        </button>
      </div>
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
            <span className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {job.location}</span>
          )}
          {job.remote && <span className="rounded bg-green-50 px-1.5 py-0.5 text-green-700">Remote</span>}
          {job.salary_range && <span>{job.salary_range}</span>}
        </div>
      </div>

      {/* Skills */}
      {job.required_skills.length > 0 && (
        <div>
          <h5 className="mb-1 text-xs font-semibold text-gray-500">Required Skills</h5>
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
          <h5 className="mb-1 text-xs font-semibold text-gray-500">Summary</h5>
          <p className="text-xs leading-relaxed text-gray-600">{job.summary}</p>
        </div>
      )}

      {/* Candidates */}
      <div>
        <h5 className="mb-1 text-xs font-semibold text-gray-500">
          Candidates ({jobCandidates.length})
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
          <p className="text-xs text-gray-400">No candidates yet</p>
        )}
      </div>

      {/* Actions */}
      <div className="border-t border-gray-100 pt-3">
        <button
          onClick={() => onSendPrompt(`Upload a resume for the ${job.title} position`)}
          className="rounded-lg bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"
        >
          Upload Resume
        </button>
      </div>
    </div>
  );
}

/* ── Pipeline Stage View ─────────────────────────────────────────────────── */

function PipelineStageView({
  stage,
  onViewCandidate,
}: {
  stage: CandidateStatus;
  onViewCandidate: (id: string) => void;
}) {
  const { data: allCandidates } = useApi(useCallback(() => listCandidates(), []));

  const stageCandidates = useMemo(
    () => (allCandidates || []).filter((c) => c.status === stage),
    [allCandidates, stage]
  );

  const stageLabel = PIPELINE_COLUMNS.find((p) => p.key === stage)?.label || stage;

  if (!allCandidates) return <LoadingDots />;

  return (
    <div className="space-y-3">
      <p className="text-sm text-gray-500">
        {stageCandidates.length} candidate{stageCandidates.length !== 1 ? "s" : ""} in{" "}
        <span className="font-semibold text-gray-700">{stageLabel}</span>
      </p>

      {stageCandidates.length > 0 ? (
        <div className="space-y-2">
          {stageCandidates.map((c) => (
            <button
              key={c.id}
              onClick={() => onViewCandidate(c.id)}
              className="flex w-full items-start gap-3 rounded-lg border border-gray-100 p-3 text-left hover:border-gray-200 hover:shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium text-gray-900">{c.name}</p>
                <p className="truncate text-xs text-gray-500">
                  {c.current_title || "N/A"}
                  {c.current_company ? ` at ${c.current_company}` : ""}
                </p>
                {c.skills.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.skills.slice(0, 3).map((s) => (
                      <span key={s} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {c.match_score > 0 && (
                <span className="shrink-0 text-xs font-semibold text-amber-600">
                  {Math.round(c.match_score * 100)}%
                </span>
              )}
            </button>
          ))}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-gray-400">No candidates in this stage</p>
      )}
    </div>
  );
}

/* ── Events View ─────────────────────────────────────────────────────────── */

function EventsView({ onSendPrompt }: { onSendPrompt: (prompt: string) => void }) {
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
        {upcoming.length} event{upcoming.length !== 1 ? "s" : ""} in the next 7 days
      </p>

      {upcoming.length > 0 ? (
        <div className="space-y-2">
          {upcoming.map((e) => {
            const dateStr = new Date(e.start_time).toLocaleDateString("en-US", {
              weekday: "short", month: "short", day: "numeric",
            });
            const timeStr = e.start_time?.slice(11, 16);
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
                  <p className="text-xs text-gray-400">with {e.candidate_name}</p>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-6 text-center">
          <Calendar className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-400">No upcoming events</p>
          <button
            onClick={() => onSendPrompt("Schedule an interview")}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            Schedule one
          </button>
        </div>
      )}
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
  const SeverityIcon = n.severity === "warning" ? AlertTriangle
    : n.severity === "success" ? Sparkles : Bell;

  return (
    <div className={`rounded-lg border p-2.5 ${severityStyles[n.severity]}`}>
      <div className="flex items-start gap-2">
        <SeverityIcon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${iconStyles[n.severity]}`} />
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
                View profile
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
