import axios from "axios";
import type { AutomationLog, AutomationRule, CalendarEvent, Candidate, ChatMessage, ChatResponse, ChatSession, Email, Job, JobSeekerProfile, Notification, SchedulerStatus, Settings, User, UserRole, WorkflowStepEvent } from "../types";

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
export const deleteAccount = (deleteRecords = false) =>
  api.delete("/auth/account", { params: { delete_records: deleteRecords } }).then((r) => r.data);

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
    date_of_birth?: string;
  }
) => api.patch<Candidate>(`/candidates/${id}`, data).then((r) => r.data);
export const deleteCandidate = (id: string) =>
  api.delete(`/candidates/${id}`).then((r) => r.data);
export const reparseCandidate = (id: string) =>
  api.post<Candidate>(`/candidates/${id}/reparse`).then((r) => r.data);
export const matchCandidates = (job_id: string, candidate_ids: string[]) =>
  api
    .post("/candidates/match", { job_id, candidate_ids })
    .then((r) => r.data);
export const linkCandidateJob = (candidateId: string, jobId: string) => {
  const form = new FormData();
  form.append("job_id", jobId);
  return api.post<Candidate>(`/candidates/${candidateId}/link-job`, form).then((r) => r.data);
};
export const unlinkCandidateJob = (candidateId: string, jobId: string) =>
  api.delete(`/candidates/${candidateId}/jobs/${jobId}`).then((r) => r.data);

// ── Pipeline ─────────────────────────────────────────────────────────────
export const listPipelineEntries = (view: "candidate" | "jobs" = "candidate") =>
  api.get("/candidates/pipeline", { params: { view } }).then((r) => r.data);

export const updatePipelineStatus = (candidateId: string, jobId: string, pipelineStatus: string) =>
  api.patch(`/candidates/pipeline/${candidateId}/${jobId}`, { pipeline_status: pipelineStatus }).then((r) => r.data);

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
export const getSetupStatus = () =>
  api.get<{ llm_configured: boolean; llm_provider: string; llm_model: string; has_api_key: boolean }>("/settings/setup-status").then((r) => r.data);
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
export const sendChatMessage = (message: string, session_id?: string, encouragement_mode?: boolean) =>
  api.post<ChatResponse>("/agent/chat", { message, session_id, encouragement_mode: encouragement_mode ?? false }).then((r) => r.data);

/**
 * SSE streaming chat. Streams text tokens via onToken callback,
 * then resolves with the final structured ChatResponse.
 * Falls back to the non-streaming endpoint if streaming fails.
 */
export async function streamChatMessage(
  message: string,
  session_id: string | undefined,
  onToken: (text: string) => void,
  onWorkflowStep?: (step: WorkflowStepEvent) => void,
  encouragement_mode?: boolean,
): Promise<ChatResponse> {
  try {
    return await _streamSSE(message, session_id, onToken, onWorkflowStep, encouragement_mode);
  } catch (err) {
    // Fallback: try the non-streaming endpoint
    console.warn("Streaming failed, falling back to sync chat:", err);
    return sendChatMessage(message, session_id, encouragement_mode);
  }
}

function _streamSSE(
  message: string,
  session_id: string | undefined,
  onToken: (text: string) => void,
  onWorkflowStep?: (step: WorkflowStepEvent) => void,
  encouragement_mode?: boolean,
): Promise<ChatResponse> {
  return new Promise((resolve, reject) => {
    const token = getToken();
    fetch("/api/agent/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, session_id: session_id || "", encouragement_mode: encouragement_mode ?? false }),
    })
      .then((resp) => {
        if (!resp.ok) {
          reject(new Error(`Stream failed: ${resp.status}`));
          return;
        }
        const reader = resp.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let resolved = false;

        function pump(): Promise<void> {
          return reader.read().then(({ done, value }) => {
            if (done) {
              if (!resolved) reject(new Error("Stream ended without done event"));
              return;
            }
            buffer += decoder.decode(value, { stream: true });

            // Strip \r for robustness (handles \r\n line endings)
            const lines = buffer.replace(/\r/g, "").split("\n");
            buffer = lines.pop() || "";

            let eventType = "";
            let dataLines: string[] = [];

            for (const line of lines) {
              if (line.startsWith("event:")) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                dataLines.push(line.slice(5).trim());
              } else if (line === "" || line.startsWith(":")) {
                // Empty line = event boundary; lines starting with : are SSE comments
                if (eventType && dataLines.length > 0) {
                  const data = dataLines.join("\n");
                  if (eventType === "token") {
                    try {
                      const parsed = JSON.parse(data);
                      if (parsed.t) onToken(parsed.t);
                    } catch { /* ignore malformed tokens */ }
                  } else if (eventType === "workflow_step") {
                    try {
                      onWorkflowStep?.(JSON.parse(data) as WorkflowStepEvent);
                    } catch { /* ignore */ }
                  } else if (eventType === "done") {
                    try {
                      resolved = true;
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
export const seekerSaveJob = (data: {
  title: string;
  company?: string;
  location?: string;
  url?: string;
  snippet?: string;
  salary_range?: string;
  source?: string;
}) => api.post<Job>("/seeker/jobs", data).then((r) => r.data);
export const seekerGetSavedUrls = () =>
  api.get<{ urls: string[]; title_company_pairs: { title: string; company: string }[] }>("/seeker/jobs/saved-urls").then((r) => r.data);

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

// ── Automations ─────────────────────────────────────────────────────────
export const listAutomationRules = () =>
  api.get<AutomationRule[]>("/automations/rules").then((r) => r.data);
export const getAutomationRule = (id: string) =>
  api.get<AutomationRule>(`/automations/rules/${id}`).then((r) => r.data);
export const createAutomationRule = (data: {
  name: string;
  description?: string;
  rule_type: string;
  trigger_type?: string;
  schedule_value?: string;
  conditions_json?: string;
  actions_json?: string;
  enabled?: boolean;
}) => api.post<AutomationRule>("/automations/rules", data).then((r) => r.data);
export const updateAutomationRule = (
  id: string,
  data: Partial<AutomationRule>,
) => api.patch<AutomationRule>(`/automations/rules/${id}`, data).then((r) => r.data);
export const deleteAutomationRule = (id: string) =>
  api.delete(`/automations/rules/${id}`).then((r) => r.data);
export const toggleAutomationRule = (id: string) =>
  api.post<{ enabled: boolean }>(`/automations/rules/${id}/toggle`).then((r) => r.data);
export const runAutomationRule = (id: string) =>
  api.post(`/automations/rules/${id}/run`).then((r) => r.data);
export const listAutomationLogs = (ruleId?: string, limit?: number) =>
  api
    .get<AutomationLog[]>("/automations/logs", {
      params: { ...(ruleId ? { rule_id: ruleId } : {}), ...(limit ? { limit } : {}) },
    })
    .then((r) => r.data);
export const getSchedulerStatus = () =>
  api.get<SchedulerStatus>("/automations/status").then((r) => r.data);
