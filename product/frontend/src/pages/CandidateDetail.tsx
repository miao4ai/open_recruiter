import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowBackOutlined,
  MailOutline,
  DeleteOutline,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  AutoAwesomeOutlined,
  LinkOutlined,
  LinkOffOutlined,
} from "@mui/icons-material";
import {
  Box,
  Stack,
  Button,
  Paper,
  Grid2 as Grid,
  TextField,
  MenuItem,
  Chip,
  Typography,
  CircularProgress,
} from "@mui/material";
import { useApi } from "../hooks/useApi";
import RefreshOutlined from "@mui/icons-material/RefreshOutlined";
import {
  getCandidate,
  listEmails,
  listJobs,
  updateCandidate,
  deleteCandidate,
  matchCandidates,
  composeEmail,
  reparseCandidate,
  linkCandidateJob,
  unlinkCandidateJob,
} from "../lib/api";
import type { Candidate, CandidateJobMatch } from "../types";

export default function CandidateDetail() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: candidate, loading, refresh } = useApi(
    useCallback(() => getCandidate(id!), [id])
  );
  const { data: emails } = useApi(
    useCallback(() => listEmails(id!), [id])
  );
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<Candidate>>({});
  const [saving, setSaving] = useState(false);

  // Re-parse state
  const [reparsing, setReparsing] = useState(false);

  // Match analysis state
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [typewriterText, setTypewriterText] = useState("");
  const [typewriterDone, setTypewriterDone] = useState(true);

  // Link job state
  const [linkJobId, setLinkJobId] = useState("");
  const [linking, setLinking] = useState(false);

  if (loading) {
    return (
      <Typography variant="body2" sx={{ color: "grey.500" }}>
        {t("common.loading")}
      </Typography>
    );
  }
  if (!candidate) {
    return (
      <Typography variant="body2" sx={{ color: "error.main" }}>
        {t("candidateDetail.candidateNotFound")}
      </Typography>
    );
  }

  const jobMatches: CandidateJobMatch[] = candidate.job_matches ?? [];
  // Pick the selected or best match for display
  const activeMatch = selectedJobId
    ? jobMatches.find((m) => m.job_id === selectedJobId)
    : jobMatches.length > 0
      ? jobMatches.reduce((best, m) => (m.match_score > best.match_score ? m : best), jobMatches[0])
      : null;

  const scorePct = activeMatch ? Math.round(activeMatch.match_score * 100) : 0;
  const hasAnalysis = !!(activeMatch?.match_reasoning);

  const startEdit = () => {
    setForm({
      name: candidate.name,
      email: candidate.email,
      phone: candidate.phone,
      current_title: candidate.current_title,
      current_company: candidate.current_company,
      skills: candidate.skills,
      experience_years: candidate.experience_years,
      location: candidate.location,
      date_of_birth: candidate.date_of_birth,
      notes: candidate.notes,
    });
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateCandidate(id!, form);
      setEditing(false);
      refresh();
    } finally {
      setSaving(false);
    }
  };

  const handleSendEmail = async () => {
    await composeEmail({
      to_email: candidate.email,
      subject: `Exciting Career Opportunity`,
      body: `Hi ${candidate.name || "there"},\n\nI came across your profile and was very impressed by your background and experience.\n\nWould you be open to a brief conversation? I'd love to share more details about an opportunity that I think would be a great fit.\n\nLooking forward to hearing from you!\n\nBest regards`,
      email_type: "outreach",
      candidate_id: candidate.id,
      candidate_name: candidate.name,
    });
    navigate("/outreach");
  };

  const handleDelete = async () => {
    if (!confirm(t("candidateDetail.confirmDeleteCandidate"))) return;
    await deleteCandidate(id!);
    navigate("/candidates");
  };

  const handleReparse = async () => {
    setReparsing(true);
    try {
      await reparseCandidate(id!);
      refresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || t("candidateDetail.reparseFailed"));
    } finally {
      setReparsing(false);
    }
  };

  const handleAnalyze = async () => {
    const jobId = selectedJobId || activeMatch?.job_id;
    if (!jobId) return;
    setAnalyzing(true);
    setTypewriterText("");
    setTypewriterDone(false);
    try {
      const results = await matchCandidates(jobId, [candidate.id]);
      const result = results[0];
      if (result?.reasoning) {
        setTypewriterText(result.reasoning);
      }
      refresh();
    } finally {
      setAnalyzing(false);
    }
  };

  const handleLinkJob = async () => {
    if (!linkJobId) return;
    setLinking(true);
    try {
      await linkCandidateJob(id!, linkJobId);
      setLinkJobId("");
      refresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Link failed");
    } finally {
      setLinking(false);
    }
  };

  const handleUnlinkJob = async (jobId: string) => {
    if (!confirm(t("candidateDetail.unlinkJob"))) return;
    try {
      await unlinkCandidateJob(id!, jobId);
      refresh();
    } catch (err: any) {
      alert(err?.response?.data?.detail || "Unlink failed");
    }
  };

  const updateField = (key: string, value: string | string[] | number | null) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  // Determine which reasoning text to show
  const showTypewriter = !typewriterDone && typewriterText;
  const reasoningText = showTypewriter ? typewriterText : activeMatch?.match_reasoning || "";

  const scoreColor =
    scorePct >= 70
      ? "#10b981"
      : scorePct >= 40
        ? "#f59e0b"
        : "#ef4444";

  const scoreTextColor =
    scorePct >= 70
      ? "#059669"
      : scorePct >= 40
        ? "#d97706"
        : "#ef4444";

  // Jobs not yet linked (for link selector)
  const linkedJobIds = new Set(jobMatches.map((m) => m.job_id));
  const availableJobs = jobs?.filter((j) => !linkedJobIds.has(j.id)) ?? [];

  return (
    <Stack spacing={3}>
      {/* Back link */}
      <Button
        component={Link}
        to="/candidates"
        startIcon={<ArrowBackOutlined sx={{ fontSize: 16 }} />}
        sx={{
          alignSelf: "flex-start",
          fontSize: 14,
          color: "grey.600",
          textTransform: "none",
          "&:hover": { color: "grey.800", bgcolor: "transparent" },
        }}
      >
        {t("candidateDetail.backToCandidates")}
      </Button>

      {/* Action toolbar */}
      <Paper variant="outlined" sx={{ px: 2.5, py: 1.5, borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="h6" sx={{ fontWeight: 600, mr: 1 }}>
            {candidate.name || t("common.unnamed")}
          </Typography>
          {candidate.current_title && (
            <Typography variant="body2" sx={{ color: "grey.500" }}>
              {candidate.current_title}
              {candidate.current_company ? ` ${t("dashboard.at", { company: candidate.current_company })}` : ""}
            </Typography>
          )}
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center">
          <Button
            onClick={handleSendEmail}
            variant="contained"
            size="small"
            startIcon={<MailOutline sx={{ fontSize: 14 }} />}
            sx={{ fontSize: 12, textTransform: "none", px: 1.5, py: 0.75 }}
          >
            {t("candidateDetail.sendEmail")}
          </Button>
          <Button
            onClick={handleReparse}
            disabled={reparsing}
            variant="outlined"
            size="small"
            startIcon={
              reparsing ? (
                <CircularProgress size={14} />
              ) : (
                <RefreshOutlined sx={{ fontSize: 14 }} />
              )
            }
            sx={{
              fontSize: 12, textTransform: "none",
              borderColor: "grey.300", color: "grey.600",
              "&:hover": { bgcolor: "grey.50", borderColor: "grey.300" },
              px: 1.5, py: 0.75,
            }}
          >
            {reparsing ? t("candidateDetail.parsing") : t("candidateDetail.reparseResume")}
          </Button>
          {!editing ? (
            <Button
              onClick={startEdit}
              variant="outlined"
              size="small"
              startIcon={<EditOutlined sx={{ fontSize: 14 }} />}
              sx={{
                fontSize: 12, textTransform: "none",
                borderColor: "grey.300", color: "grey.600",
                "&:hover": { bgcolor: "grey.50" },
                px: 1, py: 0.75,
              }}
            >
              {t("common.edit")}
            </Button>
          ) : (
            <Stack direction="row" spacing={0.5}>
              <Button
                onClick={handleSave}
                disabled={saving}
                variant="contained"
                size="small"
                startIcon={<SaveOutlined sx={{ fontSize: 14 }} />}
                sx={{ fontSize: 12, textTransform: "none", px: 1, py: 0.75 }}
              >
                {saving ? "..." : t("common.save")}
              </Button>
              <Button
                onClick={() => setEditing(false)}
                variant="outlined"
                size="small"
                sx={{
                  fontSize: 12, textTransform: "none",
                  borderColor: "grey.300", color: "grey.600",
                  "&:hover": { bgcolor: "grey.50" },
                  px: 1, py: 0.75, minWidth: "auto",
                }}
              >
                <CloseOutlined sx={{ fontSize: 14 }} />
              </Button>
            </Stack>
          )}
          <Button
            onClick={handleDelete}
            variant="outlined"
            size="small"
            startIcon={<DeleteOutline sx={{ fontSize: 14 }} />}
            sx={{
              fontSize: 12, textTransform: "none",
              borderColor: "grey.300", color: "#dc2626",
              "&:hover": { bgcolor: "#fef2f2", borderColor: "grey.300" },
              px: 1.5, py: 0.75,
            }}
          >
            {t("common.delete")}
          </Button>
        </Stack>
      </Paper>

      <Grid container spacing={3}>
        {/* Left: info card */}
        <Grid size={{ xs: 12, lg: 5 }}>
          <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
            <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {t("candidateDetail.profile")}
              </Typography>
            </Box>

            {editing ? (
              <Stack spacing={2} sx={{ mt: 2 }}>
                <TextField
                  label={t("candidateDetail.fieldName")}
                  size="small"
                  fullWidth
                  value={form.name ?? ""}
                  onChange={(e) => updateField("name", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldEmail")}
                  size="small"
                  fullWidth
                  value={form.email ?? ""}
                  onChange={(e) => updateField("email", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldPhone")}
                  size="small"
                  fullWidth
                  value={form.phone ?? ""}
                  onChange={(e) => updateField("phone", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldTitle")}
                  size="small"
                  fullWidth
                  value={form.current_title ?? ""}
                  onChange={(e) => updateField("current_title", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldCompany")}
                  size="small"
                  fullWidth
                  value={form.current_company ?? ""}
                  onChange={(e) => updateField("current_company", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldLocation")}
                  size="small"
                  fullWidth
                  value={form.location ?? ""}
                  onChange={(e) => updateField("location", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldDateOfBirth")}
                  size="small"
                  fullWidth
                  type="date"
                  InputLabelProps={{ shrink: true }}
                  value={form.date_of_birth ?? ""}
                  onChange={(e) => updateField("date_of_birth", e.target.value)}
                />
                <TextField
                  label={t("candidateDetail.fieldExperience")}
                  size="small"
                  fullWidth
                  type="number"
                  value={form.experience_years?.toString() ?? ""}
                  onChange={(e) =>
                    updateField(
                      "experience_years",
                      e.target.value ? parseInt(e.target.value, 10) || null : null
                    )
                  }
                />
                <TextField
                  label={t("candidateDetail.fieldSkills")}
                  size="small"
                  fullWidth
                  value={(form.skills ?? []).join(", ")}
                  onChange={(e) =>
                    updateField(
                      "skills",
                      e.target.value
                        .split(",")
                        .map((s) => s.trim())
                        .filter(Boolean)
                    )
                  }
                />
                <TextField
                  label={t("candidateDetail.fieldNotes")}
                  size="small"
                  fullWidth
                  multiline
                  rows={3}
                  value={form.notes ?? ""}
                  onChange={(e) => updateField("notes", e.target.value)}
                />
              </Stack>
            ) : (
              <>
                {candidate.current_title && (
                  <Typography variant="body2" sx={{ color: "grey.600" }}>
                    {candidate.current_title}
                    {candidate.current_company
                      ? ` ${t("dashboard.at", { company: candidate.current_company })}`
                      : ""}
                  </Typography>
                )}

                <Stack spacing={1} sx={{ mt: 2, fontSize: 14 }}>
                  {candidate.email && (
                    <Typography variant="body2">
                      <Box component="span" sx={{ color: "grey.600" }}>{t("candidateDetail.emailLabel")}</Box>{" "}
                      {candidate.email}
                    </Typography>
                  )}
                  {candidate.phone && (
                    <Typography variant="body2">
                      <Box component="span" sx={{ color: "grey.600" }}>{t("candidateDetail.phoneLabel")}</Box>{" "}
                      {candidate.phone}
                    </Typography>
                  )}
                  {candidate.location && (
                    <Typography variant="body2">
                      <Box component="span" sx={{ color: "grey.600" }}>{t("candidateDetail.locationLabel")}</Box>{" "}
                      {candidate.location}
                    </Typography>
                  )}
                  {candidate.experience_years != null && (
                    <Typography variant="body2">
                      <Box component="span" sx={{ color: "grey.600" }}>{t("candidateDetail.experienceLabel")}</Box>{" "}
                      {candidate.experience_years} {t("common.years")}
                    </Typography>
                  )}
                  {candidate.date_of_birth && (
                    <Typography variant="body2">
                      <Box component="span" sx={{ color: "grey.600" }}>{t("candidateDetail.dobLabel")}</Box>{" "}
                      {candidate.date_of_birth}
                    </Typography>
                  )}
                </Stack>

                {/* Linked Jobs */}
                <Box sx={{ mt: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{ mb: 0.5, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                  >
                    {t("candidateDetail.linkedJobs")} ({jobMatches.length})
                  </Typography>
                  {jobMatches.length > 0 ? (
                    <Stack spacing={0.75}>
                      {jobMatches.map((m) => (
                        <Box
                          key={m.job_id}
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            p: 0.75,
                            borderRadius: 1,
                            bgcolor: selectedJobId === m.job_id ? "action.selected" : "grey.50",
                            cursor: "pointer",
                            "&:hover": { bgcolor: "action.hover" },
                          }}
                          onClick={() => setSelectedJobId(m.job_id === selectedJobId ? "" : m.job_id)}
                        >
                          <Box sx={{ minWidth: 0 }}>
                            <Typography variant="body2" sx={{ fontWeight: 500, fontSize: 13 }}>
                              {m.job_title || m.job_id}
                            </Typography>
                            {m.job_company && (
                              <Typography variant="caption" sx={{ color: "grey.500" }}>
                                {m.job_company}
                              </Typography>
                            )}
                          </Box>
                          <Stack direction="row" spacing={0.5} alignItems="center">
                            {m.match_score > 0 && (
                              <Chip
                                label={`${Math.round(m.match_score * 100)}%`}
                                size="small"
                                sx={{
                                  fontSize: 11,
                                  height: 20,
                                  bgcolor: m.match_score >= 0.7 ? "#d1fae5" : m.match_score >= 0.4 ? "#fef3c7" : "#fee2e2",
                                  color: m.match_score >= 0.7 ? "#047857" : m.match_score >= 0.4 ? "#b45309" : "#dc2626",
                                }}
                              />
                            )}
                            <Button
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleUnlinkJob(m.job_id);
                              }}
                              sx={{ minWidth: "auto", p: 0.25, color: "grey.400", "&:hover": { color: "error.main" } }}
                            >
                              <LinkOffOutlined sx={{ fontSize: 16 }} />
                            </Button>
                          </Stack>
                        </Box>
                      ))}
                    </Stack>
                  ) : (
                    <Typography variant="body2" sx={{ color: "grey.500", fontSize: 13 }}>
                      {t("candidateDetail.noLinkedJobs")}
                    </Typography>
                  )}

                  {/* Link to job */}
                  {availableJobs.length > 0 && (
                    <Stack direction="row" spacing={0.5} sx={{ mt: 1 }}>
                      <TextField
                        select
                        size="small"
                        value={linkJobId}
                        onChange={(e) => setLinkJobId(e.target.value)}
                        sx={{ flex: 1 }}
                      >
                        <MenuItem value="">{t("candidateDetail.linkToJobOption")}</MenuItem>
                        {availableJobs.map((j) => (
                          <MenuItem key={j.id} value={j.id}>
                            {j.title} -- {j.company}
                          </MenuItem>
                        ))}
                      </TextField>
                      <Button
                        onClick={handleLinkJob}
                        disabled={!linkJobId || linking}
                        variant="outlined"
                        size="small"
                        sx={{
                          fontSize: 12,
                          textTransform: "none",
                          borderColor: "grey.300",
                          px: 1,
                          minWidth: "auto",
                        }}
                      >
                        {linking ? <CircularProgress size={14} /> : <LinkOutlined sx={{ fontSize: 16 }} />}
                      </Button>
                    </Stack>
                  )}
                </Box>

                {/* Skills */}
                {candidate.skills.length > 0 && (
                  <Box sx={{ mt: 2 }}>
                    <Typography
                      variant="caption"
                      sx={{ mb: 1, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                    >
                      {t("candidateDetail.skills")}
                    </Typography>
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                      {candidate.skills.map((s) => (
                        <Chip
                          key={s}
                          label={s}
                          size="small"
                          sx={{
                            bgcolor: "#eff6ff",
                            color: "#1d4ed8",
                            fontSize: 12,
                          }}
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                {/* Notes */}
                <Box sx={{ mt: 2 }}>
                  <Typography
                    variant="caption"
                    sx={{ mb: 0.5, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                  >
                    {t("candidateDetail.notes")}
                  </Typography>
                  <Typography variant="body2" sx={{ color: "grey.700" }}>
                    {candidate.notes || t("candidateDetail.noNotes")}
                  </Typography>
                </Box>
              </>
            )}
          </Paper>
        </Grid>

        {/* Right: match analysis */}
        <Grid size={{ xs: 12, lg: 7 }}>
          <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
            <Box sx={{ mb: 2, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {t("candidateDetail.matchAnalysis")}
              </Typography>
              {jobMatches.length > 1 && (
                <TextField
                  select
                  size="small"
                  value={selectedJobId || activeMatch?.job_id || ""}
                  onChange={(e) => setSelectedJobId(e.target.value)}
                  sx={{ minWidth: 150 }}
                >
                  {jobMatches.map((m) => (
                    <MenuItem key={m.job_id} value={m.job_id}>
                      {m.job_title || m.job_id}
                    </MenuItem>
                  ))}
                </TextField>
              )}
            </Box>

            {/* Score ring + reasoning */}
            {(hasAnalysis || analyzing || showTypewriter) ? (
              <>
                <Box sx={{ mb: 2, display: "flex", alignItems: "center", gap: 2 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      height: 64,
                      width: 64,
                      flexShrink: 0,
                      borderRadius: "50%",
                      border: 4,
                      borderColor: scoreColor,
                      color: scoreTextColor,
                      fontSize: 18,
                      fontWeight: 700,
                    }}
                  >
                    {scorePct}%
                  </Box>
                  <Typography variant="body2" sx={{ color: "grey.600" }}>
                    {showTypewriter ? (
                      <TypewriterText
                        text={typewriterText}
                        speed={18}
                        onComplete={() => setTypewriterDone(true)}
                      />
                    ) : (
                      reasoningText || t("candidateDetail.noMatchAnalysis")
                    )}
                  </Typography>
                </Box>

                {/* Strengths */}
                {(activeMatch?.strengths ?? []).length > 0 && (
                  <Box sx={{ mb: 1.5 }}>
                    <Typography
                      variant="caption"
                      sx={{ mb: 0.5, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                    >
                      {t("candidateDetail.strengths")}
                    </Typography>
                    <Box component="ul" sx={{ listStyle: "disc inside", pl: 0, m: 0 }}>
                      {activeMatch!.strengths.map((s, i) => (
                        <Typography
                          component="li"
                          key={i}
                          variant="body2"
                          sx={{ color: "#047857", mb: 0.5 }}
                        >
                          {s}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}

                {/* Gaps */}
                {(activeMatch?.gaps ?? []).length > 0 && (
                  <Box sx={{ mb: 2 }}>
                    <Typography
                      variant="caption"
                      sx={{ mb: 0.5, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                    >
                      {t("candidateDetail.gapsLabel")}
                    </Typography>
                    <Box component="ul" sx={{ listStyle: "disc inside", pl: 0, m: 0 }}>
                      {activeMatch!.gaps.map((g, i) => (
                        <Typography
                          component="li"
                          key={i}
                          variant="body2"
                          sx={{ color: "#dc2626", mb: 0.5 }}
                        >
                          {g}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </>
            ) : (
              <Typography variant="body2" sx={{ mb: 2, color: "grey.500" }}>
                {jobMatches.length === 0
                  ? t("candidateDetail.linkJobFirst")
                  : t("candidateDetail.clickToGenerate")}
              </Typography>
            )}

            {/* Candidate Summary */}
            {candidate.resume_summary && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="caption"
                  sx={{ mb: 0.5, display: "block", fontWeight: 500, textTransform: "uppercase", color: "grey.600" }}
                >
                  {t("candidateDetail.candidateSummary")}
                </Typography>
                <Typography variant="body2" sx={{ lineHeight: 1.6, color: "grey.700" }}>
                  {candidate.resume_summary}
                </Typography>
              </Box>
            )}

            {/* Generate button */}
            <Button
              onClick={handleAnalyze}
              disabled={analyzing || jobMatches.length === 0}
              fullWidth
              variant="contained"
              sx={{
                background: "linear-gradient(to right, #7c3aed, #2563eb)",
                "&:hover": {
                  background: "linear-gradient(to right, #6d28d9, #1d4ed8)",
                },
                textTransform: "none",
                fontSize: 14,
                fontWeight: 500,
                py: 1,
                "&.Mui-disabled": {
                  opacity: 0.5,
                  color: "white",
                  background: "linear-gradient(to right, #7c3aed, #2563eb)",
                },
              }}
              startIcon={
                analyzing ? (
                  <CircularProgress size={16} sx={{ color: "white" }} />
                ) : (
                  <AutoAwesomeOutlined sx={{ fontSize: 16 }} />
                )
              }
            >
              {analyzing
                ? t("candidateDetail.analyzing")
                : hasAnalysis
                  ? t("candidateDetail.reGenerateAnalysis")
                  : t("candidateDetail.generateAnalysis")}
            </Button>
          </Paper>
        </Grid>

        {/* Communication history (below match analysis when there are emails) */}
        {emails && emails.length > 0 && (
          <Grid size={12}>
            <Paper variant="outlined" sx={{ p: 2.5, borderRadius: 3 }}>
              <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                {t("candidateDetail.communicationHistory")}
              </Typography>
              <Stack spacing={1.5}>
                {emails.map((e) => (
                  <Box
                    key={e.id}
                    sx={{
                      borderRadius: 2,
                      border: 1,
                      borderColor: "grey.100",
                      bgcolor: "grey.50",
                      p: 1.5,
                    }}
                  >
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {e.subject}
                    </Typography>
                    <Typography variant="caption" sx={{ mt: 0.5, display: "block", color: "grey.600" }}>
                      {e.email_type} &middot;{" "}
                      {e.sent ? t("candidateDetail.sent", { date: e.sent_at ?? "" }) : t("candidateDetail.draft")}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Paper>
          </Grid>
        )}
      </Grid>
    </Stack>
  );
}

/* -- Typewriter Effect --------------------------------------------------- */

function TypewriterText({
  text,
  speed = 18,
  onComplete,
}: {
  text: string;
  speed?: number;
  onComplete?: () => void;
}) {
  const [displayed, setDisplayed] = useState("");
  const indexRef = useRef(0);

  useEffect(() => {
    if (!text) return;
    setDisplayed("");
    indexRef.current = 0;

    const timer = setInterval(() => {
      indexRef.current += 1;
      setDisplayed(text.slice(0, indexRef.current));
      if (indexRef.current >= text.length) {
        clearInterval(timer);
        onComplete?.();
      }
    }, speed);

    return () => clearInterval(timer);
  }, [text, speed]);

  return (
    <Box component="span">
      {displayed}
      {displayed.length < text.length && (
        <Box
          component="span"
          sx={{
            ml: 0.5,
            display: "inline-block",
            height: 16,
            width: 2,
            bgcolor: "grey.400",
            "@keyframes pulse": {
              "0%, 100%": { opacity: 1 },
              "50%": { opacity: 0 },
            },
            animation: "pulse 1.5s infinite",
          }}
        />
      )}
    </Box>
  );
}
