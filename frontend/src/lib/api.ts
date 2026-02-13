import axios from "axios";
import type { Candidate, ChatMessage, Email, Job, Settings, User } from "../types";

const api = axios.create({ baseURL: "/api" });

// ── Auth interceptors ────────────────────────────────────────────────────

const TOKEN_KEY = "or_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// ── Auth ─────────────────────────────────────────────────────────────────
export const register = (email: string, password: string, name: string) =>
  api
    .post<{ token: string; user: User }>("/auth/register", { email, password, name })
    .then((r) => r.data);
export const login = (email: string, password: string) =>
  api
    .post<{ token: string; user: User }>("/auth/login", { email, password })
    .then((r) => r.data);
export const getMe = () =>
  api.get<User>("/auth/me").then((r) => r.data);

// ── Jobs ──────────────────────────────────────────────────────────────────
export const listJobs = () => api.get<Job[]>("/jobs").then((r) => r.data);
export const getJob = (id: string) =>
  api.get<Job>(`/jobs/${id}`).then((r) => r.data);
export const createJob = (data: {
  title?: string;
  company?: string;
  posted_date?: string;
  raw_text: string;
}) => api.post<Job>("/jobs", data).then((r) => r.data);
export const updateJob = (
  id: string,
  data: { title?: string; company?: string; posted_date?: string; raw_text?: string }
) => api.put<Job>(`/jobs/${id}`, data).then((r) => r.data);
export const deleteJob = (id: string) =>
  api.delete(`/jobs/${id}`).then((r) => r.data);
export const getRankedCandidates = (jobId: string) =>
  api.get<Candidate[]>(`/jobs/${jobId}/ranked-candidates`).then((r) => r.data);

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
  data: {
    name?: string;
    email?: string;
    phone?: string;
    current_title?: string;
    current_company?: string;
    skills?: string[];
    experience_years?: number | null;
    location?: string;
    status?: string;
    notes?: string;
    job_id?: string;
  }
) => api.patch<Candidate>(`/candidates/${id}`, data).then((r) => r.data);
export const deleteCandidate = (id: string) =>
  api.delete(`/candidates/${id}`).then((r) => r.data);
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
export const composeEmail = (data: {
  to_email: string;
  subject: string;
  body: string;
  email_type?: string;
  candidate_id?: string;
  candidate_name?: string;
}) =>
  api.post<Email>("/emails/compose", data).then((r) => r.data);
export const composeEmailWithAttachment = (data: {
  to_email: string;
  subject: string;
  body: string;
  email_type?: string;
  candidate_id?: string;
  candidate_name?: string;
  job_id?: string;
  use_candidate_resume?: boolean;
  attachment?: File;
}) => {
  const form = new FormData();
  form.append("to_email", data.to_email);
  form.append("subject", data.subject);
  form.append("body", data.body);
  if (data.email_type) form.append("email_type", data.email_type);
  if (data.candidate_id) form.append("candidate_id", data.candidate_id);
  if (data.candidate_name) form.append("candidate_name", data.candidate_name);
  if (data.job_id) form.append("job_id", data.job_id);
  if (data.use_candidate_resume) form.append("use_candidate_resume", "true");
  if (data.attachment) form.append("attachment", data.attachment);
  return api.post<Email>("/emails/compose-with-attachment", form).then((r) => r.data);
};
export const approveEmail = (id: string) =>
  api.post(`/emails/${id}/approve`).then((r) => r.data);
export const sendEmail = (id: string) =>
  api.post(`/emails/${id}/send`).then((r) => r.data);
export const updateEmailDraft = (
  id: string,
  data: {
    to_email: string;
    subject: string;
    body: string;
    email_type?: string;
    candidate_id?: string;
    candidate_name?: string;
  }
) => api.put<Email>(`/emails/${id}`, data).then((r) => r.data);
export const deleteEmail = (id: string) =>
  api.delete(`/emails/${id}`).then((r) => r.data);
export const pendingEmails = () =>
  api.get<Email[]>("/emails/pending").then((r) => r.data);

// ── Search ───────────────────────────────────────────────────────────────
export const searchByText = (
  query: string,
  collection: "jobs" | "candidates",
  n_results: number = 20,
) =>
  api
    .post<{ record: Job | Candidate; similarity_score: number }[]>(
      "/search/text",
      { query, collection, n_results },
    )
    .then((r) => r.data);

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

// ── Chat ─────────────────────────────────────────────────────────────────
export const sendChatMessage = (message: string) =>
  api.post<{ reply: string }>("/agent/chat", { message }).then((r) => r.data);
export const getChatHistory = () =>
  api.get<ChatMessage[]>("/agent/chat/history").then((r) => r.data);
export const clearChatHistory = () =>
  api.delete("/agent/chat/history").then((r) => r.data);
