import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  X,
  Clock,
  User,
  Briefcase,
  Trash2,
  Edit3,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import {
  listEvents,
  createEvent,
  updateEvent,
  deleteEvent,
  listCandidates,
  listJobs,
} from "../lib/api";
import type { CalendarEvent, EventType, Candidate, Job } from "../types";

/* ── Helpers ──────────────────────────────────────────────────────────── */

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const EVENT_COLORS: Record<EventType, { dot: string; bg: string; text: string }> = {
  interview: { dot: "bg-purple-500", bg: "bg-purple-50 border-purple-200", text: "text-purple-700" },
  follow_up: { dot: "bg-blue-500", bg: "bg-blue-50 border-blue-200", text: "text-blue-700" },
  offer: { dot: "bg-green-500", bg: "bg-green-50 border-green-200", text: "text-green-700" },
  screening: { dot: "bg-amber-500", bg: "bg-amber-50 border-amber-200", text: "text-amber-700" },
  other: { dot: "bg-gray-400", bg: "bg-gray-50 border-gray-200", text: "text-gray-600" },
};

const EVENT_TYPE_LABELS: Record<EventType, string> = {
  interview: "Interview",
  follow_up: "Follow-up",
  offer: "Offer",
  screening: "Screening",
  other: "Other",
};

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

function toDateStr(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function toMonthStr(year: number, month: number) {
  return `${year}-${pad(month + 1)}`;
}

function formatTime(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDateShort(iso: string) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

/* ── Calendar grid logic ──────────────────────────────────────────────── */

function getCalendarDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrev = new Date(year, month, 0).getDate();

  const days: { date: Date; inMonth: boolean }[] = [];

  // Previous month padding
  for (let i = firstDay - 1; i >= 0; i--) {
    days.push({ date: new Date(year, month - 1, daysInPrev - i), inMonth: false });
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    days.push({ date: new Date(year, month, d), inMonth: true });
  }
  // Next month padding to fill 6 rows
  const remaining = 42 - days.length;
  for (let d = 1; d <= remaining; d++) {
    days.push({ date: new Date(year, month + 1, d), inMonth: false });
  }
  return days;
}

/* ── Event Modal ──────────────────────────────────────────────────────── */

function EventModal({
  date,
  event,
  candidates,
  jobs,
  onSave,
  onDelete,
  onClose,
}: {
  date?: string;
  event?: CalendarEvent | null;
  candidates: Candidate[];
  jobs: Job[];
  onSave: (data: Partial<CalendarEvent>) => void;
  onDelete?: () => void;
  onClose: () => void;
}) {
  const isEdit = !!event;
  const [title, setTitle] = useState(event?.title ?? "");
  const [startDate, setStartDate] = useState(
    event?.start_time ? event.start_time.slice(0, 10) : date ?? ""
  );
  const [startTime, setStartTime] = useState(
    event?.start_time ? event.start_time.slice(11, 16) : "09:00"
  );
  const [endTime, setEndTime] = useState(
    event?.end_time ? event.end_time.slice(11, 16) : "10:00"
  );
  const [eventType, setEventType] = useState<EventType>(event?.event_type ?? "other");
  const [candidateId, setCandidateId] = useState(event?.candidate_id ?? "");
  const [jobId, setJobId] = useState(event?.job_id ?? "");
  const [notes, setNotes] = useState(event?.notes ?? "");
  const [saving, setSaving] = useState(false);

  const selectedCandidate = candidates.find((c) => c.id === candidateId);
  const selectedJob = jobs.find((j) => j.id === jobId);

  const handleSubmit = async () => {
    if (!title.trim() || !startDate) return;
    setSaving(true);
    const startIso = `${startDate}T${startTime}:00`;
    const endIso = endTime ? `${startDate}T${endTime}:00` : "";
    await onSave({
      title: title.trim(),
      start_time: startIso,
      end_time: endIso,
      event_type: eventType,
      candidate_id: candidateId,
      candidate_name: selectedCandidate?.name ?? "",
      job_id: jobId,
      job_title: selectedJob?.title ?? "",
      notes,
    });
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">{isEdit ? "Edit Event" : "New Event"}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Title</label>
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Interview with John Smith"
              autoFocus
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Date</label>
              <input
                type="date"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Start</label>
              <input
                type="time"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">End</label>
              <input
                type="time"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Type</label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(EVENT_TYPE_LABELS) as EventType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => setEventType(t)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    eventType === t
                      ? `${EVENT_COLORS[t].bg} ${EVENT_COLORS[t].text} border-current`
                      : "border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {EVENT_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Candidate</label>
              <select
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={candidateId}
                onChange={(e) => setCandidateId(e.target.value)}
              >
                <option value="">None</option>
                {candidates.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Job</label>
              <select
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
              >
                <option value="">None</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Notes</label>
            <textarea
              className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="What needs to happen at this event..."
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t px-6 py-4">
          <div>
            {isEdit && onDelete && (
              <button
                onClick={onDelete}
                className="flex items-center gap-1 text-sm text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!title.trim() || !startDate || saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : isEdit ? "Update" : "Create"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Event Detail Modal ───────────────────────────────────────────────── */

function EventDetailModal({
  event,
  onEdit,
  onDelete,
  onClose,
}: {
  event: CalendarEvent;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  const colors = EVENT_COLORS[event.event_type] || EVENT_COLORS.other;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`rounded-t-xl border-b px-6 py-4 ${colors.bg}`}>
          <div className="flex items-start justify-between">
            <div>
              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors.text}`}>
                {EVENT_TYPE_LABELS[event.event_type] || "Other"}
              </span>
              <h3 className="mt-1 text-lg font-semibold text-gray-900">{event.title}</h3>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-3 px-6 py-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Clock className="h-4 w-4" />
            <span>
              {formatDateShort(event.start_time)} {formatTime(event.start_time)}
              {event.end_time ? ` — ${formatTime(event.end_time)}` : ""}
            </span>
          </div>

          {event.candidate_name && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <User className="h-4 w-4" />
              <span>{event.candidate_name}</span>
            </div>
          )}

          {event.job_title && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Briefcase className="h-4 w-4" />
              <span>{event.job_title}</span>
            </div>
          )}

          {event.notes && (
            <div className="mt-2 rounded-lg bg-gray-50 p-3 text-sm text-gray-700 whitespace-pre-wrap">
              {event.notes}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t px-6 py-4">
          <button
            onClick={onDelete}
            className="flex items-center gap-1 rounded-lg border border-red-200 px-3 py-2 text-sm text-red-600 hover:bg-red-50"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
          <button
            onClick={onEdit}
            className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Edit3 className="h-4 w-4" />
            Edit
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Calendar Component ──────────────────────────────────────────── */

export default function Calendar() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const todayStr = toDateStr(today);

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createDate, setCreateDate] = useState("");
  const [showDetailModal, setShowDetailModal] = useState<CalendarEvent | null>(null);
  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);

  const monthStr = toMonthStr(year, month);
  const fetchEvents = useCallback(() => listEvents({ month: monthStr }), [monthStr]);
  const { data: events, refresh } = useApi(fetchEvents);

  // Prefetch adjacent months for smoother navigation
  const prevMonthStr = toMonthStr(month === 0 ? year - 1 : year, month === 0 ? 11 : month - 1);
  const nextMonthStr = toMonthStr(month === 11 ? year + 1 : year, month === 11 ? 0 : month + 1);
  const fetchPrev = useCallback(() => listEvents({ month: prevMonthStr }), [prevMonthStr]);
  const fetchNext = useCallback(() => listEvents({ month: nextMonthStr }), [nextMonthStr]);
  const { data: prevEvents } = useApi(fetchPrev);
  const { data: nextEvents } = useApi(fetchNext);

  // Merge all events for display
  const allEvents = useMemo(() => [
    ...(prevEvents ?? []),
    ...(events ?? []),
    ...(nextEvents ?? []),
  ], [prevEvents, events, nextEvents]);

  // Candidates & jobs for the modal dropdowns
  const fetchCandidates = useCallback(() => listCandidates(), []);
  const fetchJobs = useCallback(() => listJobs(), []);
  const { data: candidates } = useApi(fetchCandidates);
  const { data: jobs } = useApi(fetchJobs);

  // Group events by date
  const eventsByDate = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const e of allEvents) {
      const dateKey = e.start_time.slice(0, 10);
      if (!map[dateKey]) map[dateKey] = [];
      map[dateKey].push(e);
    }
    return map;
  }, [allEvents]);

  // Upcoming events (next 7 days)
  const upcoming = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(end.getDate() + 7);
    return allEvents
      .filter((e) => {
        const d = new Date(e.start_time);
        return d >= start && d < end;
      })
      .sort((a, b) => a.start_time.localeCompare(b.start_time));
  }, [allEvents]);

  const calendarDays = useMemo(() => getCalendarDays(year, month), [year, month]);

  // Navigation
  const goPrev = () => {
    if (month === 0) { setYear(year - 1); setMonth(11); }
    else setMonth(month - 1);
  };
  const goNext = () => {
    if (month === 11) { setYear(year + 1); setMonth(0); }
    else setMonth(month + 1);
  };
  const goToday = () => {
    setYear(today.getFullYear());
    setMonth(today.getMonth());
  };

  // CRUD handlers
  const handleCreate = async (data: Partial<CalendarEvent>) => {
    await createEvent(data as Parameters<typeof createEvent>[0]);
    setShowCreateModal(false);
    refresh();
  };

  const handleUpdate = async (data: Partial<CalendarEvent>) => {
    if (!editEvent) return;
    await updateEvent(editEvent.id, data);
    setEditEvent(null);
    setShowDetailModal(null);
    refresh();
  };

  const handleDelete = async (id: string) => {
    await deleteEvent(id);
    setShowDetailModal(null);
    setEditEvent(null);
    refresh();
  };

  // Click on a date cell
  const handleDateClick = (dateStr: string) => {
    setCreateDate(dateStr);
    setShowCreateModal(true);
  };

  // Click on an event title
  const handleEventClick = (e: React.MouseEvent, event: CalendarEvent) => {
    e.stopPropagation();
    setShowDetailModal(event);
  };

  // Keyboard: Escape to close modals
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowCreateModal(false);
        setShowDetailModal(null);
        setEditEvent(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-full gap-6">
      {/* Main calendar area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              {MONTH_NAMES[month]} {year}
            </h1>
            <div className="flex items-center gap-1">
              <button
                onClick={goPrev}
                className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <button
                onClick={goToday}
                className="rounded-lg border px-3 py-1 text-sm font-medium text-gray-600 hover:bg-gray-50"
              >
                Today
              </button>
              <button
                onClick={goNext}
                className="rounded-lg p-1.5 text-gray-500 hover:bg-gray-100"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>
          </div>
          <button
            onClick={() => { setCreateDate(todayStr); setShowCreateModal(true); }}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            New Event
          </button>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 border-b">
          {DAY_NAMES.map((d) => (
            <div key={d} className="py-2 text-center text-xs font-semibold text-gray-500">
              {d}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid flex-1 grid-cols-7 grid-rows-6 border-l">
          {calendarDays.map(({ date, inMonth }, i) => {
            const dateStr = toDateStr(date);
            const isToday = dateStr === todayStr;
            const dayEvents = eventsByDate[dateStr] ?? [];

            return (
              <div
                key={i}
                onClick={() => inMonth && handleDateClick(dateStr)}
                className={`relative border-b border-r p-1.5 transition-colors ${
                  inMonth
                    ? "cursor-pointer hover:bg-blue-50/50"
                    : "bg-gray-50/50"
                }`}
              >
                <span
                  className={`inline-flex h-7 w-7 items-center justify-center rounded-full text-sm ${
                    isToday
                      ? "bg-blue-600 font-bold text-white"
                      : inMonth
                        ? "text-gray-900"
                        : "text-gray-300"
                  }`}
                >
                  {date.getDate()}
                </span>

                {/* Event pills */}
                <div className="mt-0.5 space-y-0.5">
                  {dayEvents.slice(0, 3).map((evt) => {
                    const c = EVENT_COLORS[evt.event_type] || EVENT_COLORS.other;
                    return (
                      <button
                        key={evt.id}
                        onClick={(e) => handleEventClick(e, evt)}
                        className={`flex w-full items-center gap-1 truncate rounded px-1.5 py-0.5 text-left text-xs transition-opacity hover:opacity-80 ${c.bg} border`}
                      >
                        <span className={`h-1.5 w-1.5 flex-shrink-0 rounded-full ${c.dot}`} />
                        <span className={`truncate font-medium ${c.text}`}>{evt.title}</span>
                      </button>
                    );
                  })}
                  {dayEvents.length > 3 && (
                    <span className="block px-1.5 text-xs text-gray-400">
                      +{dayEvents.length - 3} more
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Upcoming sidebar */}
      <div className="w-72 flex-shrink-0 rounded-xl border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-900">Upcoming (7 days)</h2>
        {upcoming.length === 0 ? (
          <p className="text-sm text-gray-400">No upcoming events</p>
        ) : (
          <div className="space-y-2">
            {upcoming.map((evt) => {
              const c = EVENT_COLORS[evt.event_type] || EVENT_COLORS.other;
              return (
                <button
                  key={evt.id}
                  onClick={() => setShowDetailModal(evt)}
                  className={`w-full rounded-lg border p-3 text-left transition-colors hover:shadow-sm ${c.bg}`}
                >
                  <div className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${c.dot}`} />
                    <span className={`text-sm font-medium ${c.text}`}>{evt.title}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-1 text-xs text-gray-500">
                    <Clock className="h-3 w-3" />
                    {formatDateShort(evt.start_time)} {formatTime(evt.start_time)}
                  </div>
                  {evt.candidate_name && (
                    <div className="mt-0.5 flex items-center gap-1 text-xs text-gray-500">
                      <User className="h-3 w-3" />
                      {evt.candidate_name}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Modals */}
      {showCreateModal && (
        <EventModal
          date={createDate}
          candidates={candidates ?? []}
          jobs={jobs ?? []}
          onSave={handleCreate}
          onClose={() => setShowCreateModal(false)}
        />
      )}

      {showDetailModal && !editEvent && (
        <EventDetailModal
          event={showDetailModal}
          onEdit={() => setEditEvent(showDetailModal)}
          onDelete={() => handleDelete(showDetailModal.id)}
          onClose={() => setShowDetailModal(null)}
        />
      )}

      {editEvent && (
        <EventModal
          event={editEvent}
          candidates={candidates ?? []}
          jobs={jobs ?? []}
          onSave={handleUpdate}
          onDelete={() => handleDelete(editEvent.id)}
          onClose={() => { setEditEvent(null); setShowDetailModal(null); }}
        />
      )}
    </div>
  );
}
