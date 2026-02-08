import axios from "axios";
import type { Candidate, Email, Job, Settings } from "../types";

const api = axios.create({ baseURL: "/api" });

// ── Jobs ──────────────────────────────────────────────────────────────────
export const listJobs = () => api.get<Job[]>("/jobs").then((r) => r.data);
export const getJob = (id: string) =>
  api.get<Job>(`/jobs/${id}`).then((r) => r.data);
export const createJob = (raw_text: string) =>
  api.post<Job>("/jobs", { raw_text }).then((r) => r.data);
export const deleteJob = (id: string) =>
  api.delete(`/jobs/${id}`).then((r) => r.data);

// ── Candidates ────────────────────────────────────────────────────────────
export const listCandidates = (params?: {
  job_id?: string;
  status?: string;
}) => api.get<Candidate[]>("/candidates", { params }).then((r) => r.data);
export const getCandidate = (id: string) =>
  api.get<Candidate>(`/candidates/${id}`).then((r) => r.data);
export const uploadResume = (file: File, job_id: string = "") => {
  const form = new FormData();
  form.append("file", file);
  if (job_id) form.append("job_id", job_id);
  return api.post<Candidate>("/candidates/upload", form).then((r) => r.data);
};
export const updateCandidate = (
  id: string,
  data: { status?: string; notes?: string }
) => api.patch<Candidate>(`/candidates/${id}`, data).then((r) => r.data);
export const matchCandidates = (job_id: string, candidate_ids: string[]) =>
  api
    .post("/candidates/match", { job_id, candidate_ids })
    .then((r) => r.data);

// ── Emails ────────────────────────────────────────────────────────────────
export const listEmails = (candidate_id?: string) =>
  api
    .get<Email[]>("/emails", { params: candidate_id ? { candidate_id } : {} })
    .then((r) => r.data);
export const draftEmail = (
  candidate_id: string,
  job_id: string,
  email_type: string = "outreach"
) =>
  api
    .post<Email>("/emails/draft", { candidate_id, job_id, email_type })
    .then((r) => r.data);
export const approveEmail = (id: string) =>
  api.post(`/emails/${id}/approve`).then((r) => r.data);
export const sendEmail = (id: string) =>
  api.post(`/emails/${id}/send`).then((r) => r.data);
export const pendingEmails = () =>
  api.get<Email[]>("/emails/pending").then((r) => r.data);

// ── Settings ──────────────────────────────────────────────────────────────
export const getSettings = () =>
  api.get<Settings>("/settings").then((r) => r.data);
export const updateSettings = (data: Partial<Settings>) =>
  api.put("/settings", data).then((r) => r.data);
export const testLlm = () =>
  api.post("/settings/test-llm").then((r) => r.data);
export const testEmail = () =>
  api.post("/settings/test-email").then((r) => r.data);

// ── Agent (SSE) ───────────────────────────────────────────────────────────
export const runAgent = (instruction: string) =>
  api.post("/agent/run", { instruction }).then((r) => r.data);
