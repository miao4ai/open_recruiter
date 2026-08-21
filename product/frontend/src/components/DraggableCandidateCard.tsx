import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import type { Candidate } from "../types";

interface Props {
  candidate: Candidate;
  dragId?: string;
  jobLabel?: string;
  onViewCandidate: (id: string) => void;
}

export default function DraggableCandidateCard({ candidate: c, dragId, jobLabel, onViewCandidate }: Props) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: dragId ?? c.id,
    data: { candidate: c },
  });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex cursor-grab items-start gap-3 rounded-lg border border-gray-100 p-3 text-left hover:border-gray-200 hover:shadow-sm active:cursor-grabbing"
    >
      <div className="min-w-0 flex-1" onClick={() => onViewCandidate(c.id)}>
        <p className="font-medium text-gray-900">{c.name}</p>
        <p className="truncate text-xs text-gray-500">
          {c.current_title || "N/A"}
          {c.current_company ? ` at ${c.current_company}` : ""}
        </p>
        {jobLabel && (
          <p className="mt-0.5 truncate text-[11px] font-medium text-blue-600">
            {jobLabel}
          </p>
        )}
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
    </div>
  );
}
