import { useCallback, useMemo } from "react";
import {
  WorkOutline,
  PeopleOutline,
  MailOutline,
  CalendarTodayOutlined,
  AddOutlined,
  UploadOutlined,
  SendOutlined,
} from "@mui/icons-material";
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Avatar,
  Grid2 as Grid,
} from "@mui/material";
import { useApi } from "../hooks/useApi";
import { listJobs, listCandidates, listEmails } from "../lib/api";
import type { Job, Candidate, Email, CandidateStatus } from "../types";
import { PIPELINE_COLUMNS } from "../types";

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <Card
      variant="outlined"
      sx={{
        borderRadius: 3,
        boxShadow: "0 1px 2px 0 rgba(0,0,0,0.05)",
      }}
    >
      <CardContent
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 2,
          p: 2.5,
          "&:last-child": { pb: 2.5 },
        }}
      >
        <Avatar
          sx={{
            bgcolor: color,
            width: 40,
            height: 40,
            borderRadius: 2,
          }}
          variant="rounded"
        >
          <Icon sx={{ fontSize: 20, color: "#fff" }} />
        </Avatar>
        <Box>
          <Typography variant="body2" sx={{ color: "grey.500" }}>
            {label}
          </Typography>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            {value}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
}

type ActivityItem = {
  type: "job" | "candidate" | "email";
  icon: React.ElementType;
  iconBg: string;
  iconFg: string;
  title: string;
  detail: string;
  time: string;
};

function RecentActivity({
  jobs,
  candidates,
  emails,
}: {
  jobs: Job[] | null;
  candidates: Candidate[] | null;
  emails: Email[] | null;
}) {
  const items = useMemo(() => {
    const all: ActivityItem[] = [];

    for (const j of jobs ?? []) {
      all.push({
        type: "job",
        icon: AddOutlined,
        iconBg: "#dbeafe",
        iconFg: "#2563eb",
        title: `Job created: ${j.title}`,
        detail: j.company || "",
        time: j.created_at,
      });
    }

    for (const c of candidates ?? []) {
      all.push({
        type: "candidate",
        icon: UploadOutlined,
        iconBg: "#d1fae5",
        iconFg: "#059669",
        title: `Candidate added: ${c.name || "Unnamed"}`,
        detail: c.current_title
          ? `${c.current_title}${c.current_company ? ` at ${c.current_company}` : ""}`
          : "",
        time: c.created_at,
      });
    }

    for (const e of emails ?? []) {
      const status = e.sent ? "sent" : e.approved ? "approved" : "drafted";
      all.push({
        type: "email",
        icon: e.sent ? SendOutlined : MailOutline,
        iconBg: e.sent ? "#dcfce7" : "#fef3c7",
        iconFg: e.sent ? "#16a34a" : "#d97706",
        title: `Email ${status}: ${e.subject}`,
        detail: `To: ${e.to_email}${e.candidate_name ? ` (${e.candidate_name})` : ""}`,
        time: e.sent_at || e.created_at,
      });
    }

    // Sort by time descending, take latest 15
    all.sort((a, b) => (b.time ?? "").localeCompare(a.time ?? ""));
    return all.slice(0, 15);
  }, [jobs, candidates, emails]);

  if (items.length === 0) {
    return (
      <Paper
        variant="outlined"
        sx={{
          borderRadius: 3,
          p: 3,
          textAlign: "center",
        }}
      >
        <Typography variant="body2" sx={{ color: "grey.400" }}>
          No activity yet. Create a job and add candidates to get started.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 3,
        overflow: "hidden",
      }}
    >
      {items.map((item, i) => (
        <Box
          key={i}
          sx={{
            display: "flex",
            alignItems: "flex-start",
            gap: 1.5,
            px: 2,
            py: 1.5,
            borderBottom: i < items.length - 1 ? "1px solid" : "none",
            borderColor: "grey.100",
          }}
        >
          <Avatar
            variant="rounded"
            sx={{
              mt: 0.25,
              width: 28,
              height: 28,
              borderRadius: 2,
              bgcolor: item.iconBg,
            }}
          >
            <item.icon sx={{ fontSize: 16, color: item.iconFg }} />
          </Avatar>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                color: "grey.800",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {item.title}
            </Typography>
            {item.detail && (
              <Typography
                variant="caption"
                sx={{
                  color: "grey.500",
                  display: "block",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.detail}
              </Typography>
            )}
          </Box>
          <Typography
            component="time"
            variant="caption"
            sx={{ flexShrink: 0, color: "grey.400" }}
          >
            {formatRelativeTime(item.time)}
          </Typography>
        </Box>
      ))}
    </Paper>
  );
}

function formatRelativeTime(isoStr: string): string {
  if (!isoStr) return "";
  const date = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

export default function Dashboard() {
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const { data: candidates } = useApi(
    useCallback(() => listCandidates(), [])
  );
  const { data: emails } = useApi(useCallback(() => listEmails(), []));

  const totalJobs = jobs?.length ?? 0;
  const totalCandidates = candidates?.length ?? 0;
  const pendingEmails =
    emails?.filter((e) => !e.sent && !e.approved).length ?? 0;
  const interviews =
    candidates?.filter((c) => c.status === "interview_scheduled").length ?? 0;

  // Group candidates by status for pipeline
  const grouped: Record<string, typeof candidates> = {};
  for (const col of PIPELINE_COLUMNS) {
    grouped[col.key] = candidates?.filter((c) => c.status === col.key) ?? [];
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Stat cards */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={WorkOutline}
            label="Active Jobs"
            value={totalJobs}
            color="#3b82f6"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={PeopleOutline}
            label="Candidates"
            value={totalCandidates}
            color="#10b981"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={MailOutline}
            label="Pending Emails"
            value={pendingEmails}
            color="#f59e0b"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={CalendarTodayOutlined}
            label="Interviews"
            value={interviews}
            color="#8b5cf6"
          />
        </Grid>
      </Grid>

      {/* Pipeline Kanban */}
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
          Pipeline
        </Typography>
        <Box
          sx={{
            display: "flex",
            gap: 1.5,
            overflowX: "auto",
            pb: 2,
          }}
        >
          {PIPELINE_COLUMNS.map((col) => (
            <Paper
              key={col.key}
              variant="outlined"
              sx={{
                width: 208,
                flexShrink: 0,
                borderRadius: 2,
              }}
            >
              <Box
                sx={{
                  borderBottom: "1px solid",
                  borderColor: "grey.100",
                  px: 1.5,
                  py: 1,
                }}
              >
                <Typography
                  variant="body2"
                  sx={{ fontWeight: 500, color: "grey.700" }}
                >
                  {col.label}
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ ml: 0.75, color: "grey.400" }}
                  >
                    {grouped[col.key]?.length ?? 0}
                  </Typography>
                </Typography>
              </Box>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 1,
                  p: 1,
                }}
              >
                {grouped[col.key]?.length ? (
                  grouped[col.key]?.map((c) => (
                    <Paper
                      key={c.id}
                      variant="outlined"
                      sx={{
                        borderColor: "grey.100",
                        bgcolor: "grey.50",
                        p: 1,
                        borderRadius: 1.5,
                      }}
                    >
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {c.name || "Unnamed"}
                      </Typography>
                      <Typography variant="caption" sx={{ color: "grey.500" }}>
                        Score: {c.match_score ? `${Math.round(c.match_score * 100)}%` : "\u2014"}
                      </Typography>
                    </Paper>
                  ))
                ) : (
                  <Typography
                    variant="caption"
                    sx={{
                      px: 1,
                      py: 2,
                      textAlign: "center",
                      color: "grey.400",
                    }}
                  >
                    No candidates
                  </Typography>
                )}
              </Box>
            </Paper>
          ))}
        </Box>
      </Box>

      {/* Recent Activity */}
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1.5 }}>
          Recent Activity
        </Typography>
        <RecentActivity jobs={jobs} candidates={candidates} emails={emails} />
      </Box>
    </Box>
  );
}
