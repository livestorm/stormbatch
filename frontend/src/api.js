// Shared helpers for calling the StormBatch API.

export const SESSION_EXPIRED_MESSAGE =
  "Your Livestorm session has expired. Please reconnect your account.";

let sessionExpiredHandler = () => {};

// Carries the HTTP status so callers can tell an expired login (401) from a
// failure they can work around.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// A 401 means the Livestorm token is gone or expired; the app registers a
// handler that sends the user back to the connect screen.
export function onSessionExpired(handler) {
  sessionExpiredHandler = handler;
}

export async function readApiResponse(response, fallbackMessage) {
  if (response.status === 401) {
    sessionExpiredHandler();
    throw new ApiError(SESSION_EXPIRED_MESSAGE, 401);
  }
  const text = await response.text();
  if (!text.trim()) {
    if (!response.ok) throw new ApiError(fallbackMessage, response.status);
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(fallbackMessage, response.status);
  }
}

export function errorDetail(data, fallbackMessage) {
  // FastAPI validation errors carry a list, not a message.
  return typeof data?.detail === "string" && data.detail ? data.detail : fallbackMessage;
}

export async function requestJson(url, { method = "GET", body, fallbackMessage = "Request failed." } = {}) {
  const init = { method };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const response = await fetch(url, init);
  const data = await readApiResponse(response, fallbackMessage);
  if (!response.ok) throw new ApiError(errorDetail(data, fallbackMessage), response.status);
  return data;
}

export function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
