import { LightbulbOutlined } from "@mui/icons-material";
import type { Suggestion } from "../types";

interface Props {
  suggestions: Suggestion[];
  onSelect: (prompt: string) => void;
}

export default function SmartActionBar({ suggestions, onSelect }: Props) {
  if (suggestions.length === 0) return null;

  return (
    <div className="flex items-center gap-2 px-1 py-2">
      <LightbulbOutlined sx={{ fontSize: 14 }} className="shrink-0 text-amber-500" />
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button
            key={s.label}
            onClick={() => onSelect(s.prompt)}
            className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium text-gray-600 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
          >
            {s.icon && <span className="mr-1">{s.icon}</span>}
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
