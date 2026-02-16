import { useCallback, useState } from "react";
import {
  Search, Loader2, MapPin, Building2, DollarSign, Clock, Briefcase, ChevronDown, ChevronUp, X,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { seekerListJobs } from "../lib/api";
import type { Job } from "../types";

export default function JobSeekerJobs() {
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const { data: jobs, loading } = useApi(
    useCallback(() => seekerListJobs(searchTerm), [searchTerm]),
  );
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const handleSearch = () => {
    setSearchTerm(query.trim());
  };

  const handleClear = () => {
    setQuery("");
    setSearchTerm("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Job Search</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse open positions from recruiters
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search by title, company, skills, location..."
            className="w-full rounded-xl border border-gray-300 py-2.5 pl-10 pr-9 text-sm
              focus:border-pink-500 focus:outline-none focus:ring-1 focus:ring-pink-500"
          />
          {query && (
            <button
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <button
          onClick={handleSearch}
          className="rounded-xl bg-pink-500 px-5 py-2.5 text-sm font-medium text-white
            hover:bg-pink-600"
        >
          Search
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-pink-400" />
        </div>
      )}

      {/* Results count */}
      {!loading && jobs && (
        <p className="text-sm text-gray-500">
          {jobs.length} job{jobs.length !== 1 ? "s" : ""} found
          {searchTerm ? ` for "${searchTerm}"` : ""}
        </p>
      )}

      {/* Job list */}
      {!loading && jobs && jobs.length > 0 && (
        <div className="space-y-3">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              expanded={expandedId === job.id}
              onToggle={() =>
                setExpandedId(expandedId === job.id ? null : job.id)
              }
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && jobs && jobs.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-12 text-center">
          <Briefcase className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-gray-500">
            {searchTerm
              ? "No jobs match your search. Try different keywords."
              : "No jobs posted yet. Check back later!"}
          </p>
        </div>
      )}
    </div>
  );
}

/* ── Job Card ─────────────────────────────────────────────────────────── */

function JobCard({
  job,
  expanded,
  onToggle,
}: {
  job: Job;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Main row */}
      <button
        onClick={onToggle}
        className="flex w-full items-start gap-4 p-5 text-left"
      >
        {/* Icon */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-pink-50">
          <Briefcase className="h-5 w-5 text-pink-500" />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-gray-900">
            {job.title || "Untitled Position"}
          </h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            {job.company && (
              <span className="inline-flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5" />
                {job.company}
              </span>
            )}
            {job.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {job.location}
                {job.remote && " (Remote)"}
              </span>
            )}
            {!job.location && job.remote && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                Remote
              </span>
            )}
            {job.salary_range && (
              <span className="inline-flex items-center gap-1">
                <DollarSign className="h-3.5 w-3.5" />
                {job.salary_range}
              </span>
            )}
            {job.posted_date && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" />
                {job.posted_date}
              </span>
            )}
          </div>

          {/* Skill pills */}
          {job.required_skills && job.required_skills.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {job.required_skills.slice(0, 6).map((s) => (
                <span
                  key={s}
                  className="rounded-full bg-pink-50 px-2.5 py-0.5 text-xs font-medium text-pink-700"
                >
                  {s}
                </span>
              ))}
              {job.required_skills.length > 6 && (
                <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500">
                  +{job.required_skills.length - 6}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Expand icon */}
        <div className="shrink-0 pt-1 text-gray-400">
          {expanded ? (
            <ChevronUp className="h-5 w-5" />
          ) : (
            <ChevronDown className="h-5 w-5" />
          )}
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5 pt-4">
          {job.summary && (
            <div className="mb-4">
              <h4 className="mb-1 text-sm font-semibold text-gray-700">
                Summary
              </h4>
              <p className="whitespace-pre-wrap text-sm text-gray-600">
                {job.summary}
              </p>
            </div>
          )}

          {job.experience_years != null && (
            <p className="mb-3 text-sm text-gray-600">
              <span className="font-medium">Experience:</span>{" "}
              {job.experience_years}+ years
            </p>
          )}

          {job.preferred_skills && job.preferred_skills.length > 0 && (
            <div className="mb-3">
              <h4 className="mb-1 text-sm font-semibold text-gray-700">
                Nice to have
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {job.preferred_skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Full description if available via raw_text (we stripped it in list, but detail could have it) */}
          {job.raw_text && (
            <div>
              <h4 className="mb-1 text-sm font-semibold text-gray-700">
                Full Description
              </h4>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-600">
                {job.raw_text}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
