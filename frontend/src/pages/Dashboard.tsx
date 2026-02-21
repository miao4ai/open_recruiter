import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  WorkOutline,
  PeopleOutline,
  MailOutline,
  CalendarTodayOutlined,
  AddOutlined,
  UploadOutlined,
  SendOutlined,
  ChevronLeftOutlined,
  ChevronRightOutlined,
  AccessTimeOutlined,
  PersonOutline,
} from "@mui/icons-material";
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Avatar,
  Grid2 as Grid,
  IconButton,
  Button,
} from "@mui/material";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { listJobs, listCandidates, listEmails, listEvents, listPipelineEntries } from "../lib/api";
import type { Job, Candidate, Email, CalendarEvent, EventType, PipelineEntry, PipelineViewMode } from "../types";
import { PIPELINE_COLUMNS } from "../types";
import type { TFunction } from "i18next";

/* ── StatCard ──────────────────────────────────────────────────────────── */

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

/* ── RecentActivity ────────────────────────────────────────────────────── */

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
  t,
}: {
  jobs: Job[] | null;
  candidates: Candidate[] | null;
  emails: Email[] | null;
  t: TFunction;
}) {
  const items = useMemo(() => {
    const all: ActivityItem[] = [];

    for (const j of jobs ?? []) {
      all.push({
        type: "job",
        icon: AddOutlined,
        iconBg: "#dbeafe",
        iconFg: "#2563eb",
        title: t("dashboard.jobCreated", { title: j.title }),
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
        title: t("dashboard.candidateAdded", { name: c.name || t("common.unnamed") }),
        detail: c.current_title
          ? `${c.current_title}${c.current_company ? ` ${t("dashboard.at", { company: c.current_company })}` : ""}`
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
        title: t("dashboard.emailStatus", { status, subject: e.subject }),
        detail: `${t("dashboard.to", { email: e.to_email })}${e.candidate_name ? ` (${e.candidate_name})` : ""}`,
        time: e.sent_at || e.created_at,
      });
    }

    // Sort by time descending, take latest 15
    all.sort((a, b) => (b.time ?? "").localeCompare(a.time ?? ""));
    return all.slice(0, 15);
  }, [jobs, candidates, emails, t]);

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
          {t("dashboard.noActivity")}
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
            {formatRelativeTime(item.time, t)}
          </Typography>
        </Box>
      ))}
    </Paper>
  );
}

/* ── Helper functions ──────────────────────────────────────────────────── */

function formatRelativeTime(isoStr: string, t: TFunction): string {
  if (!isoStr) return "";
  const date = new Date(isoStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return t("common.justNow");
  if (diffMin < 60) return t("common.minutesAgo", { count: diffMin });
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return t("common.hoursAgo", { count: diffHr });
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return t("common.daysAgo", { count: diffDay });
  return date.toLocaleDateString();
}

function pad2(n: number) {
  return n.toString().padStart(2, "0");
}

function toDateKey(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function getMonday(d: Date) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

function formatTimeShort(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ── Weekly Calendar Strip ─────────────────────────────────────────────── */

const EVENT_DOT_COLORS: Record<EventType, string> = {
  interview: "#a855f7",
  follow_up: "#3b82f6",
  offer: "#22c55e",
  screening: "#f59e0b",
  other: "#9ca3af",
};

const EVENT_PILL_COLORS: Record<
  EventType,
  { bg: string; border: string; text: string }
> = {
  interview: { bg: "#faf5ff", border: "#e9d5ff", text: "#7c3aed" },
  follow_up: { bg: "#eff6ff", border: "#bfdbfe", text: "#2563eb" },
  offer: { bg: "#f0fdf4", border: "#bbf7d0", text: "#16a34a" },
  screening: { bg: "#fffbeb", border: "#fde68a", text: "#d97706" },
  other: { bg: "#f9fafb", border: "#e5e7eb", text: "#4b5563" },
};

function WeeklyCalendar({ events }: { events: CalendarEvent[] | null }) {
  const { t } = useTranslation();
  const DAY_NAMES_SHORT = t("calendar.days", { returnObjects: true }) as string[];

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = toDateKey(today);

  const [weekOffset, setWeekOffset] = useState(0);

  const weekDays = useMemo(() => {
    const ref = new Date(today);
    ref.setDate(ref.getDate() + weekOffset * 7);
    const monday = getMonday(ref);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
  }, [weekOffset]);

  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const e of events ?? []) {
      const key = e.start_time.slice(0, 10);
      if (!map[key]) map[key] = [];
      map[key].push(e);
    }
    return map;
  }, [events]);

  const [selectedDate, setSelectedDate] = useState(todayStr);

  const selectedEvents = eventsByDate[selectedDate] ?? [];

  const weekLabel = useMemo(() => {
    const first = weekDays[0];
    const last = weekDays[6];
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
    return `${first.toLocaleDateString(undefined, opts)} \u2014 ${last.toLocaleDateString(undefined, opts)}`;
  }, [weekDays]);

  return (
    <Paper variant="outlined" sx={{ borderRadius: 3, overflow: "hidden" }}>
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "grey.200",
          px: 2,
          py: 1.5,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, color: "grey.900" }}>
            {t("dashboard.thisWeek")}
          </Typography>
          <Typography variant="caption" sx={{ color: "grey.400" }}>
            {weekLabel}
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <IconButton
            size="small"
            onClick={() => setWeekOffset((o) => o - 1)}
            sx={{ color: "grey.400" }}
          >
            <ChevronLeftOutlined fontSize="small" />
          </IconButton>
          <Button
            variant="outlined"
            size="small"
            onClick={() => {
              setWeekOffset(0);
              setSelectedDate(todayStr);
            }}
            sx={{
              minWidth: "auto",
              px: 1,
              py: 0.25,
              fontSize: "0.75rem",
              fontWeight: 500,
              color: "grey.500",
              borderColor: "grey.300",
              "&:hover": { bgcolor: "grey.50" },
            }}
          >
            {t("common.today")}
          </Button>
          <IconButton
            size="small"
            onClick={() => setWeekOffset((o) => o + 1)}
            sx={{ color: "grey.400" }}
          >
            <ChevronRightOutlined fontSize="small" />
          </IconButton>
          <Typography
            component={Link}
            to="/calendar"
            variant="caption"
            sx={{
              ml: 1,
              color: "primary.main",
              textDecoration: "none",
              "&:hover": { color: "primary.dark" },
            }}
          >
            {t("dashboard.fullCalendar")}
          </Typography>
        </Box>
      </Box>

      {/* Day strip */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(7, 1fr)",
          borderBottom: "1px solid",
          borderColor: "grey.200",
        }}
      >
        {weekDays.map((d) => {
          const key = toDateKey(d);
          const isToday = key === todayStr;
          const isSelected = key === selectedDate;
          const dayEvents = eventsByDate[key] ?? [];
          return (
            <Box
              key={key}
              component="button"
              onClick={() => setSelectedDate(key)}
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 0.5,
                py: 1.5,
                border: "none",
                cursor: "pointer",
                bgcolor: isSelected ? "#eff6ff" : "transparent",
                transition: "background-color 0.15s",
                "&:hover": {
                  bgcolor: isSelected ? "#eff6ff" : "grey.50",
                },
              }}
            >
              <Typography variant="caption" sx={{ color: "grey.400" }}>
                {DAY_NAMES_SHORT[d.getDay()]}
              </Typography>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  ...(isToday
                    ? { bgcolor: "#2563eb", color: "#fff" }
                    : isSelected
                      ? { bgcolor: "#dbeafe", color: "#1d4ed8" }
                      : { color: "grey.700" }),
                }}
              >
                {d.getDate()}
              </Box>
              {/* Event dots */}
              <Box sx={{ display: "flex", gap: "2px" }}>
                {dayEvents.slice(0, 3).map((evt) => (
                  <Box
                    key={evt.id}
                    sx={{
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      bgcolor:
                        EVENT_DOT_COLORS[evt.event_type] ||
                        EVENT_DOT_COLORS.other,
                    }}
                  />
                ))}
              </Box>
            </Box>
          );
        })}
      </Box>

      {/* Selected day's events */}
      <Box sx={{ px: 2, py: 1.5 }}>
        {selectedEvents.length === 0 ? (
          <Typography
            variant="caption"
            sx={{
              display: "block",
              py: 1,
              textAlign: "center",
              color: "grey.400",
            }}
          >
            {t("dashboard.noEventsOnDay")}
          </Typography>
        ) : (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            {selectedEvents.map((evt) => {
              const c =
                EVENT_PILL_COLORS[evt.event_type] || EVENT_PILL_COLORS.other;
              return (
                <Box
                  key={evt.id}
                  sx={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 1.5,
                    borderRadius: 2,
                    border: "1px solid",
                    borderColor: c.border,
                    bgcolor: c.bg,
                    p: 1.25,
                  }}
                >
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 500, color: c.text }}
                    >
                      {evt.title}
                    </Typography>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 1.5,
                        mt: 0.25,
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          gap: 0.5,
                          color: "grey.500",
                        }}
                      >
                        <AccessTimeOutlined sx={{ fontSize: 12 }} />
                        {formatTimeShort(evt.start_time)}
                        {evt.end_time
                          ? ` \u2014 ${formatTimeShort(evt.end_time)}`
                          : ""}
                      </Typography>
                      {evt.candidate_name && (
                        <Typography
                          variant="caption"
                          sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 0.5,
                            color: "grey.500",
                          }}
                        >
                          <PersonOutline sx={{ fontSize: 12 }} />
                          {evt.candidate_name}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                </Box>
              );
            })}
          </Box>
        )}
      </Box>
    </Paper>
  );
}

/* ── Dashboard ─────────────────────────────────────────────────────────── */

export default function Dashboard() {
  const { t } = useTranslation();
  const { data: jobs } = useApi(useCallback(() => listJobs(), []));
  const { data: candidates } = useApi(
    useCallback(() => listCandidates(), []),
  );
  const { data: emails } = useApi(useCallback(() => listEmails(), []));
  const { data: events } = useApi(useCallback(() => listEvents(), []));
  const { data: pipelineEntries } = useApi(useCallback(() => listPipelineEntries(), []));
  const [kanbanView, setKanbanView] = useState<PipelineViewMode>("candidate");

  const totalJobs = jobs?.length ?? 0;
  const totalCandidates = candidates?.length ?? 0;
  const pendingEmails =
    emails?.filter((e) => !e.sent && !e.approved).length ?? 0;
  const interviews =
    candidates?.filter((c) => c.status === "interview_scheduled").length ?? 0;

  // Group pipeline entries by status (per candidate-job pair)
  const hasPipelineEntries = pipelineEntries && pipelineEntries.length > 0;

  // Candidate view: group by status, each card = candidate-job pair
  const candidateGrouped: Record<string, PipelineEntry[] | typeof candidates> = {};
  for (const col of PIPELINE_COLUMNS) {
    if (hasPipelineEntries) {
      candidateGrouped[col.key] = pipelineEntries.filter((e: PipelineEntry) => e.pipeline_status === col.key);
    } else {
      candidateGrouped[col.key] = candidates?.filter((c) => c.status === col.key) ?? [];
    }
  }

  // Jobs view: group by status → then by job, each card = job with candidate count
  type JobGroup = { job_id: string; job_title: string; job_company: string; candidates: PipelineEntry[] };
  const jobsGrouped: Record<string, JobGroup[]> = {};
  for (const col of PIPELINE_COLUMNS) {
    if (hasPipelineEntries) {
      const entries = pipelineEntries.filter((e: PipelineEntry) => e.pipeline_status === col.key);
      const map = new Map<string, JobGroup>();
      for (const e of entries) {
        if (!map.has(e.job_id)) {
          map.set(e.job_id, { job_id: e.job_id, job_title: e.job_title, job_company: e.job_company, candidates: [] });
        }
        map.get(e.job_id)!.candidates.push(e);
      }
      jobsGrouped[col.key] = Array.from(map.values());
    } else {
      jobsGrouped[col.key] = [];
    }
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Stat cards */}
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={WorkOutline}
            label={t("dashboard.activeJobs")}
            value={totalJobs}
            color="#3b82f6"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={PeopleOutline}
            label={t("dashboard.candidates")}
            value={totalCandidates}
            color="#10b981"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={MailOutline}
            label={t("dashboard.pendingEmails")}
            value={pendingEmails}
            color="#f59e0b"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard
            icon={CalendarTodayOutlined}
            label={t("dashboard.interviews")}
            value={interviews}
            color="#8b5cf6"
          />
        </Grid>
      </Grid>

      {/* Weekly Calendar */}
      <WeeklyCalendar events={events} />

      {/* Pipeline Kanban */}
      <Box>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {t("dashboard.pipeline")}
          </Typography>
          {/* Candidate / Jobs toggle */}
          <Box sx={{ display: "flex", border: "1px solid", borderColor: "grey.200", borderRadius: 2, bgcolor: "grey.50", overflow: "hidden" }}>
            <Button
              size="small"
              onClick={() => setKanbanView("candidate")}
              startIcon={<PersonOutline sx={{ fontSize: 14 }} />}
              sx={{
                px: 1.5, py: 0.25, fontSize: "0.7rem", fontWeight: 500, textTransform: "none", borderRadius: 0,
                ...(kanbanView === "candidate"
                  ? { bgcolor: "white", color: "primary.main", boxShadow: "0 1px 2px rgba(0,0,0,0.1)" }
                  : { color: "grey.500" }),
              }}
            >
              {t("pipeline.viewCandidate")}
            </Button>
            <Button
              size="small"
              onClick={() => setKanbanView("jobs")}
              startIcon={<WorkOutline sx={{ fontSize: 14 }} />}
              sx={{
                px: 1.5, py: 0.25, fontSize: "0.7rem", fontWeight: 500, textTransform: "none", borderRadius: 0,
                ...(kanbanView === "jobs"
                  ? { bgcolor: "white", color: "primary.main", boxShadow: "0 1px 2px rgba(0,0,0,0.1)" }
                  : { color: "grey.500" }),
              }}
            >
              {t("pipeline.viewJobs")}
            </Button>
          </Box>
        </Box>
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
                  {t(col.labelKey)}
                  <Typography
                    component="span"
                    variant="caption"
                    sx={{ ml: 0.75, color: "grey.400" }}
                  >
                    {kanbanView === "jobs"
                      ? (jobsGrouped[col.key]?.length ?? 0)
                      : (candidateGrouped[col.key]?.length ?? 0)}
                  </Typography>
                </Typography>
              </Box>
              <Box
                sx={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 1,
                  p: 1,
                  maxHeight: 320,
                  overflowY: "auto",
                }}
              >
                {kanbanView === "jobs" ? (
                  /* ── Jobs view: each card = a job ─────────────────────── */
                  jobsGrouped[col.key]?.length ? (
                    jobsGrouped[col.key].map((group) => (
                      <Paper
                        key={group.job_id}
                        variant="outlined"
                        sx={{
                          borderColor: "grey.100",
                          bgcolor: "grey.50",
                          p: 1,
                          borderRadius: 1.5,
                        }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: 500, color: "primary.dark" }}>
                          {group.job_title || t("common.unnamed")}
                        </Typography>
                        {group.job_company && (
                          <Typography variant="caption" sx={{ color: "grey.500", display: "block" }}>
                            {group.job_company}
                          </Typography>
                        )}
                        <Typography variant="caption" sx={{ color: "grey.400", display: "block", mt: 0.5 }}>
                          {t("pipeline.candidateCount", { count: group.candidates.length })}
                        </Typography>
                        {/* Candidate names */}
                        <Box sx={{ mt: 0.5, display: "flex", flexDirection: "column", gap: 0.25 }}>
                          {group.candidates.slice(0, 3).map((c) => (
                            <Typography key={c.candidate_id} variant="caption" sx={{ color: "grey.600", fontSize: "0.65rem" }}>
                              • {c.candidate_name}
                              {c.match_score > 0 && ` (${Math.round(c.match_score * 100)}%)`}
                            </Typography>
                          ))}
                          {group.candidates.length > 3 && (
                            <Typography variant="caption" sx={{ color: "grey.400", fontSize: "0.6rem" }}>
                              +{group.candidates.length - 3} {t("common.more")}
                            </Typography>
                          )}
                        </Box>
                      </Paper>
                    ))
                  ) : (
                    <Typography
                      variant="caption"
                      sx={{ px: 1, py: 2, textAlign: "center", color: "grey.400" }}
                    >
                      {t("dashboard.noJobs")}
                    </Typography>
                  )
                ) : (
                  /* ── Candidate view: each card = candidate-job pair ──── */
                  candidateGrouped[col.key]?.length ? (
                    candidateGrouped[col.key]?.map((item: any) => {
                      const isPipelineEntry = "candidate_name" in item;
                      const name = isPipelineEntry ? item.candidate_name : item.name;
                      const score = item.match_score;
                      const key = isPipelineEntry ? `${item.candidate_id}:${item.job_id}` : item.id;
                      return (
                        <Paper
                          key={key}
                          variant="outlined"
                          sx={{
                            borderColor: "grey.100",
                            bgcolor: "grey.50",
                            p: 1,
                            borderRadius: 1.5,
                          }}
                        >
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {name || t("common.unnamed")}
                          </Typography>
                          {isPipelineEntry && item.job_title && (
                            <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 500 }}>
                              {item.job_title}{item.job_company ? ` · ${item.job_company}` : ""}
                            </Typography>
                          )}
                          <Typography variant="caption" sx={{ color: "grey.500", display: "block" }}>
                            {t("dashboard.score")}:{" "}
                            {score
                              ? `${Math.round(score * 100)}%`
                              : "\u2014"}
                          </Typography>
                        </Paper>
                      );
                    })
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
                      {t("dashboard.noCandidates")}
                    </Typography>
                  )
                )}
              </Box>
            </Paper>
          ))}
        </Box>
      </Box>

      {/* Recent Activity */}
      <Box>
        <Typography variant="h6" sx={{ fontWeight: 600, mb: 1.5 }}>
          {t("dashboard.recentActivity")}
        </Typography>
        <RecentActivity jobs={jobs} candidates={candidates} emails={emails} t={t} />
      </Box>
    </Box>
  );
}
