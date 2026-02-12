import { useCallback, useMemo } from "react";
import { Briefcase, Users, Mail, Calendar, Plus, Upload, Send } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { listJobs, listCandidates, listEmails } from "../lib/api";
import type { Job, Candidate, Email, CandidateStatus } from "../types";
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

export default function Dashboard() {
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const { data: candidates } = useApi(
    useCallback(() => listCandidates(), [])
  );
  const { data: emails } = useApi(useCallback(() => listEmails(), []));

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
