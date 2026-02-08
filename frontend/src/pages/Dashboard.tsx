import { useCallback } from "react";
import { Briefcase, Users, Mail, Calendar } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { listJobs, listCandidates, listEmails } from "../lib/api";
import type { CandidateStatus } from "../types";
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

      {/* Recent activity placeholder */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Recent Activity</h2>
        <div className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-400">
          No activity yet. Create a job and add candidates to get started.
        </div>
      </div>
    </div>
  );
}
