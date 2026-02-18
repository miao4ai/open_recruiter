import { useCallback, useEffect, useRef, useState } from "react";
import { SearchOutlined, CloseOutlined, AutoAwesomeOutlined } from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
import { searchByText } from "../lib/api";
import type { Job, Candidate } from "../types";

type Collection = "jobs" | "candidates";

export interface SearchResult<T> {
  record: T;
  similarity_score: number;
}

interface Props<T> {
  collection: Collection;
  placeholder?: string;
  onResults: (results: SearchResult<T>[] | null) => void;
}

export default function SemanticSearchBar<T extends Job | Candidate>({
  collection,
  placeholder,
  onResults,
}: Props<T>) {
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [focused, setFocused] = useState(false);
  const [resultCount, setResultCount] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const abortRef = useRef<AbortController>(undefined);
  const inputRef = useRef<HTMLInputElement>(null);

  const doSearch = useCallback(
    async (text: string) => {
      // Cancel any in-flight request
      abortRef.current?.abort();

      if (!text.trim()) {
        onResults(null);
        setResultCount(null);
        setSearching(false);
        return;
      }

      setSearching(true);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const data = await searchByText(text, collection, 20);
        if (!controller.signal.aborted) {
          const results = data as SearchResult<T>[];
          onResults(results);
          setResultCount(results.length);
          setSearching(false);
        }
      } catch {
        if (!controller.signal.aborted) {
          setSearching(false);
        }
      }
    },
    [collection, onResults],
  );

  // Debounced search on input change
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (!query.trim()) {
      onResults(null);
      setResultCount(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(() => doSearch(query), 300);
    return () => clearTimeout(debounceRef.current);
  }, [query, doSearch, onResults]);

  const clear = () => {
    setQuery("");
    onResults(null);
    setResultCount(null);
    inputRef.current?.focus();
  };

  const isActive = query.trim().length > 0;

  return (
    <div className="relative">
      {/* Glow effect when focused */}
      <div
        className={`absolute -inset-0.5 rounded-xl bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 opacity-0 blur transition-opacity duration-300 ${
          focused ? "opacity-20" : ""
        }`}
      />

      <div
        className={`relative flex items-center gap-2 rounded-xl border bg-white px-4 py-2.5 transition-all duration-200 ${
          focused
            ? "border-blue-400 shadow-lg shadow-blue-100"
            : "border-gray-200 shadow-sm hover:border-gray-300"
        }`}
      >
        {/* Search / loading icon */}
        <div className="flex-shrink-0">
          {searching ? (
            <CircularProgress size={18} className="text-blue-500" />
          ) : (
            <SearchOutlined
              sx={{ fontSize: 18 }}
              className={`transition-colors ${
                isActive ? "text-blue-500" : "text-gray-400"
              }`}
            />
          )}
        </div>

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder ?? `Semantic search ${collection}...`}
          className="min-w-0 flex-1 bg-transparent text-sm text-gray-900 placeholder-gray-400 outline-none"
        />

        {/* Result count badge + clear button */}
        <div className="flex flex-shrink-0 items-center gap-1.5">
          {isActive && resultCount !== null && !searching && (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-600">
              <AutoAwesomeOutlined sx={{ fontSize: 12 }} />
              {resultCount} found
            </span>
          )}
          {isActive && (
            <button
              onClick={clear}
              className="rounded-md p-0.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            >
              <CloseOutlined sx={{ fontSize: 16 }} />
            </button>
          )}
        </div>
      </div>

      {/* Subtle hint */}
      {focused && !isActive && (
        <p className="absolute -bottom-5 left-4 text-[10px] text-gray-400">
          AI-powered semantic search — try natural language queries
        </p>
      )}
    </div>
  );
}
