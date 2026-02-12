import { useCallback, useState } from "react";
import { Plus, Trash2, Users, Pencil, X, Save } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { listJobs, createJob, updateJob, deleteJob } from "../lib/api";
import type { Job } from "../types";

export default function Jobs() {
  const { data: jobs, refresh } = useApi(useCallback(() => listJobs(), []));
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [postedDate, setPostedDate] = useState("");
  const [rawText, setRawText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const resetForm = () => {
    setTitle("");
    setCompany("");
    setPostedDate("");
    setRawText("");
  };

  const handleCreate = async () => {
    if (!rawText.trim()) return;
    setSubmitting(true);
    try {
      await createJob({ title, company, posted_date: postedDate, raw_text: rawText });
      resetForm();
      setShowForm(false);
      refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const startEdit = (job: Job) => {
    setEditingJob(job);
    setTitle(job.title);
    setCompany(job.company);
    setPostedDate(job.posted_date);
    setRawText(job.raw_text);
    setShowForm(false);
  };

  const handleUpdate = async () => {
    if (!editingJob) return;
    setSubmitting(true);
    try {
      await updateJob(editingJob.id, {
        title,
        company,
        posted_date: postedDate,
        raw_text: rawText,
      });
      setEditingJob(null);
      resetForm();
      refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const cancelEdit = () => {
    setEditingJob(null);
    resetForm();
  };

  const handleDelete = async (id: string) => {
    await deleteJob(id);
    refresh();
  };

  const isFormOpen = showForm || editingJob;

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          All Jobs{" "}
          <span className="text-sm font-normal text-gray-400">
            ({jobs?.length ?? 0})
          </span>
        </h2>
        {!isFormOpen && (
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            New Job
          </button>
        )}
      </div>

      {/* Create / Edit form */}
      {isFormOpen && (
        <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
          <h3 className="font-semibold">
            {editingJob ? "Edit Job" : "New Job"}
          </h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Job Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. Senior Frontend Engineer"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Company
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. Acme Corp"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Posted Date
              </label>
              <input
                type="date"
                value={postedDate}
                onChange={(e) => setPostedDate(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Job Description
            </label>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={8}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Paste the full job description here..."
            />
          </div>
          <div className="flex gap-2">
            {editingJob ? (
              <>
                <button
                  onClick={handleUpdate}
                  disabled={submitting}
                  className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  <Save className="h-4 w-4" />
                  {submitting ? "Saving..." : "Save Changes"}
                </button>
                <button
                  onClick={cancelEdit}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleCreate}
                  disabled={submitting || !rawText.trim()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Creating..." : "Create Job"}
                </button>
                <button
                  onClick={() => { setShowForm(false); resetForm(); }}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Job list */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {jobs?.map((job) => (
          <div
            key={job.id}
            className="group rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-semibold text-gray-900">
                  {job.title || "Untitled"}
                </h3>
                {job.company && (
                  <p className="mt-0.5 text-sm text-gray-500">{job.company}</p>
                )}
                {job.posted_date && (
                  <p className="mt-0.5 text-xs text-gray-400">Posted: {job.posted_date}</p>
                )}
              </div>
              <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  onClick={() => startEdit(job)}
                  className="text-gray-300 hover:text-blue-500"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDelete(job.id)}
                  className="text-gray-300 hover:text-red-500"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
            {job.required_skills.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1">
                {job.required_skills.slice(0, 4).map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
                  >
                    {s}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-3 flex items-center gap-1 text-xs text-gray-400">
              <Users className="h-3.5 w-3.5" />
              {job.candidate_count} candidate
              {job.candidate_count !== 1 ? "s" : ""}
            </div>
          </div>
        ))}
      </div>

      {(!jobs || jobs.length === 0) && !showForm && (
        <div className="rounded-xl border border-dashed border-gray-300 bg-white p-12 text-center">
          <BriefcaseIcon className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3 text-sm text-gray-500">
            No jobs yet. Click <strong>New Job</strong> to add one.
          </p>
        </div>
      )}
    </div>
  );
}

function BriefcaseIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      <rect width="20" height="14" x="2" y="6" rx="2" />
    </svg>
  );
}
