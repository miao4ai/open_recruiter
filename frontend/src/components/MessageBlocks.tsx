import React from "react";
import { WorkOutline, CheckOutlined, ChevronRightOutlined, StarOutlined, TrendingUpOutlined, WarningAmberOutlined, CloseOutlined, AutoFixHighOutlined, DescriptionOutlined, ContentCopyOutlined } from "@mui/icons-material";
import type { MessageBlock, MatchRanking, ApprovalBlock, SchedulingApprovalBlock, PipelineCleanupBlock, BulkOutreachBlock, ResumeImprovementBlock, CoverLetterBlock, CandidateEvalBlock, CandidateEvalDimension } from "../types";
import PlanPreview from "./PlanPreview";
import GuardrailWarning from "./GuardrailWarning";
import SchedulingApprovalCard from "./SchedulingApprovalCard";
import PipelineCleanupCard from "./PipelineCleanupCard";
import BulkOutreachCard from "./BulkOutreachCard";

interface Props {
  blocks: MessageBlock[];
  onSendPrompt: (prompt: string) => void;
  onViewCandidate?: (id: string) => void;
  onViewJob?: (id: string) => void;
  onResumeWorkflow?: (workflowId: string, payload: Record<string, unknown>) => void;
  onCancelWorkflow?: (workflowId: string) => void;
}

export default function MessageBlocks({ blocks, onSendPrompt, onViewJob, onResumeWorkflow, onCancelWorkflow }: Props) {
  if (!blocks || blocks.length === 0) return null;

  return (
    <div className="mt-2 space-y-2">
      {blocks.map((block, i) => {
        if (block.type === "match_report") {
          return (
            <MatchReportCard
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
              onViewJob={onViewJob}
            />
          );
        }
        if (block.type === "approval_block") {
          return (
            <ApprovalBlockCard
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        if (block.type === "scheduling_approval") {
          return (
            <SchedulingApprovalCard
              key={i}
              block={block}
              onApprove={(wfId, slot) =>
                onResumeWorkflow?.(wfId, { selected_slot: slot })
              }
              onCancel={(wfId) => onCancelWorkflow?.(wfId)}
            />
          );
        }
        if (block.type === "pipeline_cleanup") {
          return (
            <PipelineCleanupCard
              key={i}
              block={block}
              onApprove={(wfId, actions) =>
                onResumeWorkflow?.(wfId, { approved: true, actions })
              }
              onCancel={(wfId) => onCancelWorkflow?.(wfId)}
            />
          );
        }
        if (block.type === "bulk_outreach") {
          return (
            <BulkOutreachCard
              key={i}
              block={block}
              onApprove={(wfId, drafts) =>
                onResumeWorkflow?.(wfId, { approved: true, drafts })
              }
              onCancel={(wfId) => onCancelWorkflow?.(wfId)}
            />
          );
        }
        if (block.type === "resume_improvement") {
          return (
            <ResumeImprovementCard
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        if (block.type === "cover_letter") {
          return (
            <CoverLetterCard
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        if (block.type === "plan_preview") {
          return (
            <PlanPreview
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        if (block.type === "guardrail_warning") {
          return (
            <GuardrailWarning
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        if (block.type === "candidate_eval") {
          return (
            <CandidateEvalCard
              key={i}
              block={block}
              onSendPrompt={onSendPrompt}
            />
          );
        }
        return null;
      })}
    </div>
  );
}

/* ── Match Report Card ─────────────────────────────────────────────────── */

function MatchReportCard({
  block,
  onSendPrompt,
  onViewJob,
}: {
  block: Extract<MessageBlock, { type: "match_report" }>;
  onSendPrompt: (prompt: string) => void;
  onViewJob?: (id: string) => void;
}) {
  const { candidate, rankings, summary } = block;

  return (
    <div className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2">
        <TrendingUpOutlined sx={{ fontSize: 16 }} className="text-indigo-600" />
        <span className="text-sm font-semibold text-indigo-900">
          Match Report — {candidate.name}
        </span>
        {candidate.current_title && (
          <span className="text-xs text-gray-500">({candidate.current_title})</span>
        )}
      </div>

      {/* Rankings */}
      <div className="space-y-2">
        {rankings.map((r, i) => (
          <RankingRow
            key={r.job_id || i}
            ranking={r}
            rank={i + 1}
            onViewJob={onViewJob}
            onDraftEmail={() =>
              onSendPrompt(
                `Draft an outreach email to ${candidate.name} for the ${r.title} role`
              )
            }
          />
        ))}
      </div>

      {/* Summary */}
      {summary && (
        <p className="mt-3 border-t border-indigo-100 pt-2 text-xs leading-relaxed text-gray-600">
          {summary}
        </p>
      )}

      {/* Quick actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() =>
            onSendPrompt(`Draft an outreach email to ${candidate.name}`)
          }
          className="rounded-lg bg-indigo-100 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-200"
        >
          Draft Email
        </button>
        {rankings.length > 0 && (
          <button
            onClick={() =>
              onSendPrompt(
                `Compare ${candidate.name} with other candidates for ${rankings[0].title}`
              )
            }
            className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200"
          >
            Compare Candidates
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Approval Block Card ──────────────────────────────────────────────── */

function ApprovalBlockCard({
  block,
  onSendPrompt,
}: {
  block: ApprovalBlock;
  onSendPrompt: (prompt: string) => void;
}) {
  return (
    <div className="rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50/80 to-white p-4">
      <div className="mb-2 flex items-center gap-2">
        <div className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-100">
          <WarningAmberOutlined sx={{ fontSize: 12 }} className="text-amber-600" />
        </div>
        <span className="text-sm font-semibold text-amber-900">{block.title}</span>
      </div>

      <p className="mb-3 text-xs leading-relaxed text-gray-600">{block.description}</p>

      {block.preview_items.length > 0 && (
        <div className="mb-3 max-h-36 overflow-y-auto rounded-lg border border-amber-100 bg-white">
          {block.preview_items.map((item, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 px-3 py-2 text-xs ${
                i > 0 ? "border-t border-amber-50" : ""
              }`}
            >
              <span className="font-medium text-gray-800">{item.label}</span>
              <span className="text-gray-500">{item.detail}</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => onSendPrompt("approve")}
          className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-amber-700"
        >
          <CheckOutlined sx={{ fontSize: 14 }} />
          {block.approve_label}
        </button>
        <button
          onClick={() => onSendPrompt("cancel workflow")}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <CloseOutlined sx={{ fontSize: 14 }} />
          {block.cancel_label}
        </button>
      </div>
    </div>
  );
}

/* ── Ranking Row ───────────────────────────────────────────────────────── */

function RankingRow({
  ranking,
  rank,
  onViewJob,
  onDraftEmail,
}: {
  ranking: MatchRanking;
  rank: number;
  onViewJob?: (id: string) => void;
  onDraftEmail: () => void;
}) {
  const scorePct = Math.round(ranking.score * 100);
  const scoreColor =
    scorePct >= 70
      ? "text-green-700 bg-green-100"
      : scorePct >= 40
        ? "text-amber-700 bg-amber-100"
        : "text-red-700 bg-red-100";

  return (
    <div className="group rounded-lg border border-gray-100 bg-white p-3 transition-shadow hover:shadow-sm">
      <div className="flex items-start gap-3">
        {/* Rank badge */}
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
          {rank}
        </span>

        {/* Job info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <button
              onClick={() => onViewJob?.(ranking.job_id)}
              className="truncate text-sm font-semibold text-gray-900 hover:text-indigo-700"
            >
              <WorkOutline sx={{ fontSize: 14 }} className="mr-1 inline text-gray-400" />
              {ranking.title}
            </button>
            <span className="shrink-0 text-xs text-gray-400">
              {ranking.company}
            </span>
          </div>

          {ranking.one_liner && (
            <p className="mt-0.5 text-xs text-gray-500">{ranking.one_liner}</p>
          )}

          {/* Strengths & Gaps */}
          <div className="mt-1.5 flex flex-wrap gap-1">
            {ranking.strengths.slice(0, 3).map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-0.5 rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700"
              >
                <StarOutlined sx={{ fontSize: 10 }} />
                {s}
              </span>
            ))}
            {ranking.gaps.slice(0, 2).map((g) => (
              <span
                key={g}
                className="inline-flex items-center gap-0.5 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-600"
              >
                <WarningAmberOutlined sx={{ fontSize: 10 }} />
                {g}
              </span>
            ))}
          </div>
        </div>

        {/* Score + action */}
        <div className="flex shrink-0 flex-col items-end gap-1">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-bold ${scoreColor}`}
          >
            {scorePct}%
          </span>
          <button
            onClick={onDraftEmail}
            className="hidden items-center gap-0.5 text-[10px] text-indigo-600 hover:underline group-hover:flex"
          >
            Draft email <ChevronRightOutlined sx={{ fontSize: 12 }} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Resume Improvement Card ────────────────────────────────────────────── */

const PRIORITY_STYLES = {
  high: "bg-red-50 text-red-700 border-red-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-green-50 text-green-700 border-green-200",
};

const AREA_ICONS: Record<string, string> = {
  skills: "🛠️", experience: "💼", summary: "📝",
  formatting: "📐", keywords: "🔍", projects: "🚀",
};

function ResumeImprovementCard({
  block,
  onSendPrompt,
}: {
  block: ResumeImprovementBlock;
  onSendPrompt: (prompt: string) => void;
}) {
  const high = block.suggestions.filter((s) => s.priority === "high");
  const rest = block.suggestions.filter((s) => s.priority !== "high");

  return (
    <div className="rounded-xl border border-violet-200 bg-gradient-to-br from-violet-50/80 to-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <AutoFixHighOutlined sx={{ fontSize: 16 }} className="text-violet-600" />
        <span className="text-sm font-semibold text-violet-900">
          Resume Improvement{block.job_title ? ` — ${block.job_title}` : ""}
        </span>
        {block.job_company && (
          <span className="text-xs text-gray-400">@ {block.job_company}</span>
        )}
      </div>

      {block.summary && (
        <p className="mb-3 text-xs leading-relaxed text-gray-600">{block.summary}</p>
      )}

      <div className="space-y-2">
        {[...high, ...rest].map((s, i) => (
          <div key={i} className={`rounded-lg border p-3 ${PRIORITY_STYLES[s.priority]}`}>
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-sm">{AREA_ICONS[s.area] || "💡"}</span>
              <span className="text-xs font-semibold capitalize">{s.area}</span>
              <span className={`ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-medium border ${PRIORITY_STYLES[s.priority]}`}>
                {s.priority}
              </span>
            </div>
            <p className="text-xs text-gray-600 mb-1">{s.issue}</p>
            <p className="text-xs font-medium">→ {s.action}</p>
          </div>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onSendPrompt(`Write a cover letter for ${block.job_title}${block.job_company ? ` at ${block.job_company}` : ""}`)}
          className="rounded-lg bg-violet-100 px-3 py-1.5 text-xs font-medium text-violet-700 hover:bg-violet-200"
        >
          Write Cover Letter
        </button>
      </div>
    </div>
  );
}

/* ── Cover Letter Card ──────────────────────────────────────────────────── */

function CoverLetterCard({
  block,
  onSendPrompt,
}: {
  block: CoverLetterBlock;
  onSendPrompt: (prompt: string) => void;
}) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(block.body).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50/80 to-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <DescriptionOutlined sx={{ fontSize: 16 }} className="text-emerald-600" />
        <span className="text-sm font-semibold text-emerald-900">
          Cover Letter{block.job_title ? ` — ${block.job_title}` : ""}
        </span>
        {block.job_company && (
          <span className="text-xs text-gray-400">@ {block.job_company}</span>
        )}
        <button
          onClick={handleCopy}
          className="ml-auto flex items-center gap-1 rounded-lg bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-200"
        >
          <ContentCopyOutlined sx={{ fontSize: 12 }} />
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>

      {block.subject && (
        <div className="mb-2 rounded-lg bg-white border border-emerald-100 px-3 py-1.5">
          <span className="text-[10px] font-semibold uppercase text-gray-400 mr-2">Subject</span>
          <span className="text-xs text-gray-700">{block.subject}</span>
        </div>
      )}

      <div className="max-h-64 overflow-y-auto rounded-lg border border-emerald-100 bg-white p-3">
        <pre className="whitespace-pre-wrap text-xs leading-relaxed text-gray-700 font-sans">{block.body}</pre>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={() => onSendPrompt(`Improve my resume for ${block.job_title}`)}
          className="rounded-lg bg-emerald-100 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-200"
        >
          Improve Resume
        </button>
        <button
          onClick={() => onSendPrompt(`Save ${block.job_title}${block.job_company ? ` at ${block.job_company}` : ""}`)}
          className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200"
        >
          Save Job
        </button>
      </div>
    </div>
  );
}

/* ── Candidate Eval Card (Swarm) ─────────────────────────────────────────── */

const HIRE_REC_STYLES: Record<string, string> = {
  strong_yes: "bg-green-100 text-green-800 border-green-300",
  yes:        "bg-emerald-100 text-emerald-800 border-emerald-300",
  maybe:      "bg-amber-100 text-amber-800 border-amber-300",
  no:         "bg-red-100 text-red-800 border-red-300",
};

const HIRE_REC_LABELS: Record<string, string> = {
  strong_yes: "Strong Hire",
  yes:        "Recommend",
  maybe:      "On the Fence",
  no:         "Not Recommended",
};

const AGENT_ICONS: Record<string, string> = {
  resume:  "📄",
  culture: "🤝",
  risk:    "🛡️",
  market:  "📊",
};

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 75 ? "bg-green-500" :
    score >= 55 ? "bg-amber-400" :
    "bg-red-400";
  return (
    <div className="mt-1 h-1.5 w-full rounded-full bg-gray-100">
      <div
        className={`h-1.5 rounded-full ${color} transition-all`}
        style={{ width: `${score}%` }}
      />
    </div>
  );
}

function DimensionRow({ dim }: { dim: CandidateEvalDimension }) {
  const [expanded, setExpanded] = React.useState(false);
  const scoreColor =
    dim.score >= 75 ? "text-green-700 bg-green-50" :
    dim.score >= 55 ? "text-amber-700 bg-amber-50" :
    "text-red-700 bg-red-50";

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-3">
      <div className="flex items-center gap-2">
        <span className="text-base">{AGENT_ICONS[dim.agent] || "🔍"}</span>
        <span className="text-xs font-semibold text-gray-700 flex-1">{dim.label}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${scoreColor}`}>
          {dim.score}
        </span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-gray-400 hover:text-gray-600 ml-1"
        >
          {expanded ? "▲" : "▼"}
        </button>
      </div>
      <ScoreBar score={dim.score} />
      <p className="mt-1.5 text-xs text-gray-500 italic">{dim.verdict}</p>
      {expanded && dim.findings.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {dim.findings.map((f, i) => (
            <li key={i} className="flex items-start gap-1.5 text-[11px] text-gray-600">
              <span className="mt-0.5 shrink-0 text-gray-300">•</span>
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CandidateEvalCard({
  block,
  onSendPrompt,
}: {
  block: CandidateEvalBlock;
  onSendPrompt: (prompt: string) => void;
}) {
  const recStyle = HIRE_REC_STYLES[block.hire_recommendation] ?? HIRE_REC_STYLES.maybe;
  const recLabel = HIRE_REC_LABELS[block.hire_recommendation] ?? block.hire_recommendation;

  return (
    <div className="rounded-xl border border-blue-200 bg-gradient-to-br from-blue-50/80 to-white p-4">
      {/* Header */}
      <div className="mb-3 flex items-center gap-2 flex-wrap">
        <span className="text-base">🧠</span>
        <span className="text-sm font-semibold text-blue-900">
          Swarm Evaluation — {block.candidate.name}
        </span>
        {block.candidate.current_title && (
          <span className="text-xs text-gray-400">({block.candidate.current_title})</span>
        )}
        {block.job_title && (
          <span className="ml-auto text-xs text-gray-400">
            for {block.job_title}{block.job_company ? ` @ ${block.job_company}` : ""}
          </span>
        )}
      </div>

      {/* Overall score + recommendation */}
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-full border-2 border-blue-200 bg-white">
          <span className="text-lg font-bold text-blue-700">{block.overall_score}</span>
          <span className="text-[9px] text-gray-400 uppercase">/ 100</span>
        </div>
        <div className="flex-1">
          <span className={`inline-block rounded-full border px-3 py-1 text-xs font-semibold ${recStyle}`}>
            {recLabel}
          </span>
          {block.synthesis && (
            <p className="mt-1.5 text-xs leading-relaxed text-gray-600">{block.synthesis}</p>
          )}
        </div>
      </div>

      {/* 4 dimension rows */}
      <div className="space-y-2">
        {block.dimensions.map((dim) => (
          <DimensionRow key={dim.agent} dim={dim} />
        ))}
      </div>

      {/* Actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={() => onSendPrompt(`Draft an outreach email to ${block.candidate.name}`)}
          className="rounded-lg bg-blue-100 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-200"
        >
          Draft Email
        </button>
        <button
          onClick={() => onSendPrompt(`What jobs match ${block.candidate.name}?`)}
          className="rounded-lg bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200"
        >
          Match to Jobs
        </button>
      </div>
    </div>
  );
}
