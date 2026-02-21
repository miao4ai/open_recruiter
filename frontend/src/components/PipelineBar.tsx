import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ChevronRightOutlined, PersonOutlined, WorkOutline } from "@mui/icons-material";
import type { Candidate, CandidateStatus, PipelineEntry, PipelineViewMode } from "../types";
import { PIPELINE_COLUMNS } from "../types";

const STAGE_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  new: { bg: "bg-slate-50", text: "text-slate-700", dot: "bg-slate-400" },
  contacted: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-400" },
  replied: { bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-400" },
  screening: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-400" },
  interview_scheduled: { bg: "bg-purple-50", text: "text-purple-700", dot: "bg-purple-400" },
  offer_sent: { bg: "bg-pink-50", text: "text-pink-700", dot: "bg-pink-400" },
  hired: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-400" },
};

interface Props {
  candidates: Candidate[];
  pipelineEntries?: PipelineEntry[];
  viewMode?: PipelineViewMode;
  onViewModeChange?: (mode: PipelineViewMode) => void;
  activeStage: CandidateStatus | null;
  onStageClick: (stage: CandidateStatus) => void;
}

export default function PipelineBar({
  candidates,
  pipelineEntries,
  viewMode = "candidate",
  onViewModeChange,
  activeStage,
  onStageClick,
}: Props) {
  const { t } = useTranslation();

  // Use pipeline entries (per-job) if available, otherwise fall back to candidates
  const counts = useMemo(() => {
    const c: Partial<Record<CandidateStatus, number>> = {};
    if (pipelineEntries && pipelineEntries.length > 0) {
      if (viewMode === "jobs") {
        // Jobs view: count unique jobs per stage
        const jobSets: Partial<Record<CandidateStatus, Set<string>>> = {};
        for (const entry of pipelineEntries) {
          const s = entry.pipeline_status as CandidateStatus;
          if (!jobSets[s]) jobSets[s] = new Set();
          jobSets[s]!.add(entry.job_id);
        }
        for (const [s, set] of Object.entries(jobSets)) {
          c[s as CandidateStatus] = set!.size;
        }
      } else {
        for (const entry of pipelineEntries) {
          const s = entry.pipeline_status as CandidateStatus;
          c[s] = (c[s] || 0) + 1;
        }
      }
    } else if (viewMode !== "jobs") {
      // Candidate view fallback: count from candidates array
      for (const cand of candidates) {
        c[cand.status] = (c[cand.status] || 0) + 1;
      }
    }
    // Jobs view with no entries → all counts stay 0
    return c;
  }, [candidates, pipelineEntries, viewMode]);

  const total = useMemo(() => {
    if (pipelineEntries && pipelineEntries.length > 0) {
      if (viewMode === "jobs") {
        const uniqueJobs = new Set(pipelineEntries.map((e) => e.job_id));
        return uniqueJobs.size;
      }
      return pipelineEntries.length;
    }
    // Jobs view with no entries → total 0; Candidate view → candidate count
    return viewMode === "jobs" ? 0 : candidates.length;
  }, [pipelineEntries, candidates, viewMode]);

  return (
    <div className="flex items-center gap-1 rounded-xl border border-gray-200 bg-white px-3 py-2">
      {/* View mode toggle */}
      {onViewModeChange && (
        <div className="mr-2 flex items-center rounded-lg border border-gray-200 bg-gray-50">
          <button
            onClick={() => onViewModeChange("candidate")}
            className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-all ${
              viewMode === "candidate"
                ? "bg-white text-blue-600 shadow-sm"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <PersonOutlined sx={{ fontSize: 13 }} />
            {t("pipeline.viewCandidate")}
          </button>
          <button
            onClick={() => onViewModeChange("jobs")}
            className={`flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition-all ${
              viewMode === "jobs"
                ? "bg-white text-blue-600 shadow-sm"
                : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <WorkOutline sx={{ fontSize: 13 }} />
            {t("pipeline.viewJobs")}
          </button>
        </div>
      )}

      <span className="mr-2 text-xs font-medium text-gray-400">
        {t("pipeline.label")}
        <span className="ml-1 text-gray-300">({total})</span>
      </span>
      {PIPELINE_COLUMNS.map((col, i) => {
        const count = counts[col.key] || 0;
        const colors = STAGE_COLORS[col.key] || STAGE_COLORS.new;
        const isActive = activeStage === col.key;

        return (
          <div key={col.key} className="flex items-center">
            {i > 0 && <ChevronRightOutlined sx={{ fontSize: 12 }} className="mx-0.5 text-gray-300" />}
            <button
              onClick={() => onStageClick(col.key)}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                isActive
                  ? `${colors.bg} ${colors.text} ring-2 ring-blue-400 ring-offset-1`
                  : `hover:${colors.bg} text-gray-500 hover:${colors.text}`
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
              {t(col.labelKey)}
              <span
                className={`min-w-[1.25rem] rounded-full px-1 py-0.5 text-center text-[10px] font-bold leading-none ${
                  count > 0
                    ? `${colors.bg} ${colors.text}`
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {count}
              </span>
            </button>
          </div>
        );
      })}
    </div>
  );
}
