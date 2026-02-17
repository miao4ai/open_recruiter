import axios from "axios";
import type { CalendarEvent, Candidate, ChatMessage, ChatResponse, ChatSession, Email, Job, JobSeekerProfile, Notification, Settings, User, UserRole } from "../types";

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
export const register = (email: string, password: string, name: string, role: UserRole = "recruiter") =>
  api
    .post<{ token: string; user: User }>("/auth/register", { email, password, name, role })
    .then((r) => r.data);
export const login = (email: string, password: string, role: UserRole = "recruiter") =>
  api
    .post<{ token: string; user: User }>("/auth/login", { email, password, role })
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
export const uploadJd = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<Job>("/jobs/upload", form).then((r) => r.data);
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
export const markEmailReplied = (id: string) =>
  api.post(`/emails/${id}/mark-replied`).then((r) => r.data);
export const checkReplies = () =>
  api.post<{ status: string; replies_found: number }>("/emails/check-replies").then((r) => r.data);

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
export const sendChatMessage = (message: string, session_id?: string) =>
  api.post<ChatResponse>("/agent/chat", { message, session_id }).then((r) => r.data);

/**
 * SSE streaming chat. Streams text tokens via onToken callback,
 * then resolves with the final structured ChatResponse.
 */
export function streamChatMessage(
  message: string,
  session_id: string | undefined,
  onToken: (text: string) => void,
): Promise<ChatResponse> {
  return new Promise((resolve, reject) => {
    const token = getToken();
    fetch("/api/agent/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, session_id: session_id || "" }),
    })
      .then((resp) => {
        if (!resp.ok) {
          reject(new Error(`Stream failed: ${resp.status}`));
          return;
        }
        const reader = resp.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        function pump(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) {
              reject(new Error("Stream ended without done event"));
              return;
            }
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            let eventType = "";
            let dataLines: string[] = [];

            for (const line of lines) {
              if (line.startsWith("event:")) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                dataLines.push(line.slice(5).trim());
              } else if (line === "") {
                if (eventType && dataLines.length > 0) {
                  const data = dataLines.join("\n");
                  if (eventType === "token") {
                    try {
                      const parsed = JSON.parse(data);
                      if (parsed.t) onToken(parsed.t);
                    } catch { /* ignore */ }
                  } else if (eventType === "done") {
                    try {
                      resolve(JSON.parse(data) as ChatResponse);
                      return;
                    } catch {
                      reject(new Error("Failed to parse done event"));
                      return;
                    }
                  }
                }
                eventType = "";
                dataLines = [];
              }
            }
            return pump();
          });
        }

        pump().catch(reject);
      })
      .catch(reject);
  });
}

export const getChatHistory = (session_id?: string) =>
  api.get<ChatMessage[]>("/agent/chat/history", { params: session_id ? { session_id } : {} }).then((r) => r.data);
export const clearChatHistory = () =>
  api.delete("/agent/chat/history").then((r) => r.data);
export const updateChatMessageStatus = (messageId: string, actionStatus: string) =>
  api.patch(`/agent/chat/messages/${messageId}`, { action_status: actionStatus }).then((r) => r.data);
export const saveChatMessage = (sessionId: string, content: string, role = "assistant") =>
  api.post("/agent/chat/messages", { session_id: sessionId, content, role }).then((r) => r.data);

// ── Chat Sessions ────────────────────────────────────────────────────────
export const listChatSessions = () =>
  api.get<ChatSession[]>("/agent/chat/sessions").then((r) => r.data);
export const createChatSession = () =>
  api.post<ChatSession>("/agent/chat/sessions").then((r) => r.data);
export const deleteChatSession = (id: string) =>
  api.delete(`/agent/chat/sessions/${id}`).then((r) => r.data);
export const renameChatSession = (id: string, title: string) =>
  api.put<ChatSession>(`/agent/chat/sessions/${id}`, { title }).then((r) => r.data);

// ── Calendar ─────────────────────────────────────────────────────────
export const listEvents = (params?: { month?: string; candidate_id?: string; job_id?: string }) =>
  api.get<CalendarEvent[]>("/calendar", { params }).then((r) => r.data);
export const createEvent = (data: {
  title: string;
  start_time: string;
  end_time?: string;
  event_type?: string;
  candidate_id?: string;
  candidate_name?: string;
  job_id?: string;
  job_title?: string;
  notes?: string;
}) => api.post<CalendarEvent>("/calendar", data).then((r) => r.data);
export const getEvent = (id: string) =>
  api.get<CalendarEvent>(`/calendar/${id}`).then((r) => r.data);
export const updateEvent = (id: string, data: Partial<CalendarEvent>) =>
  api.put<CalendarEvent>(`/calendar/${id}`, data).then((r) => r.data);
export const deleteEvent = (id: string) =>
  api.delete(`/calendar/${id}`).then((r) => r.data);

// ── Job Seeker — Own Saved Jobs ──────────────────────────────────────────
export const seekerListJobs = (q = "") =>
  api.get<Job[]>("/seeker/jobs", { params: q ? { q } : {} }).then((r) => r.data);
export const seekerGetJob = (id: string) =>
  api.get<Job>(`/seeker/jobs/${id}`).then((r) => r.data);
export const seekerUploadJd = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<Job>("/seeker/jobs/upload", form).then((r) => r.data);
};
export const seekerDeleteJob = (id: string) =>
  api.delete(`/seeker/jobs/${id}`).then((r) => r.data);

// ── Job Seeker Profile ──────────────────────────────────────────────────
export const getMyProfile = () =>
  api.get<JobSeekerProfile>("/profile").then((r) => r.data);
export const updateMyProfile = (data: Partial<JobSeekerProfile>) =>
  api.put<JobSeekerProfile>("/profile", data).then((r) => r.data);
export const uploadResumeForProfile = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return api.post<JobSeekerProfile>("/profile/upload-resume", form).then((r) => r.data);
};

// ── Notifications ────────────────────────────────────────────────────────
export const getNotifications = () =>
  api.get<Notification[]>("/agent/notifications").then((r) => r.data);
