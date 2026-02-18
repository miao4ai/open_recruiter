import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogContent,
  LinearProgress,
  MenuItem,
  Paper,
  Popover,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import ErrorOutline from "@mui/icons-material/ErrorOutline";
import { DataGrid, type GridColDef } from "@mui/x-data-grid";
import UploadOutlined from "@mui/icons-material/UploadOutlined";
import PeopleOutline from "@mui/icons-material/PeopleOutline";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { useApi } from "../hooks/useApi";
import { listCandidates, listJobs, uploadResume, deleteCandidate } from "../lib/api";
import type { Candidate, CandidateStatus } from "../types";
import SemanticSearchBar, { type SearchResult } from "../components/SemanticSearchBar";

const UPLOAD_STEPS = [
  "Uploading file",
  "Extracting text",
  "AI parsing resume",
  "Saving candidate",
];

function UploadProgressDialog({
  open,
  done,
  error,
  onClose,
}: {
  open: boolean;
  done: boolean;
  error: string;
  onClose: () => void;
}) {
  const [activeStep, setActiveStep] = useState(0);

  // Auto-advance steps while waiting for API response
  useEffect(() => {
    if (!open) {
      setActiveStep(0);
      return;
    }
    if (done || error) return;

    const timer = setInterval(() => {
      setActiveStep((prev) => {
        // Stay on the last step until API returns
        if (prev >= UPLOAD_STEPS.length - 1) return prev;
        return prev + 1;
      });
    }, 2500);

    return () => clearInterval(timer);
  }, [open, done, error]);

  // When done, jump to completed
  useEffect(() => {
    if (done) setActiveStep(UPLOAD_STEPS.length);
  }, [done]);

  // Auto-close after success
  useEffect(() => {
    if (done && !error) {
      const t = setTimeout(onClose, 1200);
      return () => clearTimeout(t);
    }
  }, [done, error, onClose]);

  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogContent sx={{ py: 4, px: 3 }}>
        <Stepper activeStep={error ? activeStep : activeStep} orientation="vertical">
          {UPLOAD_STEPS.map((label, i) => (
            <Step key={label} completed={error ? i < activeStep : i < activeStep}>
              <StepLabel
                error={!!error && i === activeStep}
              >
                {label}
              </StepLabel>
            </Step>
          ))}
        </Stepper>

        {!done && !error && (
          <LinearProgress sx={{ mt: 3, borderRadius: 2 }} />
        )}

        {done && !error && (
          <Box sx={{ mt: 3, textAlign: "center" }}>
            <CheckCircleOutline sx={{ fontSize: 36, color: "success.main" }} />
            <Typography variant="body2" sx={{ mt: 1, fontWeight: 500, color: "success.main" }}>
              Resume imported successfully!
            </Typography>
          </Box>
        )}

        {error && (
          <Box sx={{ mt: 3, textAlign: "center" }}>
            <ErrorOutline sx={{ fontSize: 36, color: "error.main" }} />
            <Typography variant="body2" sx={{ mt: 1, color: "error.main" }}>
              {error}
            </Typography>
            <Button onClick={onClose} size="small" sx={{ mt: 1.5 }}>
              Close
            </Button>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}

const STATUS_CHIP_COLOR: Record<
  CandidateStatus,
  "default" | "primary" | "secondary" | "success" | "warning" | "info" | "error"
> = {
  new: "default",
  contacted: "primary",
  replied: "success",
  screening: "warning",
  interview_scheduled: "secondary",
  interviewed: "info",
  offer_sent: "info",
  hired: "success",
  rejected: "error",
  withdrawn: "default",
};

function ScoreCell({
  jobMatches,
}: {
  jobMatches: { job_id: string; job_title: string; job_company: string; match_score: number; match_reasoning: string; strengths: string[]; gaps: string[] }[];
}) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const scored = (jobMatches ?? []).filter((m) => m.match_score > 0);
  if (scored.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        —
      </Typography>
    );
  }

  // Show best score in the bar
  const best = scored.reduce((a, b) => (a.match_score > b.match_score ? a : b), scored[0]);
  const pct = Math.round(best.match_score * 100);
  const color: "success" | "warning" | "error" =
    pct >= 70 ? "success" : pct >= 40 ? "warning" : "error";

  return (
    <>
      <Box
        onClick={(e) => setAnchorEl(e.currentTarget)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          width: "100%",
          cursor: "pointer",
          "&:hover": { opacity: 0.8 },
        }}
      >
        <LinearProgress
          variant="determinate"
          value={pct}
          color={color}
          sx={{ flexGrow: 1, height: 8, borderRadius: 4 }}
        />
        <Typography variant="caption" color="text.secondary">
          {pct}%
        </Typography>
      </Box>
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
      >
        <Box sx={{ p: 2, maxWidth: 400 }}>
          {scored.map((m, idx) => {
            const mPct = Math.round(m.match_score * 100);
            const mColor: "success" | "warning" | "error" =
              mPct >= 70 ? "success" : mPct >= 40 ? "warning" : "error";
            const hasAnalysis = !!(m.match_reasoning || m.strengths?.length > 0 || m.gaps?.length > 0);
            return (
              <Box key={m.job_id} sx={{ mb: idx < scored.length - 1 ? 2 : 0 }}>
                {/* Job header with score */}
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, fontSize: 13 }}>
                    {m.job_title || m.job_id}
                  </Typography>
                  <Chip
                    label={`${mPct}%`}
                    size="small"
                    color={mColor}
                    sx={{ fontSize: 11, height: 20 }}
                  />
                </Box>
                {m.job_company && (
                  <Typography variant="caption" sx={{ color: "grey.500", display: "block", mb: 0.5 }}>
                    {m.job_company}
                  </Typography>
                )}
                {hasAnalysis ? (
                  <>
                    {m.match_reasoning && (
                      <Typography variant="body2" sx={{ mb: 1, color: "text.secondary", lineHeight: 1.5, fontSize: 13 }}>
                        {m.match_reasoning}
                      </Typography>
                    )}
                    {m.strengths?.length > 0 && (
                      <Box sx={{ mb: 0.5 }}>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "success.main", textTransform: "uppercase" }}>
                          Strengths
                        </Typography>
                        {m.strengths.map((s, i) => (
                          <Typography key={i} variant="body2" sx={{ color: "success.dark", pl: 1, fontSize: 12 }}>
                            • {s}
                          </Typography>
                        ))}
                      </Box>
                    )}
                    {m.gaps?.length > 0 && (
                      <Box>
                        <Typography variant="caption" sx={{ fontWeight: 600, color: "error.main", textTransform: "uppercase" }}>
                          Gaps
                        </Typography>
                        {m.gaps.map((g, i) => (
                          <Typography key={i} variant="body2" sx={{ color: "error.dark", pl: 1, fontSize: 12 }}>
                            • {g}
                          </Typography>
                        ))}
                      </Box>
                    )}
                  </>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    Vector similarity only. Generate Analysis for details.
                  </Typography>
                )}
                {idx < scored.length - 1 && (
                  <Box sx={{ borderBottom: "1px solid", borderColor: "grey.200", mt: 1.5 }} />
                )}
              </Box>
            );
          })}
        </Box>
      </Popover>
    </>
  );
}

function SkillsCell({ skills }: { skills: string[] }) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  if (skills.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        —
      </Typography>
    );
  }

  return (
    <>
      <Box
        onClick={(e) => { if (skills.length > 3) setAnchorEl(e.currentTarget); }}
        sx={{
          display: "flex",
          flexWrap: "wrap",
          gap: 0.5,
          cursor: skills.length > 3 ? "pointer" : "default",
        }}
      >
        {skills.slice(0, 3).map((s) => (
          <Chip key={s} label={s} size="small" variant="outlined" />
        ))}
        {skills.length > 3 && (
          <Chip
            label={`+${skills.length - 3}`}
            size="small"
            variant="outlined"
            sx={{ color: "text.secondary", borderStyle: "dashed" }}
          />
        )}
      </Box>
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
      >
        <Box sx={{ p: 1.5, display: "flex", flexWrap: "wrap", gap: 0.5, maxWidth: 360 }}>
          {skills.map((s) => (
            <Chip key={s} label={s} size="small" variant="outlined" />
          ))}
        </Box>
      </Popover>
    </>
  );
}

function JobsCell({ matches }: { matches: { job_id: string; job_title: string; job_company: string; match_score: number }[] }) {
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  if (matches.length === 0) {
    return (
      <Typography variant="caption" color="text.secondary">
        —
      </Typography>
    );
  }

  return (
    <>
      <Box
        onClick={(e) => { if (matches.length > 1) setAnchorEl(e.currentTarget); }}
        sx={{
          display: "flex",
          flexWrap: "wrap",
          gap: 0.5,
          cursor: matches.length > 1 ? "pointer" : "default",
        }}
      >
        <Chip
          label={matches[0].job_title || matches[0].job_id}
          size="small"
          variant="outlined"
        />
        {matches.length > 1 && (
          <Chip
            label={`+${matches.length - 1}`}
            size="small"
            variant="outlined"
            sx={{ color: "text.secondary", borderStyle: "dashed" }}
          />
        )}
      </Box>
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
      >
        <Box sx={{ p: 1.5, display: "flex", flexDirection: "column", gap: 0.75, maxWidth: 360 }}>
          {matches.map((m) => (
            <Box key={m.job_id} sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1 }}>
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
              {m.match_score > 0 && (
                <Chip
                  label={`${Math.round(m.match_score * 100)}%`}
                  size="small"
                  sx={{
                    fontSize: 11,
                    height: 20,
                    flexShrink: 0,
                    bgcolor: m.match_score >= 0.7 ? "#d1fae5" : m.match_score >= 0.4 ? "#fef3c7" : "#fee2e2",
                    color: m.match_score >= 0.7 ? "#047857" : m.match_score >= 0.4 ? "#b45309" : "#dc2626",
                  }}
                />
              )}
            </Box>
          ))}
        </Box>
      </Popover>
    </>
  );
}

export default function Candidates() {
  const { data: candidates, refresh } = useApi(
    useCallback(() => listCandidates(), [])
  );
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadDone, setUploadDone] = useState(false);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult<Candidate>[] | null>(null);

  const handleSearchResults = useCallback((results: SearchResult<Candidate>[] | null) => {
    setSearchResults(results);
  }, []);

  const displayCandidates = searchResults
    ? searchResults.map((r) => r.record)
    : candidates;

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadDone(false);
    setUploadError("");
    try {
      await uploadResume(file, selectedJobId);
      setUploadDone(true);
      refresh();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (err?.response?.status === 409 && detail) {
        setUploadError(detail);
      } else {
        setUploadError("Upload failed. Please try again.");
      }
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const closeUploadDialog = () => {
    setUploading(false);
    setUploadDone(false);
    setUploadError("");
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this candidate?")) return;
    await deleteCandidate(id);
    refresh();
  };

  const columns: GridColDef[] = [
    {
      field: "name",
      headerName: "Name",
      flex: 1,
      minWidth: 150,
      renderCell: (params) => (
        <Link
          to={`/candidates/${params.row.id}`}
          style={{ color: "#1976d2", textDecoration: "none", fontWeight: 500 }}
        >
          {params.value || "Unnamed"}
        </Link>
      ),
    },
    {
      field: "email",
      headerName: "Email",
      flex: 1,
      minWidth: 180,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {params.value || "\u2014"}
        </Typography>
      ),
    },
    {
      field: "current_title",
      headerName: "Title",
      flex: 1,
      minWidth: 150,
      renderCell: (params) => (
        <Typography variant="body2" color="text.secondary">
          {params.value || "\u2014"}
        </Typography>
      ),
    },
    {
      field: "job_matches",
      headerName: "Jobs",
      flex: 1,
      minWidth: 160,
      sortable: false,
      renderCell: (params) => <JobsCell matches={params.value ?? []} />,
    },
    {
      field: "match_score",
      headerName: "Score",
      width: 160,
      renderCell: (params) => (
        <ScoreCell jobMatches={params.row.job_matches ?? []} />
      ),
    },
    {
      field: "status",
      headerName: "Status",
      width: 150,
      renderCell: (params) => (
        <Chip
          label={params.value.replace(/_/g, " ")}
          size="small"
          color={STATUS_CHIP_COLOR[params.value as CandidateStatus] ?? "default"}
        />
      ),
    },
    {
      field: "skills",
      headerName: "Skills",
      flex: 1,
      minWidth: 200,
      sortable: false,
      renderCell: (params) => <SkillsCell skills={params.value ?? []} />,
    },
    {
      field: "actions",
      headerName: "",
      width: 50,
      sortable: false,
      filterable: false,
      disableColumnMenu: true,
      renderCell: (params) => (
        <Tooltip title="Delete">
          <IconButton
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(params.row.id);
            }}
            sx={{ color: "grey.400", "&:hover": { color: "error.main" } }}
          >
            <DeleteOutline sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      ),
    },
  ];

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Upload progress dialog */}
      <UploadProgressDialog
        open={uploading}
        done={uploadDone}
        error={uploadError}
        onClose={closeUploadDialog}
      />

      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Typography variant="h6">
          All Candidates{" "}
          <Typography
            component="span"
            variant="body2"
            color="text.secondary"
          >
            ({candidates?.length ?? 0})
          </Typography>
        </Typography>

        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <TextField
            select
            size="small"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">Link to Job (optional)</MenuItem>
            {jobs?.map((j) => (
              <MenuItem key={j.id} value={j.id}>
                {j.title} — {j.company}
              </MenuItem>
            ))}
          </TextField>

          <Button
            variant="contained"
            component="label"
            startIcon={<UploadOutlined />}
            disabled={uploading}
          >
            Import Resume
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.doc,.txt"
              hidden
              onChange={handleUpload}
            />
          </Button>
        </Box>
      </Box>

      {/* Semantic search */}
      <SemanticSearchBar<Candidate>
        collection="candidates"
        placeholder="Search candidates — try 'Python backend with 5 years experience' or 'React developer'..."
        onResults={handleSearchResults}
      />

      {/* Data grid or empty state */}
      {displayCandidates && displayCandidates.length > 0 ? (
        <Paper sx={{ width: "100%" }}>
          <DataGrid
            rows={displayCandidates ?? []}
            columns={columns}
            getRowId={(row) => row.id}
            autoHeight
            disableRowSelectionOnClick
            pageSizeOptions={[10, 25, 50]}
            initialState={{
              pagination: { paginationModel: { pageSize: 10 } },
            }}
          />
        </Paper>
      ) : (
        <Paper
          sx={{
            border: "2px dashed",
            borderColor: "grey.300",
            p: 6,
            textAlign: "center",
          }}
          elevation={0}
        >
          <PeopleOutline
            sx={{ fontSize: 40, color: "grey.400", mx: "auto" }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            {searchResults
              ? "No candidates match your search."
              : <>No candidates yet. Click <strong>Import Resume</strong> to add one.</>}
          </Typography>
        </Paper>
      )}
    </Box>
  );
}
