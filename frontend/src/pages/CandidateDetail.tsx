import { useCallback, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Mail,
  XCircle,
  Pencil,
  Save,
  X,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  getCandidate,
  listEmails,
  listJobs,
  updateCandidate,
  composeEmail,
} from "../lib/api";
import type { Candidate } from "../types";

export default function CandidateDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: candidate, loading, refresh } = useApi(
    useCallback(() => getCandidate(id!), [id])
  );
  const { data: emails } = useApi(
    useCallback(() => listEmails(id!), [id])
  );
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Candidate>>({});
  const [saving, setSaving] = useState(false);

  if (loading) {
    return <p className="text-sm text-gray-400">Loading...</p>;
  }
  if (!candidate) {
    return <p className="text-sm text-red-500">Candidate not found.</p>;
  }

  const scorePct = Math.round(candidate.match_score * 100);

  const startEdit = () => {
    setForm({
      name: candidate.name,
      email: candidate.email,
      phone: candidate.phone,
      current_title: candidate.current_title,
      current_company: candidate.current_company,
      skills: candidate.skills,
      experience_years: candidate.experience_years,
      location: candidate.location,
      notes: candidate.notes,
      job_id: candidate.job_id,
    });
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateCandidate(id!, form);
      setEditing(false);
      refresh();
    } finally {
      setSaving(false);
    }
  };

  const handleSendEmail = async () => {
    await composeEmail({
      to_email: candidate.email,
      subject: `Exciting Career Opportunity`,
      body: `Hi ${candidate.name || "there"},\n\nI came across your profile and was very impressed by your background and experience.\n\nWould you be open to a brief conversation? I'd love to share more details about an opportunity that I think would be a great fit.\n\nLooking forward to hearing from you!\n\nBest regards`,
      email_type: "outreach",
      candidate_id: candidate.id,
      candidate_name: candidate.name,
    });
    navigate("/outreach");
  };

  const handleReject = async () => {
    await updateCandidate(id!, { status: "rejected" });
    refresh();
  };

  const updateField = (key: string, value: string | string[] | number | null) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

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
          <div className="flex items-start justify-between">
            <h2 className="text-xl font-semibold">
              {candidate.name || "Unnamed"}
            </h2>
            {!editing ? (
              <button
                onClick={startEdit}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
              >
                <Pencil className="h-3.5 w-3.5" /> Edit
              </button>
            ) : (
              <div className="flex gap-1">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" /> {saving ? "..." : "Save"}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>

          {editing ? (
            <div className="mt-4 space-y-3">
              <EditField
                label="Name"
                value={form.name ?? ""}
                onChange={(v) => updateField("name", v)}
              />
              <EditField
                label="Email"
                value={form.email ?? ""}
                onChange={(v) => updateField("email", v)}
              />
              <EditField
                label="Phone"
                value={form.phone ?? ""}
                onChange={(v) => updateField("phone", v)}
              />
              <EditField
                label="Title"
                value={form.current_title ?? ""}
                onChange={(v) => updateField("current_title", v)}
              />
              <EditField
                label="Company"
                value={form.current_company ?? ""}
                onChange={(v) => updateField("current_company", v)}
              />
              <EditField
                label="Location"
                value={form.location ?? ""}
                onChange={(v) => updateField("location", v)}
              />
              <EditField
                label="Experience (years)"
                value={form.experience_years?.toString() ?? ""}
                onChange={(v) =>
                  updateField(
                    "experience_years",
                    v ? parseInt(v, 10) || null : null
                  )
                }
                type="number"
              />
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">
                  Linked Job
                </label>
                <select
                  value={form.job_id ?? ""}
                  onChange={(e) => updateField("job_id", e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">— None —</option>
                  {jobs?.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.title} — {j.company}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">
                  Skills (comma separated)
                </label>
                <input
                  value={(form.skills ?? []).join(", ")}
                  onChange={(e) =>
                    updateField(
                      "skills",
                      e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean)
                    )
                  }
                  className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-500">
                  Notes
                </label>
                <textarea
                  value={form.notes ?? ""}
                  onChange={(e) => updateField("notes", e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          ) : (
            <>
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

              {/* Linked Job */}
              {candidate.job_id && (
                <div className="mt-4">
                  <h3 className="mb-1 text-xs font-medium uppercase text-gray-500">
                    Linked Job
                  </h3>
                  <p className="text-sm text-gray-600">
                    {jobs?.find((j) => j.id === candidate.job_id)?.title ?? candidate.job_id}
                  </p>
                </div>
              )}

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
            </>
          )}
        </div>

        {/* Middle: match analysis */}
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <h3 className="mb-4 font-semibold">Match Analysis</h3>

          {/* Score ring */}
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

          {/* Candidate Summary */}
          {candidate.resume_summary && (
            <div className="mb-4">
              <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
                Candidate Summary
              </h4>
              <p className="text-sm leading-relaxed text-gray-600">
                {candidate.resume_summary}
              </p>
            </div>
          )}

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
            <button
              onClick={handleSendEmail}
              className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
            >
              <Mail className="h-3.5 w-3.5" /> Send Email
            </button>
            <button
              onClick={handleReject}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              <XCircle className="h-3.5 w-3.5" /> Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-gray-500">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-300 px-2 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    </div>
  );
}
