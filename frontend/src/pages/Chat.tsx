import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TextField from "@mui/material/TextField";
import Button from "@mui/material/Button";
import IconButton from "@mui/material/IconButton";
import Avatar from "@mui/material/Avatar";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import LinearProgress from "@mui/material/LinearProgress";
import SendOutlined from "@mui/icons-material/SendOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import Close from "@mui/icons-material/Close";
import Add from "@mui/icons-material/Add";
import ChatBubbleOutline from "@mui/icons-material/ChatBubbleOutline";
import CloudUpload from "@mui/icons-material/CloudUpload";
import DescriptionOutlined from "@mui/icons-material/DescriptionOutlined";
import WorkOutline from "@mui/icons-material/WorkOutline";
import PersonAddOutlined from "@mui/icons-material/PersonAddOutlined";
import TrendingUpOutlined from "@mui/icons-material/TrendingUpOutlined";
import AttachMoneyOutlined from "@mui/icons-material/AttachMoneyOutlined";
import MailOutline from "@mui/icons-material/MailOutline";
import { useApi } from "../hooks/useApi";
import {
  streamChatMessage,
  getChatHistory,
  clearChatHistory,
  sendEmail,
  deleteEmail,
  updateEmailDraft,
  uploadResume,
  uploadJd,
  listChatSessions,
  deleteChatSession,
  listJobs,
  listCandidates,
  updateChatMessageStatus,
  saveChatMessage,
} from "../lib/api";
import PipelineBar from "../components/PipelineBar";
import ContextPanel from "../components/ContextPanel";
import SmartActionBar from "../components/SmartActionBar";
import MessageBlocks from "../components/MessageBlocks";
import WorkflowTracker from "../components/WorkflowTracker";
import type {
  ActiveWorkflow, Candidate, CandidateStatus, ChatMessage, ChatSession,
  ContextView, Email, Job, MarketReport, MessageBlock, Suggestion, WorkflowStepEvent,
} from "../types";

/* ── Greeting / Daily Briefing ──────────────────────────────────────────── */

function makeBriefing(candidates: Candidate[], t: TFunction): ChatMessage {
  const dateStr = new Date().toLocaleDateString("en-US", {
    year: "numeric", month: "long", day: "numeric",
  });
  const total = candidates.length;
  const newCount = candidates.filter((c) => c.status === "new").length;
  const contacted = candidates.filter((c) => c.status === "contacted");
  const interviews = candidates.filter((c) => c.status === "interview_scheduled");

  const lines = [t("chat.briefingIntro", { date: dateStr })];

  lines.push(t("chat.briefingPipeline", { count: total }));
  if (newCount > 0) lines.push(t("chat.briefingNew", { count: newCount }));
  if (contacted.length > 0)
    lines.push(t("chat.briefingContacted", { count: contacted.length, names: contacted.slice(0, 3).map((c) => c.name).join(", "), more: contacted.length > 3 ? "..." : "" }));
  if (interviews.length > 0)
    lines.push(t("chat.briefingInterviews", { count: interviews.length }));

  lines.push("\n" + t("chat.briefingHelp"));

  return {
    id: "briefing-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: lines.join("\n"),
    created_at: new Date().toISOString(),
  };
}

function makeSimpleGreeting(t: TFunction): ChatMessage {
  return {
    id: "greeting-" + Date.now(),
    user_id: "",
    role: "assistant",
    content: t("chat.simpleGreeting"),
    created_at: new Date().toISOString(),
  };
}

/* ── Suggestion Builder ─────────────────────────────────────────────────── */

function buildSuggestions(
  messages: ChatMessage[],
  candidates: Candidate[] | null,
  lastAction?: ChatMessage["action"],
  t?: TFunction,
): Suggestion[] {
  const result: Suggestion[] = [];

  if (lastAction?.type === "compose_email" || lastAction?.type === "upload_resume") {
    return [];
  }

  if (candidates) {
    const contacted = candidates.filter((c) => c.status === "contacted");
    const newOnes = candidates.filter((c) => c.status === "new");

    if (contacted.length > 0) {
      result.push({ label: t ? t("chat.checkForReplies") : "Check for replies", prompt: "Have any contacted candidates replied?", icon: "📩" });
    }
    if (newOnes.length > 0 && newOnes.length <= 5) {
      result.push({ label: t ? t("chat.review", { name: newOnes[0].name }) : `Review ${newOnes[0].name}`, prompt: `What jobs match ${newOnes[0].name}?`, icon: "📊" });
    }
  }

  if (messages.length <= 2) {
    result.push({ label: t ? t("chat.uploadResume") : "Upload resume", prompt: "Upload a resume", icon: "📄" });
    result.push({ label: t ? t("chat.uploadJD") : "Upload JD", prompt: "Upload a job description", icon: "📋" });
  }

  if (result.length === 0) {
    result.push({ label: t ? t("chat.pipelineStatus") : "Pipeline status", prompt: "What's the pipeline status today?", icon: "📊" });
    result.push({ label: t ? t("chat.uploadResume") : "Upload resume", prompt: "Upload a resume", icon: "📄" });
  }

  return result.slice(0, 4);
}

/* ── Inline Email Compose Card ──────────────────────────────────────────── */

function EmailComposeCard({
  email, status, onSend, onCancel, onUpdateField,
}: {
  email: Email;
  status: "pending" | "sent" | "cancelled";
  onSend: (emailId: string) => void;
  onCancel: (emailId: string) => void;
  onUpdateField: (emailId: string, field: string, value: string) => void;
}) {
  const { t } = useTranslation();
  const [sending, setSending] = useState(false);

  if (status === "sent") {
    return (
      <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "success.light", bgcolor: "success.50", backgroundColor: "#f0fdf4" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "success.dark" }}>
          <CheckCircleOutline sx={{ fontSize: 20 }} />
          <Typography variant="body2" fontWeight={500}>{t("chat.emailSent")}</Typography>
        </Box>
        <Typography variant="body2" sx={{ mt: 0.5, color: "success.main" }}>
          {t("chat.sentTo", { email: email.to_email, name: email.candidate_name })}
        </Typography>
      </Paper>
    );
  }
  if (status === "cancelled") {
    return (
      <Paper sx={{ mt: 1, p: 1.5, borderRadius: 3, border: "1px solid", borderColor: "grey.200", bgcolor: "grey.50" }}>
        <Typography variant="body2" sx={{ fontStyle: "italic", color: "text.secondary" }}>{t("chat.emailCancelled")}</Typography>
      </Paper>
    );
  }

  const handleSend = async () => {
    setSending(true);
    try { await onSend(email.id); } finally { setSending(false); }
  };

  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "#93c5fd", bgcolor: "#eff6ff80", display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "#1d4ed8" }}>
        <MailOutline sx={{ fontSize: 16 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.emailDraft")}</Typography>
      </Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
        <Typography variant="body2" color="text.secondary">To:</Typography>
        <Typography variant="body2" fontWeight={500}>{email.to_email}</Typography>
        {email.candidate_name && (
          <Typography variant="body2" sx={{ ml: 0.5, color: "text.disabled" }}>({email.candidate_name})</Typography>
        )}
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>{t("outreach.subject")}</Typography>
        <TextField
          fullWidth size="small" value={email.subject}
          onChange={(e) => onUpdateField(email.id, "subject", e.target.value)}
          sx={{ "& .MuiOutlinedInput-root": { borderRadius: 2, bgcolor: "white" } }}
        />
      </Box>
      <Box>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>{t("outreach.body")}</Typography>
        <TextField
          fullWidth multiline rows={8} size="small" value={email.body}
          onChange={(e) => onUpdateField(email.id, "body", e.target.value)}
          sx={{ "& .MuiOutlinedInput-root": { borderRadius: 2, bgcolor: "white" }, "& .MuiInputBase-input": { lineHeight: 1.6 } }}
        />
      </Box>
      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
        <Button
          size="small" variant="outlined" color="inherit" disabled={sending}
          onClick={() => onCancel(email.id)}
          startIcon={<Close sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem", color: "text.secondary" }}
        >
          {t("common.cancel")}
        </Button>
        <Button
          size="small" variant="contained" disabled={sending}
          onClick={handleSend}
          startIcon={sending ? <CircularProgress size={14} color="inherit" /> : <SendOutlined sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem" }}
        >
          {sending ? t("common.sending") : t("chat.sendEmailBtn")}
        </Button>
      </Box>
    </Paper>
  );
}

/* ── Inline Resume Upload Card ──────────────────────────────────────────── */

function ResumeUploadCard({
  status, defaultJobId, uploadedCandidate, onUpload, onCancel,
}: {
  status: "pending" | "uploaded" | "cancelled";
  defaultJobId?: string;
  uploadedCandidate?: Candidate;
  onUpload: (file: File, jobId: string) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState(defaultJobId || "");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));

  if (status === "uploaded" && uploadedCandidate) {
    return (
      <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "success.light", bgcolor: "#f0fdf4" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "success.dark" }}>
          <CheckCircleOutline sx={{ fontSize: 20 }} />
          <Typography variant="body2" fontWeight={500}>{t("chat.resumeUploaded")}</Typography>
        </Box>
        <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.nameLabel")}</Box> {uploadedCandidate.name}
          </Typography>
          {uploadedCandidate.current_title && (
            <Typography variant="body2" sx={{ color: "success.dark" }}>
              <Box component="span" fontWeight={500}>{t("chat.titleLabel")}</Box> {uploadedCandidate.current_title}
            </Typography>
          )}
          {uploadedCandidate.skills.length > 0 && (
            <Typography variant="body2" sx={{ color: "success.dark" }}>
              <Box component="span" fontWeight={500}>{t("chat.skillsLabel")}</Box> {uploadedCandidate.skills.slice(0, 5).join(", ")}
            </Typography>
          )}
        </Box>
      </Paper>
    );
  }
  if (status === "cancelled") {
    return (
      <Paper sx={{ mt: 1, p: 1.5, borderRadius: 3, border: "1px solid", borderColor: "grey.200", bgcolor: "grey.50" }}>
        <Typography variant="body2" sx={{ fontStyle: "italic", color: "text.secondary" }}>{t("chat.uploadCancelled")}</Typography>
      </Paper>
    );
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError("");
    try { await onUpload(file, jobId); }
    catch (err: unknown) {
      const axiosErr = err as { response?: { status?: number } };
      setError(axiosErr?.response?.status === 409 ? t("chat.duplicateCandidate") : (err instanceof Error ? err.message : t("chat.uploadFailed")));
    } finally { setUploading(false); }
  };

  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "#c4b5fd", bgcolor: "#f5f3ff80", display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "#6d28d9" }}>
        <CloudUpload sx={{ fontSize: 16 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.resumeUpload")}</Typography>
      </Box>
      <Box>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setError(""); }} style={{ display: "none" }} />
        <Button
          fullWidth variant="outlined" color="inherit"
          onClick={() => fileRef.current?.click()}
          startIcon={<DescriptionOutlined sx={{ fontSize: 16 }} />}
          sx={{
            borderRadius: 2, borderStyle: "dashed", borderColor: "grey.300", bgcolor: "white",
            justifyContent: "flex-start", textTransform: "none", color: "text.secondary",
            "&:hover": { borderColor: "#7c3aed", color: "#7c3aed" }, py: 1.5,
          }}
        >
          {file ? file.name : t("chat.clickToSelectResume")}
        </Button>
      </Box>
      {jobs && jobs.length > 0 && (
        <FormControl fullWidth size="small">
          <InputLabel sx={{ fontSize: "0.75rem" }}>{t("chat.associateWithJob")}</InputLabel>
          <Select
            value={jobId} onChange={(e) => setJobId(e.target.value as string)}
            label={t("chat.associateWithJob")}
            sx={{ borderRadius: 2, bgcolor: "white" }}
          >
            <MenuItem value="">{t("chat.noSpecificJob")}</MenuItem>
            {jobs.map((j: Job) => <MenuItem key={j.id} value={j.id}>{j.title} — {j.company}</MenuItem>)}
          </Select>
        </FormControl>
      )}
      {error && <Typography variant="body2" color="error">{error}</Typography>}
      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
        <Button
          size="small" variant="outlined" color="inherit" disabled={uploading}
          onClick={onCancel}
          startIcon={<Close sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem", color: "text.secondary" }}
        >
          {t("common.cancel")}
        </Button>
        <Button
          size="small" variant="contained" disabled={uploading || !file}
          onClick={handleUpload}
          startIcon={uploading ? <CircularProgress size={14} color="inherit" /> : <CloudUpload sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem", bgcolor: "#7c3aed", "&:hover": { bgcolor: "#6d28d9" } }}
        >
          {uploading ? t("chat.uploading") : t("chat.uploadResumeBtn")}
        </Button>
      </Box>
    </Paper>
  );
}

/* ── Inline JD Upload Card ──────────────────────────────────────────────── */

function JdUploadCard({
  status, uploadedJob, onUpload, onCancel,
}: {
  status: "pending" | "uploaded" | "cancelled";
  uploadedJob?: Job;
  onUpload: (file: File) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  if (status === "uploaded" && uploadedJob) {
    return (
      <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "success.light", bgcolor: "#f0fdf4" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "success.dark" }}>
          <CheckCircleOutline sx={{ fontSize: 20 }} />
          <Typography variant="body2" fontWeight={500}>{t("chat.jdUploaded")}</Typography>
        </Box>
        <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.titleLabel")}</Box> {uploadedJob.title}
          </Typography>
          {uploadedJob.company && (
            <Typography variant="body2" sx={{ color: "success.dark" }}>
              <Box component="span" fontWeight={500}>{t("chat.companyLabel")}</Box> {uploadedJob.company}
            </Typography>
          )}
          {uploadedJob.required_skills?.length > 0 && (
            <Typography variant="body2" sx={{ color: "success.dark" }}>
              <Box component="span" fontWeight={500}>{t("chat.skillsLabel")}</Box> {uploadedJob.required_skills.slice(0, 5).join(", ")}
            </Typography>
          )}
        </Box>
      </Paper>
    );
  }
  if (status === "cancelled") {
    return (
      <Paper sx={{ mt: 1, p: 1.5, borderRadius: 3, border: "1px solid", borderColor: "grey.200", bgcolor: "grey.50" }}>
        <Typography variant="body2" sx={{ fontStyle: "italic", color: "text.secondary" }}>{t("chat.uploadCancelled")}</Typography>
      </Paper>
    );
  }

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError("");
    try { await onUpload(file); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Upload failed"); }
    finally { setUploading(false); }
  };

  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "#fdba74", bgcolor: "#fff7ed80", display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "#c2410c" }}>
        <DescriptionOutlined sx={{ fontSize: 16 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.jdUpload")}</Typography>
      </Box>
      <Box>
        <input ref={fileRef} type="file" accept=".pdf,.docx,.doc,.txt" onChange={(e) => { setFile(e.target.files?.[0] || null); setError(""); }} style={{ display: "none" }} />
        <Button
          fullWidth variant="outlined" color="inherit"
          onClick={() => fileRef.current?.click()}
          startIcon={<DescriptionOutlined sx={{ fontSize: 16 }} />}
          sx={{
            borderRadius: 2, borderStyle: "dashed", borderColor: "grey.300", bgcolor: "white",
            justifyContent: "flex-start", textTransform: "none", color: "text.secondary",
            "&:hover": { borderColor: "#ea580c", color: "#ea580c" }, py: 1.5,
          }}
        >
          {file ? file.name : t("chat.clickToSelectJd")}
        </Button>
      </Box>
      {error && <Typography variant="body2" color="error">{error}</Typography>}
      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
        <Button
          size="small" variant="outlined" color="inherit" disabled={uploading}
          onClick={onCancel}
          startIcon={<Close sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem", color: "text.secondary" }}
        >
          {t("common.cancel")}
        </Button>
        <Button
          size="small" variant="contained" disabled={uploading || !file}
          onClick={handleUpload}
          startIcon={uploading ? <CircularProgress size={14} color="inherit" /> : <CloudUpload sx={{ fontSize: 14 }} />}
          sx={{ borderRadius: 2, textTransform: "none", fontSize: "0.75rem", bgcolor: "#ea580c", "&:hover": { bgcolor: "#c2410c" } }}
        >
          {uploading ? t("chat.uploading") : t("chat.uploadJdBtn")}
        </Button>
      </Box>
    </Paper>
  );
}

/* ── Inline Job Created Card ───────────────────────────────────────────── */

function JobCreatedCard({ job }: { job: Job }) {
  const { t } = useTranslation();
  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "success.light", bgcolor: "#f0fdf4" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "success.dark" }}>
        <WorkOutline sx={{ fontSize: 20 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.jobCreated")}</Typography>
      </Box>
      <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
        <Typography variant="body2" sx={{ color: "success.dark" }}>
          <Box component="span" fontWeight={500}>{t("chat.titleLabel")}</Box> {job.title}
        </Typography>
        {job.company && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.companyLabel")}</Box> {job.company}
          </Typography>
        )}
        {job.location && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.locationLabel")}</Box> {job.location}{job.remote ? ` (${t("common.remote")})` : ""}
          </Typography>
        )}
        {job.salary_range && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.salaryLabel")}</Box> {job.salary_range}
          </Typography>
        )}
        {job.required_skills?.length > 0 && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, pt: 0.5 }}>
            {job.required_skills.slice(0, 8).map((s: string) => (
              <Chip key={s} label={s} size="small" sx={{ bgcolor: "#dcfce7", color: "success.dark", fontSize: "0.7rem", height: 22 }} />
            ))}
          </Box>
        )}
        {job.summary && (
          <Typography variant="caption" sx={{ pt: 0.5, color: "success.main" }}>{job.summary}</Typography>
        )}
      </Box>
    </Paper>
  );
}

/* ── Inline Candidate Created Card ────────────────────────────────────── */

function CandidateCreatedCard({ candidate }: { candidate: Candidate }) {
  const { t } = useTranslation();
  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "success.light", bgcolor: "#f0fdf4" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "success.dark" }}>
        <PersonAddOutlined sx={{ fontSize: 20 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.candidateAdded")}</Typography>
      </Box>
      <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 0.5 }}>
        <Typography variant="body2" sx={{ color: "success.dark" }}>
          <Box component="span" fontWeight={500}>{t("chat.nameLabel")}</Box> {candidate.name}
        </Typography>
        {candidate.current_title && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.titleLabel")}</Box> {candidate.current_title}{candidate.current_company ? ` at ${candidate.current_company}` : ""}
          </Typography>
        )}
        {candidate.email && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.emailLabel")}</Box> {candidate.email}
          </Typography>
        )}
        {candidate.experience_years && (
          <Typography variant="body2" sx={{ color: "success.dark" }}>
            <Box component="span" fontWeight={500}>{t("chat.experienceLabel")}</Box> {candidate.experience_years} years
          </Typography>
        )}
        {candidate.skills?.length > 0 && (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, pt: 0.5 }}>
            {candidate.skills.slice(0, 8).map((s: string) => (
              <Chip key={s} label={s} size="small" sx={{ bgcolor: "#dcfce7", color: "success.dark", fontSize: "0.7rem", height: 22 }} />
            ))}
          </Box>
        )}
        {candidate.match_score > 0 && (
          <Typography variant="caption" sx={{ pt: 0.5, color: "success.main" }}>
            {t("chat.matchScore", { percent: Math.round(candidate.match_score * 100) })}
          </Typography>
        )}
      </Box>
    </Paper>
  );
}

/* ── Market Report Card ────────────────────────────────────────────────── */

function MarketReportCard({ report }: { report: MarketReport }) {
  const { t } = useTranslation();
  const demandColor = report.market_demand === "high"
    ? { color: "success.dark", bgcolor: "#dcfce7" }
    : report.market_demand === "medium"
    ? { color: "#854d0e", bgcolor: "#fef9c3" }
    : { color: "error.dark", bgcolor: "#fecaca" };

  const fmt = (n: number) => {
    const currency = report.salary_range?.currency || "USD";
    return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(n);
  };

  const sr = report.salary_range || {} as MarketReport["salary_range"];

  return (
    <Paper sx={{ mt: 1, p: 2, borderRadius: 3, border: "1px solid", borderColor: "#93c5fd", bgcolor: "#eff6ff" }}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, color: "#1d4ed8" }}>
        <TrendingUpOutlined sx={{ fontSize: 20 }} />
        <Typography variant="body2" fontWeight={500}>{t("chat.marketReport", { role: report.role })}</Typography>
        {report.location && (
          <Typography variant="caption" sx={{ color: "#3b82f6" }}>({report.location})</Typography>
        )}
      </Box>

      {/* Salary Range */}
      {sr.min != null && sr.max != null && (
        <Paper elevation={0} sx={{ mt: 1.5, p: 1.5, borderRadius: 2, bgcolor: "rgba(255,255,255,0.6)" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, mb: 1 }}>
            <AttachMoneyOutlined sx={{ fontSize: 14, color: "#2563eb" }} />
            <Typography variant="caption" fontWeight={500} sx={{ color: "#2563eb" }}>{t("chat.salaryRange")}</Typography>
          </Box>
          <Box sx={{ display: "flex", alignItems: "flex-end", gap: 4 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">{t("chat.min")}</Typography>
              <Typography variant="body2" fontWeight={500} display="block">{fmt(sr.min)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">{t("chat.median")}</Typography>
              <Typography variant="body2" fontWeight={600} display="block" sx={{ color: "#1d4ed8" }}>{fmt(sr.median)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">{t("chat.max")}</Typography>
              <Typography variant="body2" fontWeight={500} display="block">{fmt(sr.max)}</Typography>
            </Box>
          </Box>
          {/* Simple bar */}
          <Box sx={{ mt: 1, height: 8, width: "100%", borderRadius: 4, bgcolor: "grey.200", position: "relative" }}>
            <Box sx={{ position: "absolute", height: 8, borderRadius: 4, bgcolor: "#60a5fa", left: "0%", width: "100%" }} />
            {sr.max > sr.min && (
              <Box sx={{
                position: "absolute", top: 0, height: 8, width: 4, bgcolor: "#1d4ed8", borderRadius: 4,
                left: `${((sr.median - sr.min) / (sr.max - sr.min)) * 100}%`,
              }} />
            )}
          </Box>
        </Paper>
      )}

      {/* Demand badge */}
      <Box sx={{ mt: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
        <Typography variant="caption" color="text.secondary">{t("chat.marketDemand")}</Typography>
        <Chip label={report.market_demand} size="small" sx={{ ...demandColor, fontSize: "0.7rem", fontWeight: 500, height: 22 }} />
      </Box>

      {/* Key Factors */}
      {report.key_factors?.length > 0 && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" fontWeight={500} sx={{ color: "#2563eb" }}>{t("chat.keyFactors")}</Typography>
          <Box sx={{ mt: 0.5, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
            {report.key_factors.map((f: string, i: number) => (
              <Chip key={i} label={f} size="small" sx={{ bgcolor: "#dbeafe", color: "#1d4ed8", fontSize: "0.7rem", height: 22 }} />
            ))}
          </Box>
        </Box>
      )}

      {/* Comparable Titles */}
      {report.comparable_titles?.length > 0 && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" fontWeight={500} sx={{ color: "#2563eb" }}>{t("chat.comparableTitles")}</Typography>
          <Box sx={{ mt: 0.5, display: "flex", flexWrap: "wrap", gap: 0.5 }}>
            {report.comparable_titles.map((title: string, i: number) => (
              <Chip key={i} label={title} size="small" variant="outlined"
                sx={{ bgcolor: "rgba(255,255,255,0.8)", color: "#2563eb", borderColor: "#93c5fd", fontSize: "0.7rem", height: 22 }}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Regional Notes */}
      {report.regional_notes && (
        <Typography variant="caption" sx={{ mt: 1, display: "block", color: "#2563eb" }}>{report.regional_notes}</Typography>
      )}

      {/* Summary */}
      {report.summary && (
        <Typography variant="body2" sx={{ mt: 1, color: "#1d4ed8" }}>{report.summary}</Typography>
      )}
    </Paper>
  );
}

/* ── Session Sidebar ────────────────────────────────────────────────────── */

function SessionSidebar({
  sessions, activeSessionId, onSelect, onDelete, onNewChat,
}: {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelect: (s: ChatSession) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onNewChat: () => void;
}) {
  const { t } = useTranslation();
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return t("common.today");
    if (diffDays === 1) return t("common.yesterday");
    if (diffDays < 7) return t("common.daysAgo", { count: diffDays });
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  return (
    <Paper
      variant="outlined"
      sx={{ display: "flex", flexDirection: "column", width: 224, borderRadius: 3, overflow: "hidden" }}
    >
      <Box sx={{ borderBottom: "1px solid", borderColor: "grey.100", p: 1.25 }}>
        <Button
          fullWidth variant="contained" size="small"
          onClick={onNewChat}
          startIcon={<Add sx={{ fontSize: 14 }} />}
          sx={{
            borderRadius: 2, textTransform: "none", fontSize: "0.75rem", fontWeight: 500,
            background: "linear-gradient(to right, #2563eb, #7c3aed)", "&:hover": { opacity: 0.9 },
          }}
        >
          {t("chat.newChat")}
        </Button>
      </Box>
      <Box sx={{ flex: 1, overflowY: "auto", p: 0.75 }}>
        {sessions.length === 0 ? (
          <Typography variant="caption" sx={{ display: "block", px: 1, py: 4, textAlign: "center", color: "text.disabled" }}>
            {t("chat.noConversations")}
          </Typography>
        ) : (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.25 }}>
            {sessions.map((s) => (
              <Box
                key={s.id}
                onClick={() => onSelect(s)}
                sx={{
                  display: "flex", alignItems: "flex-start", gap: 1, borderRadius: 2,
                  px: 1.25, py: 1, textAlign: "left", cursor: "pointer",
                  bgcolor: activeSessionId === s.id ? "#eff6ff" : "transparent",
                  color: activeSessionId === s.id ? "#1d4ed8" : "text.primary",
                  "&:hover": { bgcolor: activeSessionId === s.id ? "#eff6ff" : "grey.50" },
                  "& .delete-btn": { display: "none" },
                  "&:hover .delete-btn": { display: "block" },
                }}
              >
                <ChatBubbleOutline sx={{ mt: 0.25, fontSize: 14, flexShrink: 0, color: "text.disabled" }} />
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography variant="caption" fontWeight={500} noWrap sx={{ display: "block" }}>{s.title}</Typography>
                  <Typography variant="caption" sx={{ fontSize: "0.625rem", color: "text.disabled" }}>{formatDate(s.updated_at)}</Typography>
                </Box>
                <IconButton
                  size="small"
                  className="delete-btn"
                  onClick={(e) => onDelete(s.id, e)}
                  title="Delete"
                  sx={{ mt: 0.25, p: 0.25, flexShrink: 0, color: "text.disabled", "&:hover": { bgcolor: "grey.200", color: "text.secondary" } }}
                >
                  <Close sx={{ fontSize: 12 }} />
                </IconButton>
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Paper>
  );
}

/* ── Control Center (Chat Page) ─────────────────────────────────────────── */

export default function Chat() {
  const { t } = useTranslation();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [contextView, setContextView] = useState<ContextView | null>({ type: "briefing" });
  const [pipelineStage, setPipelineStage] = useState<CandidateStatus | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [backendSuggestions, setBackendSuggestions] = useState<Suggestion[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<ActiveWorkflow | null>(null);
  const didAutoSelect = useRef(false);
  const loadedSessionRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: sessions, refresh: refreshSessions } = useApi(useCallback(() => listChatSessions(), []));
  const { data: candidates, refresh: refreshCandidates } = useApi(useCallback(() => listCandidates(), []));

  const candidatesRef = useRef(candidates);
  candidatesRef.current = candidates;

  // Auto-select most recent session
  useEffect(() => {
    if (didAutoSelect.current || !sessions) return;
    didAutoSelect.current = true;
    if (sessions.length > 0) {
      setActiveSessionId(sessions[0].id);
    } else {
      setMessages([candidates ? makeBriefing(candidates, t) : makeSimpleGreeting(t)]);
    }
  }, [sessions, candidates, t]);

  // Load messages when session changes
  // Uses loadedSessionRef to skip reload when handleSend just created the session
  // Uses candidatesRef to avoid re-triggering on refreshCandidates()
  useEffect(() => {
    if (!activeSessionId) return;
    if (loadedSessionRef.current === activeSessionId) return;
    loadedSessionRef.current = activeSessionId;
    getChatHistory(activeSessionId).then((msgs) => {
      const c = candidatesRef.current;
      if (msgs.length === 0) {
        setMessages([c ? makeBriefing(c, t) : makeSimpleGreeting(t)]);
      } else {
        setMessages(msgs);
      }
    });
  }, [activeSessionId, t]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Derive last action for context panel auto-switch
  const lastAction = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].action) return messages[i].action;
    }
    return undefined;
  }, [messages]);

  // Context auto-switch is now handled by backend context_hint in handleSend

  const suggestions = useMemo(
    () => backendSuggestions.length > 0
      ? backendSuggestions
      : buildSuggestions(messages, candidates ?? null, lastAction, t),
    [messages, candidates, lastAction, backendSuggestions, t],
  );

  /* ── Send ──────────────────────────────────────────────────────────────── */

  const handleSend = async (overrideMessage?: string) => {
    const text = overrideMessage || input.trim();
    if (!text || sending) return;
    if (!overrideMessage) setInput("");
    setSending(true);
    setStreamingText("");

    setMessages((prev) => [...prev, {
      id: "temp-" + Date.now(), user_id: "", role: "user",
      content: text, created_at: new Date().toISOString(),
    }]);

    // If a reply looks like raw JSON with a "message" field, extract just the text
    const cleanReply = (text: string): string => {
      if (text && text.trimStart().startsWith("{") && text.includes('"message"')) {
        try {
          const parsed = JSON.parse(text);
          if (typeof parsed.message === "string") return parsed.message;
        } catch { /* not JSON, use as-is */ }
      }
      return text;
    };

    // Accumulate streamed JSON and extract the "message" field progressively
    let accumulated = "";
    const extractMessage = (raw: string): string => {
      const match = raw.match(/"message"\s*:\s*"((?:[^"\\]|\\.)*)(?:"|$)/);
      if (!match) return "";
      return match[1]
        .replace(/\\n/g, "\n")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, "\\");
    };

    try {
      const response = await streamChatMessage(
        text,
        activeSessionId ?? undefined,
        (token) => {
          accumulated += token;
          const msg = extractMessage(accumulated);
          if (msg) setStreamingText(msg);
        },
        (stepEvent: WorkflowStepEvent) => {
          setActiveWorkflow((prev) => {
            const steps = prev?.steps ?? [];
            // Build updated steps array from the event
            const updated = [...steps];
            while (updated.length <= stepEvent.step_index) {
              updated.push({ label: "", status: "pending" });
            }
            updated[stepEvent.step_index] = {
              label: stepEvent.label,
              status: stepEvent.status as "pending" | "running" | "done" | "skipped",
            };
            return {
              workflow_id: stepEvent.workflow_id,
              workflow_type: prev?.workflow_type ?? "bulk_outreach",
              status: "running",
              current_step: stepEvent.step_index,
              total_steps: stepEvent.total_steps,
              steps: updated,
            };
          });
        },
      );

      setStreamingText("");
      if (!activeSessionId && response.session_id) {
        loadedSessionRef.current = response.session_id;
        setActiveSessionId(response.session_id);
      }
      refreshSessions();
      refreshCandidates();

      // Handle workflow status from done event
      if (response.workflow_id && response.workflow_status) {
        if (response.workflow_status === "done" || response.workflow_status === "cancelled") {
          // Clear tracker after a short delay so user sees the final state
          setTimeout(() => setActiveWorkflow(null), 3000);
          setActiveWorkflow((prev) =>
            prev ? { ...prev, status: response.workflow_status! } : null
          );
        } else if (response.workflow_status === "paused") {
          // Workflow paused at approval — clear the tracker (approval block shows in chat)
          setActiveWorkflow(null);
        }
      }

      setMessages((prev) => [...prev, {
        id: response.message_id || "reply-" + Date.now(),
        user_id: "", role: "assistant", content: cleanReply(response.reply),
        created_at: new Date().toISOString(),
        action: response.action, actionStatus: response.action ? "pending" : undefined,
        blocks: response.blocks,
      }]);

      // Apply backend suggestions and context hint
      if (response.suggestions && response.suggestions.length > 0) {
        setBackendSuggestions(response.suggestions);
      } else {
        setBackendSuggestions([]);
      }
      if (response.context_hint) {
        setContextView(response.context_hint);
        setPipelineStage(null);
      }
    } catch {
      setStreamingText("");
      setMessages((prev) => [...prev, {
        id: "error-" + Date.now(), user_id: "", role: "assistant",
        content: t("chat.errorMessage"),
        created_at: new Date().toISOString(),
      }]);
    } finally {
      setSending(false);
    }
  };

  /* ── Email handlers ────────────────────────────────────────────────────── */

  const handleEmailSend = async (emailId: string) => {
    const msg = messages.find((m) => m.action?.type === "compose_email" && m.action.email.id === emailId);
    const email = msg?.action?.type === "compose_email" ? msg.action.email : null;
    try {
      if (email) {
        await updateEmailDraft(emailId, {
          to_email: email.to_email, subject: email.subject, body: email.body,
          email_type: email.email_type, candidate_id: email.candidate_id,
          candidate_name: email.candidate_name,
        });
      }
      await sendEmail(emailId);
      if (msg) updateChatMessageStatus(msg.id, "sent").catch(() => {});
      setMessages((prev) => prev.map((m) =>
        m.action?.type === "compose_email" && m.action.email.id === emailId
          ? { ...m, actionStatus: "sent" as const } : m));
      const name = email?.candidate_name || "the candidate";
      const content = `Great news! Your email to ${name} has been sent successfully. Is there anything else?`;
      if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
      setMessages((prev) => [...prev, { id: "congrats-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
      refreshCandidates();
    } catch {
      const content = t("chat.failedToSendEmail");
      if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
      setMessages((prev) => [...prev, { id: "error-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    }
  };

  const handleEmailCancel = async (emailId: string) => {
    try { await deleteEmail(emailId); } catch { /* ignore */ }
    const msg = messages.find((m) => m.action?.type === "compose_email" && m.action.email.id === emailId);
    if (msg) updateChatMessageStatus(msg.id, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.action?.type === "compose_email" && m.action.email.id === emailId
        ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  const handleEmailFieldUpdate = (emailId: string, field: string, value: string) => {
    setMessages((prev) => prev.map((m) => {
      if (m.action?.type === "compose_email" && m.action.email.id === emailId) {
        return { ...m, action: { ...m.action, email: { ...m.action.email, [field]: value } } };
      }
      return m;
    }));
  };

  /* ── Resume upload handlers ────────────────────────────────────────────── */

  const handleResumeUpload = async (msgId: string, file: File, jobId: string) => {
    const candidate: Candidate = await uploadResume(file, jobId);
    updateChatMessageStatus(msgId, "uploaded").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, actionStatus: "uploaded" as const, uploadedCandidate: candidate } : m));
    const skills = candidate.skills?.slice(0, 3).join(", ") || "N/A";
    const content = `${candidate.name}'s resume has been uploaded!\n\n- Title: ${candidate.current_title || "N/A"}\n- Skills: ${skills}\n- Experience: ${candidate.experience_years ?? "N/A"} years\n\nWould you like me to match them to a job or draft an outreach email?`;
    if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
    setMessages((prev) => [...prev, { id: "resume-ok-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    refreshCandidates();
    setContextView({ type: "candidate", id: candidate.id });
  };

  const handleResumeCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  /* ── JD upload handlers ────────────────────────────────────────────────── */

  const handleJdUpload = async (msgId: string, file: File) => {
    const job: Job = await uploadJd(file);
    updateChatMessageStatus(msgId, "uploaded").catch(() => {});
    setMessages((prev) => prev.map((m) =>
      m.id === msgId ? { ...m, actionStatus: "uploaded" as const, uploadedJob: job } : m));
    const skills = job.required_skills?.slice(0, 3).join(", ") || "N/A";
    const content = `**${job.title}**${job.company ? ` at ${job.company}` : ""} has been uploaded!\n\n- Skills: ${skills}\n- Experience: ${job.experience_years ?? "N/A"} years\n- Location: ${job.location || "N/A"}${job.remote ? " (Remote)" : ""}\n\nWould you like me to match candidates to this job?`;
    if (activeSessionId) saveChatMessage(activeSessionId, content).catch(() => {});
    setMessages((prev) => [...prev, { id: "jd-ok-" + Date.now(), user_id: "", role: "assistant", content, created_at: new Date().toISOString() }]);
    setContextView({ type: "job", id: job.id });
  };

  const handleJdCancel = (msgId: string) => {
    updateChatMessageStatus(msgId, "cancelled").catch(() => {});
    setMessages((prev) => prev.map((m) => m.id === msgId ? { ...m, actionStatus: "cancelled" as const } : m));
  };

  /* ── Session handlers ──────────────────────────────────────────────────── */

  const handleNewChat = () => {
    loadedSessionRef.current = null;
    setActiveSessionId(null);
    setMessages([candidates ? makeBriefing(candidates, t) : makeSimpleGreeting(t)]);
    setContextView({ type: "briefing" });
    setPipelineStage(null);
  };

  const handleSelectSession = (s: ChatSession) => setActiveSessionId(s.id);

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteChatSession(id);
    if (activeSessionId === id) { loadedSessionRef.current = null; setActiveSessionId(null); setMessages([]); }
    refreshSessions();
  };

  const handleClearAll = async () => {
    await clearChatHistory();
    loadedSessionRef.current = null;
    setMessages([]); setActiveSessionId(null); refreshSessions();
  };

  /* ── Pipeline + Context ────────────────────────────────────────────────── */

  const handleStageClick = (stage: CandidateStatus) => {
    if (pipelineStage === stage) {
      setPipelineStage(null); setContextView({ type: "briefing" });
    } else {
      setPipelineStage(stage); setContextView({ type: "pipeline_stage", stage });
    }
  };

  const handleViewCandidate = (id: string) => { setContextView({ type: "candidate", id }); setPipelineStage(null); };
  const handleViewJob = (id: string) => { setContextView({ type: "job", id }); setPipelineStage(null); };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  /* ── Render ────────────────────────────────────────────────────────────── */

  return (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", gap: 1.5 }}>
      {/* Pipeline Bar */}
      <PipelineBar candidates={candidates ?? []} activeStage={pipelineStage} onStageClick={handleStageClick} />

      {/* Workflow Tracker */}
      {activeWorkflow && (
        <WorkflowTracker
          workflow={activeWorkflow}
          onCancel={() => {
            setActiveWorkflow(null);
            handleSend("cancel workflow");
          }}
        />
      )}

      {/* Main: sessions + chat + context */}
      <Box sx={{ display: "flex", minHeight: 0, flex: 1, gap: 1.5 }}>
        {/* Sessions */}
        <SessionSidebar sessions={sessions ?? []} activeSessionId={activeSessionId}
          onSelect={handleSelectSession} onDelete={handleDeleteSession} onNewChat={handleNewChat} />

        {/* Chat */}
        <Box sx={{ display: "flex", flexDirection: "column", minWidth: 0, flex: 1 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", pb: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Avatar
                src="/ai-chan-avatar.png"
                alt="Erika Chan"
                sx={{ width: 28, height: 28 }}
              />
              <Typography variant="body2" fontWeight={600} color="text.primary">Erika Chan</Typography>
            </Box>
            <Button
              size="small" variant="outlined" color="inherit"
              onClick={handleClearAll}
              startIcon={<DeleteOutline sx={{ fontSize: 12 }} />}
              sx={{ fontSize: "0.625rem", fontWeight: 500, color: "text.secondary", borderColor: "grey.200", borderRadius: 2, textTransform: "none" }}
            >
              {t("chat.clear")}
            </Button>
          </Box>

          <Paper
            variant="outlined"
            sx={{
              flex: 1, overflowY: "auto", borderRadius: 3, p: 2,
              display: "flex", flexDirection: "column", gap: 1.5,
            }}
          >
            {messages.map((msg) => (
              <Box key={msg.id} sx={{ display: "flex", gap: 1.25, justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                {msg.role === "assistant" && (
                  <Avatar
                    src="/ai-chan-avatar.png"
                    alt="Erika"
                    sx={{ width: 24, height: 24, flexShrink: 0 }}
                  />
                )}
                <Box sx={{ maxWidth: "85%" }}>
                  <Paper
                    elevation={0}
                    sx={{
                      borderRadius: 3, px: 1.75, py: 1.25,
                      bgcolor: msg.role === "user" ? "primary.main" : "grey.50",
                      color: msg.role === "user" ? "white" : "text.primary",
                    }}
                  >
                    <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{msg.content}</Typography>
                  </Paper>

                  {msg.action?.type === "compose_email" && (
                    <EmailComposeCard email={msg.action.email}
                      status={(msg.actionStatus ?? "pending") as "pending" | "sent" | "cancelled"}
                      onSend={handleEmailSend} onCancel={handleEmailCancel} onUpdateField={handleEmailFieldUpdate} />
                  )}
                  {msg.action?.type === "upload_resume" && (
                    <ResumeUploadCard
                      status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                      defaultJobId={msg.action.job_id}
                      uploadedCandidate={(msg as ChatMessage & { uploadedCandidate?: Candidate }).uploadedCandidate}
                      onUpload={(file, jobId) => handleResumeUpload(msg.id, file, jobId)}
                      onCancel={() => handleResumeCancel(msg.id)} />
                  )}
                  {msg.action?.type === "upload_jd" && (
                    <JdUploadCard
                      status={(msg.actionStatus === "uploaded" ? "uploaded" : msg.actionStatus === "cancelled" ? "cancelled" : "pending") as "pending" | "uploaded" | "cancelled"}
                      uploadedJob={(msg as ChatMessage & { uploadedJob?: Job }).uploadedJob}
                      onUpload={(file) => handleJdUpload(msg.id, file)}
                      onCancel={() => handleJdCancel(msg.id)} />
                  )}
                  {msg.action?.type === "create_job" && (
                    <JobCreatedCard job={msg.action.job} />
                  )}
                  {msg.action?.type === "create_candidate" && (
                    <CandidateCreatedCard candidate={msg.action.candidate} />
                  )}
                  {msg.action?.type === "market_analysis" && msg.action.report && (
                    <MarketReportCard report={msg.action.report} />
                  )}

                  {msg.blocks && msg.blocks.length > 0 && (
                    <MessageBlocks
                      blocks={msg.blocks}
                      onSendPrompt={(p) => handleSend(p)}
                      onViewCandidate={handleViewCandidate}
                      onViewJob={handleViewJob}
                    />
                  )}
                </Box>
              </Box>
            ))}

            {sending && (
              <Box sx={{ display: "flex", gap: 1.25 }}>
                <Avatar
                  src="/ai-chan-avatar.png"
                  alt="Erika"
                  sx={{ width: 24, height: 24, flexShrink: 0 }}
                />
                <Box sx={{ maxWidth: "85%" }}>
                  <Paper elevation={0} sx={{ borderRadius: 3, px: 1.75, py: 1.25, bgcolor: "grey.50", color: "text.primary" }}>
                    {streamingText ? (
                      <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
                        {streamingText}
                        <Box
                          component="span"
                          sx={{
                            ml: 0.25, display: "inline-block", height: 16, width: 4,
                            bgcolor: "grey.400", animation: "pulse 1s ease-in-out infinite",
                            "@keyframes pulse": {
                              "0%, 100%": { opacity: 1 },
                              "50%": { opacity: 0.3 },
                            },
                          }}
                        />
                      </Typography>
                    ) : (
                      <CircularProgress size={16} sx={{ color: "grey.400" }} />
                    )}
                  </Paper>
                </Box>
              </Box>
            )}
            <div ref={messagesEndRef} />
          </Paper>

          <SmartActionBar suggestions={suggestions} onSelect={(p) => handleSend(p)} />

          <Box sx={{ display: "flex", gap: 1, pt: 0.5 }}>
            <TextField
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("chat.askErika")}
              multiline
              maxRows={4}
              fullWidth
              size="small"
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 3,
                  "& fieldset": { borderColor: "grey.300" },
                  "&:hover fieldset": { borderColor: "primary.light" },
                  "&.Mui-focused fieldset": { borderColor: "primary.main" },
                },
                "& .MuiInputBase-input": { fontSize: "0.875rem", py: 1.25, px: 2 },
              }}
            />
            <IconButton
              onClick={() => handleSend()}
              disabled={sending || !input.trim()}
              sx={{
                bgcolor: "primary.main", color: "white", borderRadius: 3, width: 44,
                "&:hover": { bgcolor: "primary.dark" },
                "&.Mui-disabled": { bgcolor: "grey.300", color: "white" },
              }}
            >
              <SendOutlined sx={{ fontSize: 18 }} />
            </IconButton>
          </Box>
        </Box>

        {/* Context Panel */}
        <ContextPanel view={contextView}
          onClose={() => { setContextView(null); setPipelineStage(null); }}
          onViewCandidate={handleViewCandidate} onViewJob={handleViewJob}
          onSendPrompt={(p) => handleSend(p)} />
      </Box>
    </Box>
  );
}
