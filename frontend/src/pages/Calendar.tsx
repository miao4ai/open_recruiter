import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Calendar as BigCalendar, luxonLocalizer, Views, type View } from "react-big-calendar";
import { DateTime, Settings as LuxonSettings } from "luxon";
import "react-big-calendar/lib/css/react-big-calendar.css";
import "../components/calendar/calendarStyles.css";
import { AddOutlined, PublicOutlined } from "@mui/icons-material";
import { useApi } from "../hooks/useApi";
import {
  listEvents,
  createEvent,
  updateEvent,
  deleteEvent,
  listCandidates,
  listJobs,
  seekerListJobs,
} from "../lib/api";
import type { CalendarEvent, UserRole } from "../types";
import EventModal from "../components/calendar/EventModal";
import EventDetailModal from "../components/calendar/EventDetailModal";
import {
  toBigCalendarEvents,
  EVENT_COLORS,
  TIMEZONE_OPTIONS,
  type BigCalendarEvent,
} from "../components/calendar/calendarUtils";

interface Props {
  role?: UserRole;
}

export default function Calendar({ role = "recruiter" }: Props) {
  const { t, i18n } = useTranslation();

  // Timezone — default to browser local
  const [timezone, setTimezone] = useState(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone,
  );

  // Luxon localizer — re-create when language changes
  const localizer = useMemo(() => {
    const localeMap: Record<string, string> = {
      en: "en-US",
      ja: "ja-JP",
      ko: "ko-KR",
      zh: "zh-CN",
      es: "es-ES",
    };
    LuxonSettings.defaultLocale = localeMap[i18n.language] || "en-US";
    return luxonLocalizer(DateTime);
  }, [i18n.language]);

  // Current date & view
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<View>(Views.MONTH);

  // Month string for API fetch
  const monthStr = useMemo(() => DateTime.fromJSDate(currentDate).toFormat("yyyy-MM"), [currentDate]);

  // Fetch events
  const fetchEvents = useCallback(() => listEvents({ month: monthStr }), [monthStr]);
  const { data: events, refresh } = useApi(fetchEvents);

  // Fetch candidates (recruiter only) and jobs
  const fetchCandidates = useCallback(
    () => (role === "recruiter" ? listCandidates() : Promise.resolve([])),
    [role],
  );
  const fetchJobs = useCallback(
    () => (role === "recruiter" ? listJobs() : seekerListJobs()),
    [role],
  );
  const { data: candidates } = useApi(fetchCandidates);
  const { data: jobs } = useApi(fetchJobs);

  // Convert to BigCalendar format
  const bigCalEvents = useMemo(
    () => toBigCalendarEvents(events ?? [], timezone),
    [events, timezone],
  );

  // Modal state
  const [showCreate, setShowCreate] = useState(false);
  const [createDate, setCreateDate] = useState("");
  const [detailEvent, setDetailEvent] = useState<CalendarEvent | null>(null);
  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);

  // CRUD handlers
  const handleCreate = async (data: Partial<CalendarEvent>) => {
    await createEvent(data as Parameters<typeof createEvent>[0]);
    setShowCreate(false);
    refresh();
  };

  const handleUpdate = async (data: Partial<CalendarEvent>) => {
    if (!editEvent) return;
    await updateEvent(editEvent.id, data);
    setEditEvent(null);
    setDetailEvent(null);
    refresh();
  };

  const handleDelete = async (id: string) => {
    await deleteEvent(id);
    setDetailEvent(null);
    setEditEvent(null);
    refresh();
  };

  // Escape key closes modals
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowCreate(false);
        setDetailEvent(null);
        setEditEvent(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Event style getter for colour-coding
  const eventPropGetter = useCallback((event: BigCalendarEvent) => {
    const c = EVENT_COLORS[event.resource.event_type] || EVENT_COLORS.other;
    return {
      style: {
        backgroundColor: c.hex,
        borderRadius: "4px",
        color: "white",
        border: "none",
        fontSize: "0.75rem",
      },
    };
  }, []);

  // i18n messages for react-big-calendar toolbar
  const messages = useMemo(
    () => ({
      today: t("common.today"),
      previous: t("calendar.previous"),
      next: t("calendar.next"),
      month: t("calendar.viewMonth"),
      week: t("calendar.viewWeek"),
      day: t("calendar.viewDay"),
      agenda: t("calendar.viewAgenda"),
      noEventsInRange: t("calendar.noEventsInRange"),
      showMore: (count: number) => t("calendar.more", { count }),
    }),
    [t],
  );

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Timezone selector */}
          <div className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm text-gray-600">
            <PublicOutlined sx={{ fontSize: 16 }} />
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="bg-transparent text-sm outline-none"
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz} value={tz}>
                  {tz.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          onClick={() => {
            setCreateDate(DateTime.now().toISODate()!);
            setShowCreate(true);
          }}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <AddOutlined sx={{ fontSize: 18 }} />
          {t("calendar.newEvent")}
        </button>
      </div>

      {/* BigCalendar */}
      <div className="min-h-0 flex-1">
        <BigCalendar
          localizer={localizer}
          events={bigCalEvents}
          startAccessor="start"
          endAccessor="end"
          date={currentDate}
          onNavigate={setCurrentDate}
          view={view}
          onView={(v) => setView(v)}
          views={[Views.MONTH, Views.WEEK, Views.DAY, Views.AGENDA]}
          selectable
          onSelectSlot={(slotInfo) => {
            setCreateDate(DateTime.fromJSDate(slotInfo.start).toISODate()!);
            setShowCreate(true);
          }}
          onSelectEvent={(event) => setDetailEvent((event as BigCalendarEvent).resource)}
          eventPropGetter={eventPropGetter as never}
          messages={messages}
          style={{ height: "100%" }}
          popup
        />
      </div>

      {/* Modals */}
      {showCreate && (
        <EventModal
          date={createDate}
          candidates={candidates ?? []}
          jobs={jobs ?? []}
          role={role}
          onSave={handleCreate}
          onClose={() => setShowCreate(false)}
        />
      )}

      {detailEvent && !editEvent && (
        <EventDetailModal
          event={detailEvent}
          onEdit={() => setEditEvent(detailEvent)}
          onDelete={() => handleDelete(detailEvent.id)}
          onClose={() => setDetailEvent(null)}
        />
      )}

      {editEvent && (
        <EventModal
          event={editEvent}
          candidates={candidates ?? []}
          jobs={jobs ?? []}
          role={role}
          onSave={handleUpdate}
          onDelete={() => handleDelete(editEvent.id)}
          onClose={() => {
            setEditEvent(null);
            setDetailEvent(null);
          }}
        />
      )}
    </div>
  );
}
