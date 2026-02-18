export type UserRole = "recruiter" | "job_seeker";

export interface User {
  id: string;
  email: string;
  name: string;
  role?: UserRole;
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
  | "interview_invite"
  | "recommendation";

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
  contact_name: string;
  contact_email: string;
  candidate_count: number;
  created_at: string;
}

export interface TopJob {
  job_id: string;
  title: string;
  company: string;
  score: number;
}

export interface CandidateJobMatch {
  id: string;
  candidate_id: string;
  job_id: string;
  job_title: string;
  job_company: string;
  match_score: number;
  match_reasoning: string;
  strengths: string[];
  gaps: string[];
  status: string;
  created_at: string;
  updated_at: string;
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
  date_of_birth: string;
  notes: string;
  job_matches: CandidateJobMatch[];
  // Backward compat — populated when listing candidates for a specific job
  match_score: number;
  match_reasoning: string;
  strengths: string[];
  gaps: string[];
  job_id: string;
  top_jobs?: TopJob[];
  created_at: string;
  updated_at: string;
}

export interface JobSeekerProfile {
  id: string;
  user_id: string;
  name: string;
  email: string;
  phone: string;
  current_title: string;
  current_company: string;
  skills: string[];
  experience_years: number | null;
  location: string;
  resume_summary: string;
  resume_path: string;
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
  gemini_api_key: string;
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

export interface ChatCreateJobAction {
  type: "create_job";
  job: Job;
}

export interface ChatCreateCandidateAction {
  type: "create_candidate";
  candidate: Candidate;
}

export interface MarketReport {
  salary_range: { min: number; max: number; median: number; currency: string };
  market_demand: "high" | "medium" | "low";
  key_factors: string[];
  comparable_titles: string[];
  regional_notes: string;
  summary: string;
  role: string;
  location: string;
}

export interface ChatMarketAnalysisAction {
  type: "market_analysis";
  report: MarketReport;
}

export type ChatAction = ChatEmailAction | ChatResumeUploadAction | ChatJdUploadAction | ChatCreateJobAction | ChatCreateCandidateAction | ChatMarketAnalysisAction;

export interface ChatResponse {
  reply: string;
  action?: ChatAction;
  blocks?: MessageBlock[];
  suggestions?: Suggestion[];
  context_hint?: ContextView | null;
  session_id?: string;
  message_id?: string;
  workflow_id?: string;
  workflow_status?: WorkflowStatus;
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
  blocks?: MessageBlock[];
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
// `labelKey` is resolved via t() at render time for i18n support
export const PIPELINE_COLUMNS: { key: CandidateStatus; labelKey: string }[] = [
  { key: "new", labelKey: "pipeline.new" },
  { key: "contacted", labelKey: "pipeline.contacted" },
  { key: "replied", labelKey: "pipeline.replied" },
  { key: "screening", labelKey: "pipeline.screening" },
  { key: "interview_scheduled", labelKey: "pipeline.interview" },
  { key: "offer_sent", labelKey: "pipeline.offer" },
  { key: "hired", labelKey: "pipeline.hired" },
];

// ── Control Center types ─────────────────────────────────────────────────

export type ContextView =
  | { type: "briefing" }
  | { type: "candidate"; id: string }
  | { type: "job"; id: string }
  | { type: "pipeline_stage"; stage: CandidateStatus }
  | { type: "events" }
  | { type: "comparison"; candidate_ids: [string, string] };

export interface Suggestion {
  label: string;
  prompt: string;
  icon?: string;
}

// ── Rich Message Blocks ─────────────────────────────────────────────────

export interface MatchRanking {
  job_id: string;
  title: string;
  company: string;
  score: number;
  strengths: string[];
  gaps: string[];
  one_liner: string;
}

export interface MatchReportBlock {
  type: "match_report";
  candidate: {
    id: string;
    name: string;
    current_title: string;
    skills: string[];
  };
  rankings: MatchRanking[];
  summary: string;
}

export interface ApprovalBlock {
  type: "approval_block";
  workflow_id: string;
  title: string;
  description: string;
  approve_label: string;
  cancel_label: string;
  preview_items: { label: string; detail: string }[];
}

export type MessageBlock = MatchReportBlock | ApprovalBlock;

// ── Workflow Types ──────────────────────────────────────────────────────

export type WorkflowType = "bulk_outreach" | "candidate_review" | "interview_scheduling" | "pipeline_cleanup" | "job_launch";
export type WorkflowStatus = "running" | "paused" | "done" | "cancelled";

export interface WorkflowStep {
  label: string;
  status: "pending" | "running" | "done" | "skipped";
}

export interface ActiveWorkflow {
  workflow_id: string;
  workflow_type: WorkflowType;
  status: WorkflowStatus;
  current_step: number;
  total_steps: number;
  steps: WorkflowStep[];
}

export interface WorkflowStepEvent {
  workflow_id: string;
  step_index: number;
  total_steps: number;
  label: string;
  status: string;
}

// ── Notifications ───────────────────────────────────────────────────────

export interface Notification {
  id: string;
  type: "stale_candidate" | "upcoming_event" | "new_match" | "pending_drafts";
  severity: "warning" | "success" | "info";
  title: string;
  description: string;
  candidate_id?: string;
  candidate_name?: string;
  action_label: string;
  action_prompt: string;
  created_at: string;
}

// ── Automation Types ────────────────────────────────────────────────────

export type AutomationRuleType =
  | "auto_match"
  | "inbox_scan"
  | "auto_followup"
  | "pipeline_cleanup";

export type AutomationTriggerType = "interval" | "cron";

export interface AutomationRule {
  id: string;
  name: string;
  description: string;
  rule_type: AutomationRuleType;
  trigger_type: AutomationTriggerType;
  schedule_value: string;
  conditions_json: string;
  actions_json: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  run_count: number;
  error_count: number;
  created_at: string;
  updated_at: string;
}

export interface AutomationLog {
  id: string;
  rule_id: string;
  rule_name: string;
  status: "running" | "success" | "error" | "skipped";
  started_at: string;
  finished_at: string | null;
  duration_ms: number;
  summary: string;
  details_json: string;
  error_message: string;
  items_processed: number;
  items_affected: number;
  created_at: string;
}

export interface SchedulerStatus {
  running: boolean;
  active_jobs: number;
  jobs: { id: string; name: string; next_run: string }[];
}
