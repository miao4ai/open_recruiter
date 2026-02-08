import { useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Mail, Calendar, XCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { getCandidate, listEmails } from "../lib/api";

export default function CandidateDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: candidate, loading } = useApi(
    useCallback(() => getCandidate(id!), [id])
  );
  const { data: emails } = useApi(
    useCallback(() => listEmails(id!), [id])
  );

  if (loading) {
    return <p className="text-sm text-gray-400">Loading...</p>;
  }
  if (!candidate) {
    return <p className="text-sm text-red-500">Candidate not found.</p>;
  }

  const scorePct = Math.round(candidate.match_score * 100);

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/candidates"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Candidates
      </Link>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: info card */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h2 className="text-xl font-semibold">
            {candidate.name || "Unnamed"}
          </h2>
          {candidate.current_title && (
            <p className="text-sm text-gray-500">
              {candidate.current_title}
              {candidate.current_company
                ? ` at ${candidate.current_company}`
                : ""}
            </p>
          )}

          <div className="mt-4 space-y-2 text-sm">
            {candidate.email && (
              <p>
                <span className="text-gray-500">Email:</span>{" "}
                {candidate.email}
              </p>
            )}
            {candidate.phone && (
              <p>
                <span className="text-gray-500">Phone:</span>{" "}
                {candidate.phone}
              </p>
            )}
            {candidate.location && (
              <p>
                <span className="text-gray-500">Location:</span>{" "}
                {candidate.location}
              </p>
            )}
            {candidate.experience_years != null && (
              <p>
                <span className="text-gray-500">Experience:</span>{" "}
                {candidate.experience_years} years
              </p>
            )}
          </div>

          {/* Skills */}
          {candidate.skills.length > 0 && (
            <div className="mt-4">
              <h3 className="mb-2 text-xs font-medium uppercase text-gray-500">
                Skills
              </h3>
              <div className="flex flex-wrap gap-1">
                {candidate.skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Notes */}
          <div className="mt-4">
            <h3 className="mb-1 text-xs font-medium uppercase text-gray-500">
              Notes
            </h3>
            <p className="text-sm text-gray-600">
              {candidate.notes || "No notes yet."}
            </p>
          </div>
        </div>

        {/* Middle: match analysis */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 font-semibold">Match Analysis</h3>

          {/* Score ring (simplified) */}
          <div className="mb-4 flex items-center gap-4">
            <div
              className={`flex h-16 w-16 items-center justify-center rounded-full border-4 text-lg font-bold ${
                scorePct >= 70
                  ? "border-emerald-500 text-emerald-600"
                  : scorePct >= 40
                    ? "border-amber-500 text-amber-600"
                    : "border-red-400 text-red-500"
              }`}
            >
              {scorePct}%
            </div>
            <p className="text-sm text-gray-500">
              {candidate.match_reasoning || "No match analysis yet."}
            </p>
          </div>

          {/* Strengths */}
          {candidate.strengths.length > 0 && (
            <div className="mb-3">
              <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
                Strengths
              </h4>
              <ul className="list-inside list-disc space-y-1 text-sm text-emerald-700">
                {candidate.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Gaps */}
          {candidate.gaps.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
                Gaps
              </h4>
              <ul className="list-inside list-disc space-y-1 text-sm text-red-600">
                {candidate.gaps.map((g, i) => (
                  <li key={i}>{g}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right: communication timeline */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 font-semibold">Communication</h3>
          {emails && emails.length > 0 ? (
            <div className="space-y-3">
              {emails.map((e) => (
                <div
                  key={e.id}
                  className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm"
                >
                  <p className="font-medium">{e.subject}</p>
                  <p className="mt-1 text-xs text-gray-500">
                    {e.email_type} &middot;{" "}
                    {e.sent ? `Sent ${e.sent_at ?? ""}` : "Draft"}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No emails yet.</p>
          )}

          {/* Action buttons */}
          <div className="mt-4 flex flex-wrap gap-2">
            <button className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">
              <Mail className="h-3.5 w-3.5" /> Send Email
            </button>
            <button className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
              <Calendar className="h-3.5 w-3.5" /> Schedule
            </button>
            <button className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">
              <XCircle className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
