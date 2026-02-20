import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CloseOutlined, DeleteOutline } from "@mui/icons-material";
import { EVENT_COLORS } from "./calendarUtils";
import type { CalendarEvent, EventType, Candidate, Job, UserRole } from "../../types";

interface Props {
  date?: string;
  event?: CalendarEvent | null;
  candidates: Candidate[];
  jobs: Job[];
  role: UserRole;
  onSave: (data: Partial<CalendarEvent>) => void;
  onDelete?: () => void;
  onClose: () => void;
}

export default function EventModal({
  date,
  event,
  candidates,
  jobs,
  role,
  onSave,
  onDelete,
  onClose,
}: Props) {
  const { t } = useTranslation();
  const isEdit = !!event;
  const [title, setTitle] = useState(event?.title ?? "");
  const [startDate, setStartDate] = useState(
    event?.start_time ? event.start_time.slice(0, 10) : date ?? "",
  );
  const [startTime, setStartTime] = useState(
    event?.start_time ? event.start_time.slice(11, 16) : "09:00",
  );
  const [endTime, setEndTime] = useState(
    event?.end_time ? event.end_time.slice(11, 16) : "10:00",
  );
  const [eventType, setEventType] = useState<EventType>(event?.event_type ?? "other");
  const [candidateId, setCandidateId] = useState(event?.candidate_id ?? "");
  const [jobId, setJobId] = useState(event?.job_id ?? "");
  const [notes, setNotes] = useState(event?.notes ?? "");
  const [saving, setSaving] = useState(false);

  const EVENT_TYPE_LABELS: Record<EventType, string> = {
    interview: t("calendar.eventTypes.interview"),
    follow_up: t("calendar.eventTypes.follow_up"),
    offer: t("calendar.eventTypes.offer"),
    screening: t("calendar.eventTypes.screening"),
    other: t("calendar.eventTypes.other"),
  };

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
      <div className="w-full max-w-lg rounded-xl bg-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h3 className="text-lg font-semibold">
            {isEdit ? t("calendar.editEvent") : t("calendar.newEvent")}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <CloseOutlined className="h-5 w-5" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 px-6 py-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.title")}</label>
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("calendar.titlePlaceholder")}
              autoFocus
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.date")}</label>
              <input
                type="date"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.start")}</label>
              <input
                type="time"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.end")}</label>
              <input
                type="time"
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.type")}</label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(EVENT_TYPE_LABELS) as EventType[]).map((typ) => (
                <button
                  key={typ}
                  onClick={() => setEventType(typ)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    eventType === typ
                      ? `${EVENT_COLORS[typ].bg} ${EVENT_COLORS[typ].text} border-current`
                      : "border-gray-200 text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {EVENT_TYPE_LABELS[typ]}
                </button>
              ))}
            </div>
          </div>

          <div className={role === "recruiter" ? "grid grid-cols-2 gap-3" : ""}>
            {role === "recruiter" && (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.candidate")}</label>
                <select
                  className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  value={candidateId}
                  onChange={(e) => setCandidateId(e.target.value)}
                >
                  <option value="">{t("common.none")}</option>
                  {candidates.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.job")}</label>
              <select
                className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
              >
                <option value="">{t("common.none")}</option>
                {jobs.map((j) => (
                  <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">{t("calendar.notesLabel")}</label>
            <textarea
              className="w-full rounded-lg border px-3 py-2 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t("calendar.notesPlaceholder")}
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
                <DeleteOutline className="h-4 w-4" />
                {t("common.delete")}
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-lg border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >
              {t("common.cancel")}
            </button>
            <button
              onClick={handleSubmit}
              disabled={!title.trim() || !startDate || saving}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? t("common.saving") : isEdit ? t("calendar.update") : t("calendar.create")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
