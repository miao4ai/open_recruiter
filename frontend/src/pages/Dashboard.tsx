import { useCallback, useMemo, useState } from "react";
import {
  Briefcase, Users, Mail, Calendar, Plus, Upload, Send,
  ChevronLeft, ChevronRight, Clock, User,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { listJobs, listCandidates, listEmails, listEvents } from "../lib/api";
import type { Job, Candidate, Email, CalendarEvent, EventType } from "../types";
import { PIPELINE_COLUMNS } from "../types";

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className={`rounded-lg p-2.5 ${color}`}>
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-semibold">{value}</p>
      </div>
    </div>
  );
}

type ActivityItem = {
  type: "job" | "candidate" | "email";
  icon: React.ElementType;
  iconColor: string;
  title: string;
  detail: string;
  time: string;
};

function RecentActivity({
  jobs,
  candidates,
  emails,
}: {
  jobs: Job[] | null;
  candidates: Candidate[] | null;
  emails: Email[] | null;
}) {
  const items = useMemo(() => {
    const all: ActivityItem[] = [];

    for (const j of jobs ?? []) {
      all.push({
        type: "job",
        icon: Plus,
        iconColor: "bg-blue-100 text-blue-600",
        title: `Job created: ${j.title}`,
        detail: j.company || "",
        time: j.created_at,
      });
    }

    for (const c of candidates ?? []) {
      all.push({
        type: "candidate",
        icon: Upload,
        iconColor: "bg-emerald-100 text-emerald-600",
        title: `Candidate added: ${c.name || "Unnamed"}`,
        detail: c.current_title ? `${c.current_title}${c.current_company ? ` at ${c.current_company}` : ""}` : "",
        time: c.created_at,
      });
    }

    for (const e of emails ?? []) {
      const status = e.sent ? "sent" : e.approved ? "approved" : "drafted";
      all.push({
        type: "email",
        icon: e.sent ? Send : Mail,
        iconColor: e.sent
          ? "bg-green-100 text-green-600"
          : "bg-amber-100 text-amber-600",
        title: `Email ${status}: ${e.subject}`,
        detail: `To: ${e.to_email}${e.candidate_name ? ` (${e.candidate_name})` : ""}`,
        time: e.sent_at || e.created_at,
      });
    }

    // Sort by time descending, take latest 15
    all.sort((a, b) => (b.time ?? "").localeCompare(a.time ?? ""));
    return all.slice(0, 15);
  }, [jobs, candidates, emails]);

  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-400">
        No activity yet. Create a job and add candidates to get started.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white divide-y divide-gray-100">
      {items.map((item, i) => (
        <div key={i} className="flex items-start gap-3 px-4 py-3">
          <div className={`mt-0.5 rounded-lg p-1.5 ${item.iconColor}`}>
            <item.icon className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-gray-800 truncate">
              {item.title}
            </p>
            {item.detail && (
              <p className="text-xs text-gray-500 truncate">{item.detail}</p>
            )}
          </div>
          <time className="shrink-0 text-xs text-gray-400">
            {formatRelativeTime(item.time)}
          </time>
        </div>
      ))}
    </div>
  );
}

function formatRelativeTime(isoStr: string): string {
  if (!isoStr) return "";
  const date = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

/* ── Weekly Calendar Strip ─────────────────────────────────────────────── */

const DAY_NAMES_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const EVENT_DOT_COLORS: Record<EventType, string> = {
  interview: "bg-purple-500",
  follow_up: "bg-blue-500",
  offer: "bg-green-500",
  screening: "bg-amber-500",
  other: "bg-gray-400",
};

const EVENT_PILL_COLORS: Record<EventType, { bg: string; text: string }> = {
  interview: { bg: "bg-purple-50 border-purple-200", text: "text-purple-700" },
  follow_up: { bg: "bg-blue-50 border-blue-200", text: "text-blue-700" },
  offer: { bg: "bg-green-50 border-green-200", text: "text-green-700" },
  screening: { bg: "bg-amber-50 border-amber-200", text: "text-amber-700" },
  other: { bg: "bg-gray-50 border-gray-200", text: "text-gray-600" },
};

function pad2(n: number) { return n.toString().padStart(2, "0"); }
function toDateKey(d: Date) { return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; }
function getMonday(d: Date) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Monday
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

function formatTimeShort(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function WeeklyCalendar({ events }: { events: CalendarEvent[] | null }) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = toDateKey(today);

  // weekOffset: 0 = current week, -1 = previous week, +1 = next week
  const [weekOffset, setWeekOffset] = useState(0);

  const weekDays = useMemo(() => {
    const ref = new Date(today);
    ref.setDate(ref.getDate() + weekOffset * 7);
    const monday = getMonday(ref);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
  }, [weekOffset]);

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const e of events ?? []) {
      const key = e.start_time.slice(0, 10);
      if (!map[key]) map[key] = [];
      map[key].push(e);
    }
    return map;
  }, [events]);

  // Selected day (defaults to today if in current week, else Monday)
  const [selectedDate, setSelectedDate] = useState(todayStr);

  const selectedEvents = eventsByDate[selectedDate] ?? [];

  const weekLabel = useMemo(() => {
    const first = weekDays[0];
    const last = weekDays[6];
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
    return `${first.toLocaleDateString(undefined, opts)} — ${last.toLocaleDateString(undefined, opts)}`;
  }, [weekDays]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">This Week</h2>
          <span className="text-xs text-gray-400">{weekLabel}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setWeekOffset((o) => o - 1)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={() => { setWeekOffset(0); setSelectedDate(todayStr); }}
            className="rounded border px-2 py-0.5 text-xs font-medium text-gray-500 hover:bg-gray-50"
          >
            Today
          </button>
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <Link
            to="/calendar"
            className="ml-2 text-xs text-blue-600 hover:text-blue-800"
          >
            Full calendar
          </Link>
        </div>
      </div>

      {/* Day strip */}
      <div className="grid grid-cols-7 border-b">
        {weekDays.map((d) => {
          const key = toDateKey(d);
          const isToday = key === todayStr;
          const isSelected = key === selectedDate;
          const dayEvents = eventsByDate[key] ?? [];
          return (
            <button
              key={key}
              onClick={() => setSelectedDate(key)}
              className={`flex flex-col items-center gap-1 py-3 transition-colors ${
                isSelected ? "bg-blue-50" : "hover:bg-gray-50"
              }`}
            >
              <span className="text-xs text-gray-400">
                {DAY_NAMES_SHORT[d.getDay()]}
              </span>
              <span
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                  isToday
                    ? "bg-blue-600 text-white"
                    : isSelected
                      ? "bg-blue-100 text-blue-700"
                      : "text-gray-700"
                }`}
              >
                {d.getDate()}
              </span>
              {/* Event dots */}
              <div className="flex gap-0.5">
                {dayEvents.slice(0, 3).map((evt) => (
                  <span
                    key={evt.id}
                    className={`h-1.5 w-1.5 rounded-full ${EVENT_DOT_COLORS[evt.event_type] || EVENT_DOT_COLORS.other}`}
                  />
                ))}
              </div>
            </button>
          );
        })}
      </div>

      {/* Selected day's events */}
      <div className="px-4 py-3">
        {selectedEvents.length === 0 ? (
          <p className="py-2 text-center text-xs text-gray-400">
            No events on this day
          </p>
        ) : (
          <div className="space-y-2">
            {selectedEvents.map((evt) => {
              const c = EVENT_PILL_COLORS[evt.event_type] || EVENT_PILL_COLORS.other;
              return (
                <div
                  key={evt.id}
                  className={`flex items-start gap-3 rounded-lg border p-2.5 ${c.bg}`}
                >
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium ${c.text}`}>{evt.title}</p>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatTimeShort(evt.start_time)}
                        {evt.end_time ? ` — ${formatTimeShort(evt.end_time)}` : ""}
                      </span>
                      {evt.candidate_name && (
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {evt.candidate_name}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


export default function Dashboard() {
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const { data: candidates } = useApi(
    useCallback(() => listCandidates(), [])
  );
  const { data: emails } = useApi(useCallback(() => listEmails(), []));
  const { data: events } = useApi(useCallback(() => listEvents(), []));

  const totalJobs = jobs?.length ?? 0;
  const totalCandidates = candidates?.length ?? 0;
  const pendingEmails =
    emails?.filter((e) => !e.sent && !e.approved).length ?? 0;
  const interviews =
    candidates?.filter((c) => c.status === "interview_scheduled").length ?? 0;

  // Group candidates by status for pipeline
  const grouped: Record<string, typeof candidates> = {};
  for (const col of PIPELINE_COLUMNS) {
    grouped[col.key] = candidates?.filter((c) => c.status === col.key) ?? [];
  }

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Briefcase}
          label="Active Jobs"
          value={totalJobs}
          color="bg-blue-500"
        />
        <StatCard
          icon={Users}
          label="Candidates"
          value={totalCandidates}
          color="bg-emerald-500"
        />
        <StatCard
          icon={Mail}
          label="Pending Emails"
          value={pendingEmails}
          color="bg-amber-500"
        />
        <StatCard
          icon={Calendar}
          label="Interviews"
          value={interviews}
          color="bg-purple-500"
        />
      </div>

      {/* Weekly Calendar */}
      <WeeklyCalendar events={events} />

      {/* Pipeline Kanban */}
      <div>
        <h2 className="mb-4 text-lg font-semibold">Pipeline</h2>
        <div className="flex gap-3 overflow-x-auto pb-4">
          {PIPELINE_COLUMNS.map((col) => (
            <div
              key={col.key}
              className="w-52 shrink-0 rounded-lg border border-gray-200 bg-white"
            >
              <div className="border-b border-gray-100 px-3 py-2">
                <h3 className="text-sm font-medium text-gray-700">
                  {col.label}
                  <span className="ml-1.5 text-xs text-gray-400">
                    {grouped[col.key]?.length ?? 0}
                  </span>
                </h3>
              </div>
              <div className="space-y-2 p-2">
                {grouped[col.key]?.map((c) => (
                  <div
                    key={c.id}
                    className="rounded-md border border-gray-100 bg-gray-50 p-2 text-sm"
                  >
                    <p className="font-medium">{c.name || "Unnamed"}</p>
                    <p className="text-xs text-gray-500">
                      Score: {Math.round(c.match_score * 100)}%
                    </p>
                  </div>
                )) ?? (
                  <p className="px-2 py-4 text-center text-xs text-gray-400">
                    No candidates
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Recent Activity</h2>
        <RecentActivity jobs={jobs} candidates={candidates} emails={emails} />
      </div>
    </div>
  );
}
