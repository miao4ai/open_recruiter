import { Briefcase, Check, ChevronRight, Star, TrendingUp, AlertTriangle, X } from "lucide-react";
import type { MessageBlock, MatchRanking, ApprovalBlock } from "../types";

interface Props {
  blocks: MessageBlock[];
  onSendPrompt: (prompt: string) => void;
  onViewCandidate?: (id: string) => void;
  onViewJob?: (id: string) => void;
}

export default function MessageBlocks({ blocks, onSendPrompt, onViewJob }: Props) {
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
        <TrendingUp className="h-4 w-4 text-indigo-600" />
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
          <AlertTriangle className="h-3 w-3 text-amber-600" />
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
          <Check className="h-3.5 w-3.5" />
          {block.approve_label}
        </button>
        <button
          onClick={() => onSendPrompt("cancel workflow")}
          className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          <X className="h-3.5 w-3.5" />
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
              <Briefcase className="mr-1 inline h-3.5 w-3.5 text-gray-400" />
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
                <Star className="h-2.5 w-2.5" fill="currentColor" />
                {s}
              </span>
            ))}
            {ranking.gaps.slice(0, 2).map((g) => (
              <span
                key={g}
                className="inline-flex items-center gap-0.5 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-600"
              >
                <AlertTriangle className="h-2.5 w-2.5" />
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
            Draft email <ChevronRight className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
}
