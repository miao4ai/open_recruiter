import { useCallback, useRef, useState } from "react";
import {
  SearchOutlined, LocationOnOutlined, BusinessOutlined, AttachMoneyOutlined, AccessTimeOutlined, WorkOutline,
  ExpandMoreOutlined, ExpandLessOutlined, CloseOutlined, UploadOutlined, DeleteOutline,
} from "@mui/icons-material";
import { CircularProgress } from "@mui/material";
import { useApi } from "../hooks/useApi";
import { seekerListJobs, seekerUploadJd, seekerDeleteJob } from "../lib/api";
import type { Job } from "../types";

export default function JobSeekerJobs() {
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const { data: jobs, loading, refresh } = useApi(
    useCallback(() => seekerListJobs(searchTerm), [searchTerm]),
  );
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

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

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await seekerUploadJd(file);
      refresh();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await seekerDeleteJob(id);
    refresh();
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">My Jobs</h1>
          <p className="mt-1 text-sm text-gray-500">
            Upload job descriptions to track positions you're interested in
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.doc,.txt"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-pink-500 px-4 py-2
              text-sm font-medium text-white hover:bg-pink-600 disabled:opacity-50"
          >
            {uploading ? (
              <CircularProgress size={16} />
            ) : (
              <UploadOutlined className="h-4 w-4" />
            )}
            {uploading ? "Parsing..." : "Upload JD"}
          </button>
        </div>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <SearchOutlined className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
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
              <CloseOutlined className="h-4 w-4" />
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
          <CircularProgress size={24} sx={{ color: 'rgb(244 114 182)' }} />
        </div>
      )}

      {/* Results count */}
      {!loading && jobs && (
        <p className="text-sm text-gray-500">
          {jobs.length} job{jobs.length !== 1 ? "s" : ""} saved
          {searchTerm ? ` matching "${searchTerm}"` : ""}
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
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && jobs && jobs.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-12 text-center">
          <WorkOutline className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-gray-500">
            {searchTerm
              ? "No jobs match your search. Try different keywords."
              : "No jobs yet. Upload a JD to get started!"}
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
  onDelete,
}: {
  job: Job;
  expanded: boolean;
  onToggle: () => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
}) {
  return (
    <div className="group rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Main row */}
      <button
        onClick={onToggle}
        className="flex w-full items-start gap-4 p-5 text-left"
      >
        {/* Icon */}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-pink-50">
          <WorkOutline className="h-5 w-5 text-pink-500" />
        </div>

        {/* Info */}
        <div className="min-w-0 flex-1">
          <h3 className="font-semibold text-gray-900">
            {job.title || "Untitled Position"}
          </h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            {job.company && (
              <span className="inline-flex items-center gap-1">
                <BusinessOutlined className="h-3.5 w-3.5" />
                {job.company}
              </span>
            )}
            {job.location && (
              <span className="inline-flex items-center gap-1">
                <LocationOnOutlined className="h-3.5 w-3.5" />
                {job.location}
                {job.remote && " (Remote)"}
              </span>
            )}
            {!job.location && job.remote && (
              <span className="inline-flex items-center gap-1">
                <LocationOnOutlined className="h-3.5 w-3.5" />
                Remote
              </span>
            )}
            {job.salary_range && (
              <span className="inline-flex items-center gap-1">
                <AttachMoneyOutlined className="h-3.5 w-3.5" />
                {job.salary_range}
              </span>
            )}
            {job.posted_date && (
              <span className="inline-flex items-center gap-1">
                <AccessTimeOutlined className="h-3.5 w-3.5" />
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

        {/* Actions */}
        <div className="flex shrink-0 items-center gap-2 pt-1">
          <span
            role="button"
            onClick={(e) => onDelete(job.id, e)}
            className="text-gray-300 opacity-0 transition-opacity hover:text-red-500 group-hover:opacity-100"
            title="Delete"
          >
            <DeleteOutline className="h-4 w-4" />
          </span>
          {expanded ? (
            <ExpandLessOutlined className="h-5 w-5 text-gray-400" />
          ) : (
            <ExpandMoreOutlined className="h-5 w-5 text-gray-400" />
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
