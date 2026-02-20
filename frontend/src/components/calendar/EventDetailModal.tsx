import { useTranslation } from "react-i18next";
import {
  CloseOutlined,
  AccessTimeOutlined,
  PersonOutline,
  WorkOutline,
  DeleteOutline,
  EditOutlined,
} from "@mui/icons-material";
import { EVENT_COLORS } from "./calendarUtils";
import type { CalendarEvent, EventType } from "../../types";

function formatTime(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDateShort(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" });
}

interface Props {
  event: CalendarEvent;
  onEdit: () => void;
  onDelete: () => void;
  onClose: () => void;
}

export default function EventDetailModal({ event, onEdit, onDelete, onClose }: Props) {
  const { t } = useTranslation();
  const colors = EVENT_COLORS[event.event_type] || EVENT_COLORS.other;

  const EVENT_TYPE_LABELS: Record<EventType, string> = {
    interview: t("calendar.eventTypes.interview"),
    follow_up: t("calendar.eventTypes.follow_up"),
    offer: t("calendar.eventTypes.offer"),
    screening: t("calendar.eventTypes.screening"),
    other: t("calendar.eventTypes.other"),
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={`rounded-t-xl border-b px-6 py-4 ${colors.bg}`}>
          <div className="flex items-start justify-between">
            <div>
              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors.text}`}>
                {EVENT_TYPE_LABELS[event.event_type] || t("calendar.eventTypes.other")}
              </span>
              <h3 className="mt-1 text-lg font-semibold text-gray-900">{event.title}</h3>
            </div>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <CloseOutlined className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="space-y-3 px-6 py-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <AccessTimeOutlined className="h-4 w-4" />
            <span>
              {formatDateShort(event.start_time)} {formatTime(event.start_time)}
              {event.end_time ? ` — ${formatTime(event.end_time)}` : ""}
            </span>
          </div>

          {event.candidate_name && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <PersonOutline className="h-4 w-4" />
              <span>{event.candidate_name}</span>
            </div>
          )}

          {event.job_title && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <WorkOutline className="h-4 w-4" />
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
            <DeleteOutline className="h-4 w-4" />
            {t("common.delete")}
          </button>
          <button
            onClick={onEdit}
            className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <EditOutlined className="h-4 w-4" />
            {t("common.edit")}
          </button>
        </div>
      </div>
    </div>
  );
}
