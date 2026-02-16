export type UserRole = "recruiter" | "job_seeker";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  created_at: string;
}

export type CandidateStatus =
  | "new"
  | "contacted"
  | "replied"
  | "screening"
  | "interview_scheduled"
  | "interviewed"
  | "offer_sent"
  | "hired"
  | "rejected"
  | "withdrawn";

export type EmailType =
  | "outreach"
  | "followup"
  | "rejection"
  | "interview_invite";

export interface Job {
  id: string;
  title: string;
  company: string;
  posted_date: string;
  required_skills: string[];
  preferred_skills: string[];
  experience_years: number | null;
  location: string;
  remote: boolean;
  salary_range: string;
  summary: string;
  raw_text: string;
  candidate_count: number;
  created_at: string;
}

export interface TopJob {
  job_id: string;
  title: string;
  company: string;
  score: number;
}

export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone: string;
  current_title: string;
  current_company: string;
  skills: string[];
  experience_years: number | null;
  location: string;
  resume_path: string;
  resume_summary: string;
  status: CandidateStatus;
  match_score: number;
  match_reasoning: string;
  strengths: string[];
  gaps: string[];
  notes: string;
  job_id: string;
  top_jobs?: TopJob[];
  created_at: string;
  updated_at: string;
}

export interface Email {
  id: string;
  candidate_id: string;
  candidate_name: string;
  to_email: string;
  subject: string;
  body: string;
  email_type: EmailType;
  approved: boolean;
  sent: boolean;
  sent_at: string | null;
  reply_received: boolean;
  attachment_path: string;
  message_id: string;
  reply_body: string;
  replied_at: string | null;
  created_at: string;
}

export interface AgentEvent {
  type: "plan" | "progress" | "approval" | "result" | "error";
  data: Record<string, unknown>;
}

export interface Settings {
  llm_provider: string;
  llm_model: string;
  anthropic_api_key: string;
  openai_api_key: string;
  email_backend: string;
  sendgrid_api_key: string;
  email_from: string;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  imap_host: string;
  imap_port: number;
  imap_username: string;
  imap_password: string;
  recruiter_name: string;
  recruiter_email: string;
  recruiter_company: string;
}

export interface ChatEmailAction {
  type: "compose_email";
  email: Email;
}

export interface ChatResumeUploadAction {
  type: "upload_resume";
  job_id?: string;
  job_title?: string;
}

export interface ChatJdUploadAction {
  type: "upload_jd";
}

export type ChatAction = ChatEmailAction | ChatResumeUploadAction | ChatJdUploadAction;

export interface ChatResponse {
  reply: string;
  action?: ChatAction;
  session_id?: string;
  message_id?: string;
}

export interface ChatMessage {
  id: string;
  user_id: string;
  session_id?: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  action?: ChatAction;
  actionStatus?: "pending" | "sent" | "uploaded" | "cancelled";
}

export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export type EventType = "interview" | "follow_up" | "offer" | "screening" | "other";

export interface CalendarEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  event_type: EventType;
  candidate_id: string;
  candidate_name: string;
  job_id: string;
  job_title: string;
  notes: string;
  created_at: string;
  updated_at: string;
}

// Pipeline columns for Kanban board
export const PIPELINE_COLUMNS: { key: CandidateStatus; label: string }[] = [
  { key: "new", label: "New" },
  { key: "contacted", label: "Contacted" },
  { key: "replied", label: "Replied" },
  { key: "screening", label: "Screening" },
  { key: "interview_scheduled", label: "Interview" },
  { key: "offer_sent", label: "Offer" },
  { key: "hired", label: "Hired" },
];
