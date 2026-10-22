import { requestJson } from "./api";

const SESSION_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isSessionId(value) {
  return SESSION_ID_RE.test(String(value).trim());
}

export function searchSessions({ query = "", scope = "upcoming", dateFrom = null, dateTo = null, page = 0 }) {
  const params = new URLSearchParams({ scope, page: String(page) });
  if (query.trim()) params.set("q", query.trim());
  if (dateFrom !== null) params.set("date_from", String(dateFrom));
  if (dateTo !== null) params.set("date_to", String(dateTo));
  return requestJson(`/api/sessions?${params}`, {
    fallbackMessage: "We couldn't load your sessions. Try again in a moment.",
  });
}

export function fetchSession(sessionId) {
  return requestJson(`/api/sessions/${encodeURIComponent(sessionId)}`, {
    fallbackMessage: "We couldn't open this session. Try again in a moment.",
  });
}

// Lowercased emails already registered to a session.
export function fetchRegisteredEmails(sessionId) {
  return requestJson(`/api/sessions/${encodeURIComponent(sessionId)}/emails`, {
    fallbackMessage: "We couldn't check who's already registered.",
  });
}

// Unix-second bounds of a local calendar day picked in an <input type="date">.
export function localDayBounds(isoDate) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const start = new Date(year, month - 1, day).getTime() / 1000;
  return { from: start, to: start + 86399 };
}

const STATUS_LABELS = {
  live: "Live now",
  upcoming: "Upcoming",
  on_demand: "On demand",
  past: "Ended",
  past_not_started: "Never started",
  canceled: "Canceled",
  draft: "Draft",
};

export function statusLabel(status) {
  return STATUS_LABELS[status] || status || "";
}

const weekdayFormat = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const dayFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const dayYearFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

// Start date in the viewer's own time zone, split for the date tile.
export function sessionStart(session) {
  if (!session?.estimated_started_at) return null;
  const date = new Date(session.estimated_started_at * 1000);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return {
    weekday: weekdayFormat.format(date),
    day: (sameYear ? dayFormat : dayYearFormat).format(date),
    time: timeFormat.format(date),
  };
}

export function sessionStartLabel(session) {
  const start = sessionStart(session);
  return start ? `${start.weekday} ${start.day}, ${start.time}` : "No date set";
}

export function registrantsLabel(count) {
  return `${count} registrant${count === 1 ? "" : "s"}`;
}

export function peopleLabel(count) {
  return `${count} ${count === 1 ? "person" : "people"}`;
}
