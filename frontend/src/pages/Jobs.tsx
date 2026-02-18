import { useCallback, useRef, useState } from "react";
import {
  AddOutlined,
  DeleteOutline,
  PeopleOutline,
  EditOutlined,
  CloseOutlined,
  SaveOutlined,
  MailOutline,
  SendOutlined,
  AttachFileOutlined,
  WorkOutline,
} from "@mui/icons-material";
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid2 as Grid,
  IconButton,
  MenuItem,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useApi } from "../hooks/useApi";
import {
  listJobs,
  createJob,
  updateJob,
  deleteJob,
  getRankedCandidates,
  composeEmailWithAttachment,
  sendEmail,
} from "../lib/api";
import type { Job, Candidate } from "../types";

export default function Jobs() {
  const { data: jobs, refresh } = useApi(useCallback(() => listJobs(), []));
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [postedDate, setPostedDate] = useState("");
  const [rawText, setRawText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [emailJob, setEmailJob] = useState<Job | null>(null);

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
    <Stack spacing={2}>
      {/* Header row */}
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          All Jobs{" "}
          <Typography component="span" variant="body2" sx={{ fontWeight: 400, color: "grey.500" }}>
            ({jobs?.length ?? 0})
          </Typography>
        </Typography>
        {!isFormOpen && (
          <Button
            variant="contained"
            startIcon={<AddOutlined />}
            onClick={() => { resetForm(); setShowForm(true); }}
          >
            New Job
          </Button>
        )}
      </Box>

      {/* Create / Edit form */}
      {isFormOpen && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack spacing={2.5}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {editingJob ? "Edit Job" : "New Job"}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  label="Job Title"
                  size="small"
                  fullWidth
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Senior Frontend Engineer"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  label="Company"
                  size="small"
                  fullWidth
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="e.g. Acme Corp"
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <TextField
                  label="Posted Date"
                  size="small"
                  fullWidth
                  type="date"
                  value={postedDate}
                  onChange={(e) => setPostedDate(e.target.value)}
                  slotProps={{ inputLabel: { shrink: true } }}
                />
              </Grid>
            </Grid>
            <TextField
              label="Job Description"
              fullWidth
              multiline
              rows={8}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Paste the full job description here..."
            />
            <Stack direction="row" spacing={1}>
              {editingJob ? (
                <>
                  <Button
                    variant="contained"
                    startIcon={<SaveOutlined />}
                    onClick={handleUpdate}
                    disabled={submitting}
                  >
                    {submitting ? "Saving..." : "Save Changes"}
                  </Button>
                  <Button variant="outlined" onClick={cancelEdit}>
                    Cancel
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="contained"
                    onClick={handleCreate}
                    disabled={submitting || !rawText.trim()}
                  >
                    {submitting ? "Creating..." : "Create Job"}
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => { setShowForm(false); resetForm(); }}
                  >
                    Cancel
                  </Button>
                </>
              )}
            </Stack>
          </Stack>
        </Paper>
      )}

      {/* Job list */}
      <Grid container spacing={1.5}>
        {jobs?.map((job) => (
          <Grid key={job.id} size={{ xs: 12, sm: 6, lg: 4 }}>
            <Card
              variant="outlined"
              sx={{
                height: "100%",
                transition: "box-shadow 0.2s",
                "&:hover": { boxShadow: 3 },
                "&:hover [data-job-actions]": { opacity: 1 },
              }}
            >
              <CardContent sx={{ p: 2.5, "&:last-child": { pb: 2.5 } }}>
                <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: "grey.900" }}>
                      {job.title || "Untitled"}
                    </Typography>
                    {job.company && (
                      <Typography variant="body2" sx={{ mt: 0.25, color: "grey.600" }}>
                        {job.company}
                      </Typography>
                    )}
                    {job.posted_date && (
                      <Typography variant="caption" sx={{ mt: 0.25, display: "block", color: "grey.500" }}>
                        Posted: {job.posted_date}
                      </Typography>
                    )}
                  </Box>
                  <Box
                    data-job-actions
                    sx={{ display: "inline-flex", gap: 0.25, opacity: 0, transition: "opacity 0.2s" }}
                  >
                    <Tooltip title="Send Email to Company">
                      <IconButton
                        size="small"
                        onClick={() => setEmailJob(job)}
                        sx={{ color: "grey.400", "&:hover": { color: "success.main" } }}
                      >
                        <MailOutline fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Edit">
                      <IconButton
                        size="small"
                        onClick={() => startEdit(job)}
                        sx={{ color: "grey.400", "&:hover": { color: "primary.main" } }}
                      >
                        <EditOutlined fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton
                        size="small"
                        onClick={() => handleDelete(job.id)}
                        sx={{ color: "grey.400", "&:hover": { color: "error.main" } }}
                      >
                        <DeleteOutline fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
                {job.required_skills.length > 0 && (
                  <Stack direction="row" spacing={0.5} sx={{ mt: 1.5, flexWrap: "wrap", gap: 0.5 }}>
                    {job.required_skills.slice(0, 4).map((s) => (
                      <Chip
                        key={s}
                        label={s}
                        size="small"
                        sx={{
                          bgcolor: "blue.50",
                          color: "primary.dark",
                          fontSize: "0.75rem",
                          height: 24,
                        }}
                      />
                    ))}
                  </Stack>
                )}
                <Stack direction="row" spacing={0.5} sx={{ mt: 1.5, alignItems: "center" }}>
                  <PeopleOutline sx={{ fontSize: 16, color: "grey.500" }} />
                  <Typography variant="caption" sx={{ color: "grey.500" }}>
                    {job.candidate_count} matched candidate
                    {job.candidate_count !== 1 ? "s" : ""}
                  </Typography>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {(!jobs || jobs.length === 0) && !showForm && (
        <Paper
          variant="outlined"
          sx={{
            p: 6,
            textAlign: "center",
            borderStyle: "dashed",
            borderColor: "grey.300",
          }}
        >
          <WorkOutline sx={{ fontSize: 40, color: "grey.400", mx: "auto", display: "block" }} />
          <Typography variant="body2" sx={{ mt: 1.5, color: "grey.600" }}>
            No jobs yet. Click <strong>New Job</strong> to add one.
          </Typography>
        </Paper>
      )}

      {/* Email modal */}
      {emailJob && (
        <JobEmailModal
          job={emailJob}
          onClose={() => setEmailJob(null)}
        />
      )}
    </Stack>
  );
}

/* -- Job Email Modal -------------------------------------------------------- */

function JobEmailModal({ job, onClose }: { job: Job; onClose: () => void }) {
  // Load all candidates ranked by vector similarity to this job
  const { data: candidates } = useApi(
    useCallback(() => getRankedCandidates(job.id), [job.id])
  );
  const [toEmail, setToEmail] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [useCandidateResume, setUseCandidateResume] = useState(false);
  const [attachment, setAttachment] = useState<File | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [subject, setSubject] = useState(
    `Candidate Recommendation \u2014 ${job.title} at ${job.company}`
  );
  const [body, setBody] = useState(
    `Dear Hiring Manager,\n\nI am writing to recommend a candidate for the ${job.title} position at ${job.company}.\n\nPlease find the candidate's resume attached. I believe their background and experience make them a strong fit for this role.\n\nI would welcome the opportunity to discuss this further at your convenience.\n\nBest regards`
  );
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const selectedCandidate = candidates?.find(
    (c) => c.id === selectedCandidateId
  );

  const handleCandidateChange = (cid: string) => {
    setSelectedCandidateId(cid);
    setUseCandidateResume(false);
    setAttachment(null);
  };

  const handleSend = async (draft: boolean) => {
    if (!toEmail.trim() || !subject.trim()) return;
    setSending(true);
    try {
      const email = await composeEmailWithAttachment({
        to_email: toEmail,
        subject,
        body,
        email_type: "outreach",
        candidate_id: selectedCandidateId,
        candidate_name: selectedCandidate?.name || "",
        job_id: job.id,
        use_candidate_resume: useCandidateResume && !attachment,
        attachment: attachment || undefined,
      });

      if (!draft) {
        await sendEmail(email.id);
      }

      setSent(true);
      setTimeout(onClose, 1000);
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          Send Email to Company — {job.title}
        </Typography>
        <IconButton size="small" onClick={onClose} sx={{ color: "grey.500" }}>
          <CloseOutlined />
        </IconButton>
      </DialogTitle>

      {sent ? (
        <DialogContent sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="body2" sx={{ fontWeight: 500, color: "success.main" }}>
            Email saved successfully!
          </Typography>
        </DialogContent>
      ) : (
        <>
          <DialogContent dividers>
            <Stack spacing={2.5}>
              {/* To */}
              <TextField
                label="Company Email"
                size="small"
                fullWidth
                type="email"
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder="hr@company.com"
              />

              {/* Candidate selector */}
              <TextField
                label="Select Candidate (optional)"
                size="small"
                fullWidth
                select
                value={selectedCandidateId}
                onChange={(e) => handleCandidateChange(e.target.value)}
              >
                <MenuItem value="">— None —</MenuItem>
                {candidates?.map((c) => (
                  <MenuItem key={c.id} value={c.id}>
                    {c.name} — {c.current_title || "N/A"} ({Math.round(c.match_score * 100)}% match)
                  </MenuItem>
                ))}
              </TextField>

              {/* Attachment */}
              {selectedCandidateId && (
                <Stack spacing={1}>
                  {selectedCandidate?.resume_path && (
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={useCandidateResume && !attachment}
                          onChange={(e) => {
                            setUseCandidateResume(e.target.checked);
                            if (e.target.checked) setAttachment(null);
                          }}
                        />
                      }
                      label={
                        <Stack direction="row" spacing={0.5} sx={{ alignItems: "center" }}>
                          <AttachFileOutlined sx={{ fontSize: 16, color: "grey.500" }} />
                          <Typography variant="body2">Attach candidate's resume</Typography>
                        </Stack>
                      }
                    />
                  )}
                  <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                    <Button
                      variant="outlined"
                      size="small"
                      component="label"
                      startIcon={<AttachFileOutlined />}
                      sx={{ textTransform: "none" }}
                    >
                      {attachment ? attachment.name : "Upload PDF"}
                      <input
                        ref={fileRef}
                        type="file"
                        accept=".pdf"
                        hidden
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) {
                            setAttachment(f);
                            setUseCandidateResume(false);
                          }
                        }}
                      />
                    </Button>
                    {attachment && (
                      <Button
                        size="small"
                        color="error"
                        sx={{ textTransform: "none" }}
                        onClick={() => {
                          setAttachment(null);
                          if (fileRef.current) fileRef.current.value = "";
                        }}
                      >
                        Remove
                      </Button>
                    )}
                  </Stack>
                </Stack>
              )}

              {/* Subject */}
              <TextField
                label="Subject"
                size="small"
                fullWidth
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />

              {/* Body */}
              <TextField
                label="Body"
                fullWidth
                multiline
                rows={8}
                value={body}
                onChange={(e) => setBody(e.target.value)}
              />
            </Stack>
          </DialogContent>

          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button
              variant="outlined"
              onClick={() => handleSend(true)}
              disabled={sending || !toEmail.trim()}
            >
              {sending ? "Saving..." : "Save as Draft"}
            </Button>
            <Button
              variant="contained"
              startIcon={<SendOutlined />}
              onClick={() => handleSend(false)}
              disabled={sending || !toEmail.trim()}
            >
              {sending ? "Sending..." : "Send Now"}
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}
