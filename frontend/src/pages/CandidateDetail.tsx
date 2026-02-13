import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Mail,
  Trash2,
  Pencil,
  Save,
  X,
  Sparkles,
  Loader2,
  Briefcase,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  getCandidate,
  listEmails,
  listJobs,
  updateCandidate,
  deleteCandidate,
  matchCandidates,
  composeEmail,
} from "../lib/api";
import type { Candidate, TopJob } from "../types";

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

  // Match analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [typewriterText, setTypewriterText] = useState("");
  const [typewriterDone, setTypewriterDone] = useState(true);

  if (loading) {
    return <p className="text-sm text-gray-400">Loading...</p>;
  }
  if (!candidate) {
    return <p className="text-sm text-red-500">Candidate not found.</p>;
  }

  const hasAnalysis = !!(candidate.match_reasoning);
  const topJobs: TopJob[] = candidate.top_jobs ?? [];

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

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this candidate?")) return;
    await deleteCandidate(id!);
    navigate("/candidates");
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setTypewriterText("");
    setTypewriterDone(false);
    try {
      // matchCandidates now triggers _auto_match_all_jobs on the backend
      const results = await matchCandidates(candidate.job_id || "", [candidate.id]);
      const result = results[0];
      if (result?.reasoning) {
        setTypewriterText(result.reasoning);
      }
      refresh();
    } finally {
      setAnalyzing(false);
    }
  };

  const updateField = (key: string, value: string | string[] | number | null) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  // Determine which reasoning text to show
  const showTypewriter = !typewriterDone && typewriterText;
  const reasoningText = showTypewriter ? typewriterText : candidate.match_reasoning;

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
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold">Match Analysis</h3>
          </div>

          {/* Candidate Summary */}
          {candidate.resume_summary && (
            <div className="mb-4">
              <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
                Summary
              </h4>
              <p className="text-sm leading-relaxed text-gray-600">
                {candidate.resume_summary}
              </p>
            </div>
          )}

          {/* Top Matching Jobs */}
          <div className="mb-4">
            <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">
              Top Matching Jobs
            </h4>
            {topJobs.length > 0 ? (
              <div className="space-y-2">
                {topJobs.map((tj, i) => {
                  const pct = Math.round(tj.score * 100);
                  const isTop = i === 0;
                  return (
                    <div
                      key={tj.job_id}
                      className={`flex items-center gap-3 rounded-lg border p-3 ${
                        isTop
                          ? "border-blue-200 bg-blue-50/50"
                          : "border-gray-100 bg-gray-50/50"
                      }`}
                    >
                      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-500">
                        #{i + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className={`truncate text-sm font-medium ${isTop ? "text-blue-700" : "text-gray-700"}`}>
                          {tj.title}
                        </p>
                        {tj.company && (
                          <p className="truncate text-xs text-gray-500">
                            {tj.company}
                          </p>
                        )}
                      </div>
                      <div
                        className={`flex-shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                          pct >= 70
                            ? "bg-emerald-100 text-emerald-700"
                            : pct >= 40
                              ? "bg-amber-100 text-amber-700"
                              : "bg-red-100 text-red-600"
                        }`}
                      >
                        {pct}%
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-400">
                <Briefcase className="h-4 w-4" />
                No jobs in the system yet.
              </div>
            )}
          </div>

          {/* AI Analysis (reasoning, strengths, gaps) */}
          {(hasAnalysis || analyzing || showTypewriter) ? (
            <>
              <div className="mb-3">
                <h4 className="mb-1 text-xs font-medium uppercase text-gray-500">
                  AI Analysis
                </h4>
                <p className="whitespace-pre-line text-sm text-gray-600">
                  {showTypewriter ? (
                    <TypewriterText
                      text={typewriterText}
                      speed={18}
                      onComplete={() => setTypewriterDone(true)}
                    />
                  ) : (
                    reasoningText || "No analysis yet."
                  )}
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
                <div className="mb-4">
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
            </>
          ) : (
            <p className="mb-4 text-sm text-gray-400">
              {topJobs.length > 0
                ? "Click below to generate a detailed AI analysis."
                : "Add jobs to the system to see match analysis."}
            </p>
          )}

          {/* Re-analyze button */}
          {topJobs.length > 0 && (
            <button
              onClick={handleAnalyze}
              disabled={analyzing}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-violet-600 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:from-violet-700 hover:to-blue-700 disabled:opacity-50"
            >
              {analyzing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  {hasAnalysis ? "Re-analyze" : "Generate Analysis"}
                </>
              )}
            </button>
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
              onClick={handleDelete}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -- Typewriter Effect --------------------------------------------------- */

function TypewriterText({
  text,
  speed = 18,
  onComplete,
}: {
  text: string;
  speed?: number;
  onComplete?: () => void;
}) {
  const [displayed, setDisplayed] = useState("");
  const indexRef = useRef(0);

  useEffect(() => {
    if (!text) return;
    setDisplayed("");
    indexRef.current = 0;

    const timer = setInterval(() => {
      indexRef.current += 1;
      setDisplayed(text.slice(0, indexRef.current));
      if (indexRef.current >= text.length) {
        clearInterval(timer);
        onComplete?.();
      }
    }, speed);

    return () => clearInterval(timer);
  }, [text, speed]);

  return (
    <span>
      {displayed}
      {displayed.length < text.length && (
        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-gray-400" />
      )}
    </span>
  );
}

/* -- Edit Field ---------------------------------------------------------- */

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
