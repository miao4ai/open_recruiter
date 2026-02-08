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
  recruiter_name: string;
  recruiter_email: string;
  recruiter_company: string;
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
