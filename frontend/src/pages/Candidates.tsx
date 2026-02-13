import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Upload, Users } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { listCandidates, listJobs, uploadResume } from "../lib/api";
import type { CandidateStatus } from "../types";

const STATUS_COLORS: Record<CandidateStatus, string> = {
  new: "bg-gray-100 text-gray-700",
  contacted: "bg-blue-100 text-blue-700",
  replied: "bg-emerald-100 text-emerald-700",
  screening: "bg-amber-100 text-amber-700",
  interview_scheduled: "bg-purple-100 text-purple-700",
  interviewed: "bg-indigo-100 text-indigo-700",
  offer_sent: "bg-cyan-100 text-cyan-700",
  hired: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-700",
  withdrawn: "bg-gray-200 text-gray-600",
};

export default function Candidates() {
  const { data: candidates, refresh } = useApi(
    useCallback(() => listCandidates(), [])
  );
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [uploadError, setUploadError] = useState("");

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError("");
    try {
      await uploadResume(file, selectedJobId);
      refresh();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 409 && detail) {
        setUploadError(detail);
      } else {
        setUploadError("Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          All Candidates{" "}
          <span className="text-sm font-normal text-gray-400">
            ({candidates?.length ?? 0})
          </span>
        </h2>
        <div className="flex items-center gap-2">
          {/* Job selector for upload */}
          <select
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Link to Job (optional)</option>
            {jobs?.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} — {j.company}
              </option>
            ))}
          </select>
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            <Upload className="h-4 w-4" />
            {uploading ? "Uploading..." : "Import Resume"}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              className="hidden"
              onChange={handleUpload}
            />
          </label>
        </div>
      </div>

      {/* Upload error */}
      {uploadError && (
        <div className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <span>{uploadError}</span>
          <button onClick={() => setUploadError("")} className="ml-3 text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      {/* Table */}
      {candidates && candidates.length > 0 ? (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-xs uppercase text-gray-500">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Job</th>
                <th className="px-4 py-3 font-medium">Score</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Skills</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((c) => {
                const linkedJob = jobs?.find((j) => j.id === c.job_id);
                return (
                  <tr
                    key={c.id}
                    className="border-b border-gray-50 transition-colors hover:bg-gray-50"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/candidates/${c.id}`}
                        className="font-medium text-blue-600 hover:underline"
                      >
                        {c.name || "Unnamed"}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {c.email || "\u2014"}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.current_title || "\u2014"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {linkedJob ? linkedJob.title : "\u2014"}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBar score={c.match_score} />
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {c.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {c.skills.slice(0, 3).map((s) => (
                          <span
                            key={s}
                            className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600"
                          >
                            {s}
                          </span>
                        ))}
                        {c.skills.length > 3 && (
                          <span className="text-xs text-gray-400">
                            +{c.skills.length - 3}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-12 text-center">
          <Users className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-gray-500">
            No candidates yet. Click <strong>Import Resume</strong> to add one.
          </p>
        </div>
      )}
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-16 rounded-full bg-gray-200">
        <div
          className={`h-2 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500">{pct}%</span>
    </div>
  );
}
