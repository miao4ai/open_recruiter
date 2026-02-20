import { DateTime } from "luxon";
import type { CalendarEvent, EventType } from "../../types";

/* -- Event type colour map ------------------------------------------------- */

export const EVENT_COLORS: Record<
  EventType,
  { dot: string; bg: string; text: string; hex: string }
> = {
  interview: {
    dot: "bg-purple-500",
    bg: "bg-purple-50 border-purple-200",
    text: "text-purple-700",
    hex: "#8b5cf6",
  },
  follow_up: {
    dot: "bg-blue-500",
    bg: "bg-blue-50 border-blue-200",
    text: "text-blue-700",
    hex: "#3b82f6",
  },
  offer: {
    dot: "bg-green-500",
    bg: "bg-green-50 border-green-200",
    text: "text-green-700",
    hex: "#22c55e",
  },
  screening: {
    dot: "bg-amber-500",
    bg: "bg-amber-50 border-amber-200",
    text: "text-amber-700",
    hex: "#f59e0b",
  },
  other: {
    dot: "bg-gray-400",
    bg: "bg-gray-50 border-gray-200",
    text: "text-gray-600",
    hex: "#9ca3af",
  },
};

/* -- react-big-calendar event adapter -------------------------------------- */

export interface BigCalendarEvent {
  id: string;
  title: string;
  start: Date;
  end: Date;
  resource: CalendarEvent;
}

export function toBigCalendarEvents(
  events: CalendarEvent[],
  timezone: string,
): BigCalendarEvent[] {
  return events.map((e) => {
    const start = DateTime.fromISO(e.start_time, { zone: timezone }).toJSDate();
    const end = e.end_time
      ? DateTime.fromISO(e.end_time, { zone: timezone }).toJSDate()
      : DateTime.fromISO(e.start_time, { zone: timezone })
          .plus({ hours: 1 })
          .toJSDate();
    return { id: e.id, title: e.title, start, end, resource: e };
  });
}

/* -- Timezone options ------------------------------------------------------ */

export const TIMEZONE_OPTIONS = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Madrid",
  "Asia/Tokyo",
  "Asia/Seoul",
  "Asia/Shanghai",
  "Asia/Kolkata",
  "Australia/Sydney",
  "Pacific/Auckland",
  "UTC",
];
