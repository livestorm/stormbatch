<script setup>
import { computed, onMounted, ref, watch } from "vue";
import ApiKeyInput from "./components/ApiKeyInput.vue";
import BetaInfoModal from "./components/BetaInfoModal.vue";
import FileUpload from "./components/FileUpload.vue";
import JobResults from "./components/JobResults.vue";
import PreviewTable from "./components/PreviewTable.vue";
import SessionIdsInput from "./components/SessionIdsInput.vue";
import SourceSessionInput from "./components/SourceSessionInput.vue";
import livestormIcon from "../assets/Icon-Livestorm-Tertiary-Light.png";

const showBetaInfo = ref(false);

const BULK_JOB_CHUNK_SIZE = 50;
const JOB_STATUS_POLL_INTERVAL_MS = 5000;

// ── Auth ───────────────────────────────────────────────────────────────────────

const isAuthenticated = ref(false);
const isAuthLoading = ref(true);
const userProfile = ref(null);

const userInitials = computed(() => {
  const p = userProfile.value;
  if (!p) return "";
  const first = (p.first_name || "").trim();
  const last = (p.last_name || "").trim();
  const email = (p.email || "").trim();
  if (first && last) return (first[0] + last[0]).toUpperCase();
  if (first) return first[0].toUpperCase();
  if (email) return email[0].toUpperCase();
  return "";
});

const userName = computed(() => {
  const p = userProfile.value;
  if (!p) return "";
  const full = [p.first_name, p.last_name].filter(Boolean).join(" ");
  return full || p.email || "";
});

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    isAuthenticated.value = data.authenticated;
    if (data.authenticated) { fetchUserProfile(); currentStep.value = 2; }
  } catch {
    isAuthenticated.value = false;
  } finally {
    isAuthLoading.value = false;
  }
}

async function fetchUserProfile() {
  try {
    const res = await fetch("/api/auth/me");
    if (res.ok) userProfile.value = await res.json();
  } catch { /* profile is optional — fail silently */ }
}

function handleLogin() {
  window.location.href = "/api/auth/livestorm/login";
}

async function handleLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  isAuthenticated.value = false;
  userProfile.value = null;
  startNewBatch();
  currentStep.value = 1;
}

onMounted(() => {
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth_error");
  if (authError) {
    errorMessage.value = `Livestorm connection failed: ${authError.replace(/_/g, " ")}.`;
    window.history.replaceState({}, "", window.location.pathname);
  }
  checkAuthStatus();
});

// ── Source mode ────────────────────────────────────────────────────────────────

const sourceMode = ref("upload"); // "upload" | "transfer"

function setSourceMode(mode) {
  if (mode === sourceMode.value) return;
  sourceMode.value = mode;
  selectedFile.value = null;
  preview.value = null;
  columnSettings.value = [];
  duplicateEmails.value = [];
  sourceSessionId.value = "";
  transferData.value = null;
  transferExcludedRows.value = {};
  transferIncludedFields.value = [];
  isSourceLoading.value = false;
  jobs.value = [];
  hasSubmittedJobs.value = false;
  rowResults.value = [];
  totalSessionCount.value = 0;
  createdSessionCount.value = 0;
  resetMessages();
  resetSessionFieldsState();
}

// ── Upload mode state ──────────────────────────────────────────────────────────

const selectedFile = ref(null);
const preview = ref(null);
const columnSettings = ref([]);
const duplicateEmails = ref([]);
const isPreviewLoading = ref(false);

// ── Field validation state ─────────────────────────────────────────────────────

const sessionFieldsState = ref({
  fields: [],
  loading: false,
  error: "",
  validated: false,
  hasPeople: false,
  sessionId: "",
});

// ── Transfer mode state ────────────────────────────────────────────────────────

const sourceSessionId = ref("");
const transferData = ref(null); // { session_id, headers, rows, total }
const transferExcludedRows = ref({}); // { [rowIndex]: true }
const transferIncludedFields = ref([]); // field IDs to send
const isSourceLoading = ref(false);

// ── Shared state ───────────────────────────────────────────────────────────────

const sessionIds = ref([]);
const jobs = ref([]);
const errorMessage = ref("");
const successMessage = ref("");
const isSubmitting = ref(false);
const rowResults = ref([]);
const hasSubmittedJobs = ref(false);
const retryingSessions = ref({});
const totalSessionCount = ref(0);
const createdSessionCount = ref(0);

// ── Computed ───────────────────────────────────────────────────────────────────

const parsedSessionIds = computed(() => sessionIds.value);

// ── Step navigation ────────────────────────────────────────────────────────────

const currentStep = ref(1); // 1 = Connect, 2 = Source, 3 = Target

const sourceReady = computed(() =>
  sourceMode.value === "upload" ? Boolean(preview.value) : Boolean(transferData.value),
);

function goToStep(step) {
  if (step === 1) return;
  if (!isAuthenticated.value) return;
  if (step === 3 && !sourceReady.value) return;
  currentStep.value = step;
  if (step === 3 && sourceMode.value === "upload" && parsedSessionIds.value.length > 0 && !sessionFieldsState.value.validated && !sessionFieldsState.value.loading) {
    validateSessionFields();
  }
}

// Upload mode
const emailColumn = computed(() => {
  if (!preview.value) return "";
  return (
    preview.value.headers.find(
      (h) => preview.value.normalized_headers[h] === "email",
    ) || ""
  );
});

const hasEmailColumn = computed(() => Boolean(emailColumn.value));

const autoMapping = computed(() =>
  Object.fromEntries(
    columnSettings.value
      .filter((c) => c.include)
      .map((c) => [c.column, c.attributeId.trim()]),
  ),
);

const mappedAttributePreview = computed(() =>
  columnSettings.value.map((c) => ({ ...c, required: c.attributeId === "email" })),
);

// Transfer mode
const transferActiveRows = computed(() => {
  if (!transferData.value) return [];
  return transferData.value.rows.filter((_, i) => !transferExcludedRows.value[i]);
});

const transferExcludedCount = computed(
  () => Object.keys(transferExcludedRows.value).length,
);

// Shared / progress
const expectedJobCount = computed(() => {
  if (sourceMode.value === "transfer") {
    if (!transferActiveRows.value.length || !parsedSessionIds.value.length) return 0;
    return (
      parsedSessionIds.value.length *
      Math.max(1, Math.ceil(transferActiveRows.value.length / BULK_JOB_CHUNK_SIZE))
    );
  }
  if (!preview.value || !parsedSessionIds.value.length) return parsedSessionIds.value.length;
  return (
    parsedSessionIds.value.length *
    Math.max(1, Math.ceil(preview.value.row_count / BULK_JOB_CHUNK_SIZE))
  );
});

const isReadyToSubmit = computed(() => {
  if (!isAuthenticated.value || !parsedSessionIds.value.length) return false;
  if (sourceMode.value === "upload") {
    return (
      Boolean(preview.value) &&
      hasEmailColumn.value &&
      Object.values(autoMapping.value).includes("email")
    );
  }
  return (
    Boolean(transferData.value) &&
    transferIncludedFields.value.includes("email") &&
    transferActiveRows.value.length > 0
  );
});

// ── Field validation computed ──────────────────────────────────────────────────

const validFieldIds = computed(() => new Set(sessionFieldsState.value.fields.map((f) => f.id)));

const hasInvalidIncludedMappings = computed(() => {
  if (!sessionFieldsState.value.validated || !sessionFieldsState.value.hasPeople) return false;
  const validIds = validFieldIds.value;
  return Object.values(autoMapping.value).some(
    (attrId) => attrId && attrId !== "email" && !validIds.has(attrId),
  );
});

const canSubmit = computed(() => isReadyToSubmit.value && !hasInvalidIncludedMappings.value);

function isFieldMapped(fieldId) {
  return Object.values(autoMapping.value).includes(fieldId);
}

function onCheckAttrChange(idx, value) {
  const trimmed = value.trim();
  const isNowValid = trimmed === "email" || validFieldIds.value.has(trimmed);
  updateColumnSetting(idx, {
    attributeId: trimmed,
    ...(isNowValid ? { include: true } : {}),
  });
}

const finishedJobs = computed(
  () =>
    jobs.value.filter((j) =>
      ["ended", "failed", "completed"].includes(String(j.status).toLowerCase()),
    ).length,
);

function taskStatus(task) {
  return task?.attributes?.status || task?.status || "unknown";
}

function taskError(task) {
  const attrs = task?.attributes || {};
  const errors = attrs.errors || task?.errors;
  if (Array.isArray(errors)) {
    return errors.map((e) => e.detail || e.title || e.message || String(e)).join(", ");
  }
  return attrs.error || attrs.message || task?.error || task?.message || "";
}

function isAlreadyRegisteredMessage(message) {
  const n = String(message).toLowerCase();
  return (
    n.includes("already been invited") ||
    n.includes("already registered") ||
    n.includes("has already been taken") ||
    n.includes("already been registered")
  );
}

function failedJobTasks(job) {
  return (job.tasks || []).filter(
    (t) => String(taskStatus(t)).toLowerCase() === "failed",
  );
}

function hasActionableFailure(job) {
  const status = String(job.status).toLowerCase();
  const failed = failedJobTasks(job);
  if (failed.length) return failed.some((t) => !isAlreadyRegisteredMessage(taskError(t)));
  return status === "failed";
}

const progressPercent = computed(() => {
  const total = totalSessionCount.value || jobs.value.length;
  if (!total) return 0;
  return Math.min(100, Math.round((createdSessionCount.value / total) * 100));
});

const isPollingJobs = computed(() =>
  jobs.value.some(
    (j) => !["ended", "failed", "completed"].includes(String(j.status).toLowerCase()),
  ),
);

const visibleResultJobs = computed(() =>
  jobs.value.filter((j) => hasActionableFailure(j) || j.retry_results?.length),
);

const registrationSummary = computed(() => {
  const taskResults = jobs.value.flatMap((j) => j.tasks || []);
  const failedTasks = taskResults.filter(
    (t) => String(taskStatus(t)).toLowerCase() === "failed",
  ).length;
  const failedJobs = jobs.value.filter((j) => hasActionableFailure(j)).length;
  const alreadyRegisteredOnlyJobs = jobs.value.filter((j) => {
    const failed = failedJobTasks(j);
    return failed.length > 0 && !hasActionableFailure(j);
  }).length;
  return {
    jobs: totalSessionCount.value || jobs.value.length || (isSubmitting.value ? expectedJobCount.value : 0),
    created: createdSessionCount.value,
    finished: finishedJobs.value,
    totalTasks: taskResults.length,
    failedTasks,
    failedJobs,
    alreadyRegisteredOnlyJobs,
  };
});

const progressTitle = computed(() => {
  if (isSubmitting.value) return sourceMode.value === "transfer" ? "Transferring…" : "Registering…";
  if (isPollingJobs.value) return "Checking results…";
  return registrationSummary.value.failedJobs ? "Batch finished with failed jobs" : "Batch complete";
});

const progressMessage = computed(() => {
  if (isSubmitting.value) {
    const total = totalSessionCount.value || expectedJobCount.value;
    const current = Math.min(createdSessionCount.value + 1, total);
    return total
      ? `Processing batch ${current} of ${total}.`
      : sourceMode.value === "transfer"
        ? "Transferring registrants to Livestorm."
        : "Sending registrants to Livestorm.";
  }
  if (isPollingJobs.value) return "Checking Livestorm results.";
  return registrationSummary.value.failedJobs
    ? "Review the rows that need attention below."
    : "All done. Review the results below.";
});

const completionTitle = computed(() =>
  registrationSummary.value.failedJobs ? "Some registrants need attention" : "All registrants are in",
);

const completionMessage = computed(() => {
  const { failedJobs, alreadyRegisteredOnlyJobs } = registrationSummary.value;
  if (failedJobs) return "Some rows couldn't be registered. Check the details below and retry if needed.";
  if (alreadyRegisteredOnlyJobs)
    return "Nice work. Some were already registered in Livestorm — they're all set.";
  return "Nice work. Livestorm accepted the full batch.";
});

// ── Helpers ────────────────────────────────────────────────────────────────────

function resetMessages() {
  errorMessage.value = "";
  successMessage.value = "";
}

function resetSessionFieldsState() {
  sessionFieldsState.value = {
    fields: [],
    loading: false,
    error: "",
    validated: false,
    hasPeople: false,
    sessionId: "",
  };
}

async function validateSessionFields() {
  const sessionId = parsedSessionIds.value[0];
  if (!sessionId || sourceMode.value !== "upload") return;

  sessionFieldsState.value = {
    fields: [],
    loading: true,
    error: "",
    validated: false,
    hasPeople: false,
    sessionId,
  };

  try {
    const response = await fetch("/api/session-fields", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await readApiResponse(response, "Failed to fetch session fields");
    if (!response.ok) throw new Error(data.detail || "Failed to fetch session fields");

    sessionFieldsState.value = {
      fields: data.fields || [],
      loading: false,
      error: "",
      validated: true,
      hasPeople: data.has_people,
      sessionId,
    };

    // Auto-disable columns whose attribute ID does not exist in the session's form
    if (data.has_people && data.fields?.length > 0) {
      const validIds = new Set(data.fields.map((f) => f.id));
      columnSettings.value = columnSettings.value.map((c) => {
        if (c.attributeId === "email") return c;
        if (c.include && c.attributeId && !validIds.has(c.attributeId.trim())) {
          return { ...c, include: false };
        }
        return c;
      });
    }
  } catch (error) {
    sessionFieldsState.value = {
      fields: [],
      loading: false,
      error: error.message,
      validated: false,
      hasPeople: false,
      sessionId,
    };
  }
}

async function readApiResponse(response, fallbackMessage) {
  const text = await response.text();
  if (!text.trim()) {
    if (!response.ok) throw new Error(fallbackMessage);
    return {};
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(fallbackMessage);
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Upload mode handlers ───────────────────────────────────────────────────────

function onFileSelected(file) {
  selectedFile.value = file;
  preview.value = null;
  columnSettings.value = [];
  jobs.value = [];
  rowResults.value = [];
  hasSubmittedJobs.value = false;
  duplicateEmails.value = [];
  resetMessages();
}

async function loadPreview() {
  if (!selectedFile.value) {
    errorMessage.value = "Please choose an .xlsx or .csv file first.";
    return;
  }
  resetMessages();
  isPreviewLoading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    const response = await fetch("/api/preview", { method: "POST", body: formData });
    const data = await readApiResponse(
      response,
      "Preview failed. The server returned an empty or invalid response.",
    );
    if (!response.ok) throw new Error(data.detail || "Preview failed");

    preview.value = data;
    columnSettings.value = data.headers.map((h) => ({
      column: h,
      attributeId: data.normalized_headers[h],
      include: true,
    }));
    const detectedEmailCol = data.headers.find(
      (h) => data.normalized_headers[h] === "email",
    );
    duplicateEmails.value = detectedEmailCol
      ? data.duplicate_email_columns[detectedEmailCol] || []
      : [];
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isPreviewLoading.value = false;
  }
}

function updateColumnSetting(index, patch) {
  columnSettings.value = columnSettings.value.map((c, i) => {
    if (i !== index) return c;
    const next = { ...c, ...patch };
    if (next.attributeId === "email") next.include = true;
    return next;
  });
}

// ── Transfer mode handlers ─────────────────────────────────────────────────────

async function fetchSourceRegistrants() {
  if (!sourceSessionId.value.trim()) {
    errorMessage.value = "Enter a source session ID.";
    return;
  }
  if (!isAuthenticated.value) {
    errorMessage.value = "Please connect your Livestorm account first.";
    return;
  }
  resetMessages();
  isSourceLoading.value = true;
  transferData.value = null;
  transferExcludedRows.value = {};
  transferIncludedFields.value = [];

  try {
    const response = await fetch("/api/session-people", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sourceSessionId.value.trim() }),
    });
    const data = await readApiResponse(
      response,
      "Failed to fetch registrants. The server returned an empty or invalid response.",
    );
    if (!response.ok) throw new Error(data.detail || "Failed to fetch registrants.");
    transferData.value = data;
    transferIncludedFields.value = [...data.headers];
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isSourceLoading.value = false;
  }
}

function toggleTransferField(fieldId) {
  if (fieldId === "email") return;
  const idx = transferIncludedFields.value.indexOf(fieldId);
  transferIncludedFields.value =
    idx >= 0
      ? transferIncludedFields.value.filter((f) => f !== fieldId)
      : [...transferIncludedFields.value, fieldId];
}

function removeTransferRow(index) {
  transferExcludedRows.value = { ...transferExcludedRows.value, [index]: true };
}

function restoreTransferRow(index) {
  const next = { ...transferExcludedRows.value };
  delete next[index];
  transferExcludedRows.value = next;
}

// ── Job lifecycle ──────────────────────────────────────────────────────────────

function attachRowResults(tasks, job) {
  const sourceRows = job?.row_results?.length ? job.row_results : rowResults.value;
  return tasks.map((task, index) => ({
    ...task,
    row_result: sourceRows[index] || {
      row_number: (job?.row_start || 2) + index,
      email: "",
      fields: [],
    },
  }));
}

async function pollJobUntilFinished(job) {
  while (!["ended", "failed", "completed"].includes(String(job.status).toLowerCase())) {
    const response = await fetch("/api/job-status", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: job.session_id, job_id: job.job_id }),
    });
    const data = await readApiResponse(
      response,
      "Failed to fetch job status. The server returned an empty or invalid response.",
    );

    if (!response.ok) {
      const detail = data.detail || "Failed to fetch job status";
      if (String(detail).toLowerCase().includes("throttle limit")) {
        job.error = "Livestorm is rate limiting status checks. StormBatch will keep waiting and try again.";
        await wait(JOB_STATUS_POLL_INTERVAL_MS);
        continue;
      }
      job.status = "failed";
      job.error = detail;
      return;
    }

    job.status = data.status;
    job.tasks = attachRowResults(data.tasks || [], job);
    job.raw = data.raw || {};
    job.warning = data.tasks_error
      ? "Livestorm confirmed this job, but row-level details are temporarily unavailable."
      : "";
    job.error = "";
    if (!["ended", "failed", "completed"].includes(String(job.status).toLowerCase())) {
      await wait(JOB_STATUS_POLL_INTERVAL_MS);
    }
  }
}

async function retryFailedRows(job) {
  const failedRegistrants = failedJobTasks(job)
    .map((t) => t.row_result)
    .filter((r) => r?.email);

  if (!failedRegistrants.length) {
    job.error = "No failed row details were available to retry with single registration.";
    return;
  }

  retryingSessions.value = { ...retryingSessions.value, [job.session_id]: true };

  try {
    const response = await fetch("/api/retry-failed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: job.session_id, registrants: failedRegistrants }),
    });
    const data = await readApiResponse(
      response,
      "Retry failed. The server returned an empty or invalid response.",
    );
    if (!response.ok) throw new Error(data.detail || "Retry failed");
    job.retry_results = data.results || [];
  } catch (error) {
    job.error = error.message;
  } finally {
    retryingSessions.value = { ...retryingSessions.value, [job.session_id]: false };
  }
}

// ── Submit ─────────────────────────────────────────────────────────────────────

function handleSubmit() {
  if (sourceMode.value === "upload") submitRegistration();
  else submitTransfer();
}

async function submitRegistration() {
  resetMessages();
  if (!selectedFile.value) { errorMessage.value = "Please upload an .xlsx or .csv file."; return; }
  if (!preview.value) { errorMessage.value = "Preview the file before submitting."; return; }
  if (!parsedSessionIds.value.length) { errorMessage.value = "Session IDs must not be empty."; return; }
  if (!hasEmailColumn.value) { errorMessage.value = "The file must include an Email column."; return; }
  const includedIds = Object.values(autoMapping.value);
  if (!includedIds.includes("email")) { errorMessage.value = "The Email column must be included."; return; }
  if (includedIds.some((id) => !id)) { errorMessage.value = "Included columns must have a Livestorm field ID."; return; }
  if (new Set(includedIds).size !== includedIds.length) {
    errorMessage.value = "Included columns cannot use the same Livestorm field ID twice.";
    return;
  }
  if (hasInvalidIncludedMappings.value) {
    errorMessage.value = "Some mapped field IDs are not valid for this session. Go back to Source and fix or disable the invalid columns.";
    return;
  }
  if (!isAuthenticated.value) { errorMessage.value = "Please connect your Livestorm account first."; return; }

  isSubmitting.value = true;
  jobs.value = [];
  hasSubmittedJobs.value = false;
  totalSessionCount.value = expectedJobCount.value;
  createdSessionCount.value = 0;

  try {
    for (const sessionId of parsedSessionIds.value) {
      const expectedChunks = Math.max(
        1,
        Math.ceil(preview.value.row_count / BULK_JOB_CHUNK_SIZE),
      );
      for (let chunkIndex = 1; chunkIndex <= expectedChunks; chunkIndex++) {
        const formData = new FormData();
        formData.append("session_ids", sessionId);
        formData.append("mapping", JSON.stringify(autoMapping.value));
        formData.append("chunk_index", String(chunkIndex));
        formData.append("chunk_size", String(BULK_JOB_CHUNK_SIZE));
        formData.append("file", selectedFile.value);

        const response = await fetch("/api/register", { method: "POST", body: formData });
        const data = await readApiResponse(
          response,
          "Registration failed. The server returned an empty or invalid response.",
        );

        if (!response.ok) {
          jobs.value.push({
            session_id: sessionId,
            job_id: `not-created-${chunkIndex}`,
            status: "failed",
            chunk_index: chunkIndex,
            chunk_count: expectedChunks,
            row_start: (chunkIndex - 1) * BULK_JOB_CHUNK_SIZE + 2,
            row_count: Math.min(
              BULK_JOB_CHUNK_SIZE,
              preview.value.row_count - (chunkIndex - 1) * BULK_JOB_CHUNK_SIZE,
            ),
            row_results: rowResults.value,
            tasks: [],
            raw: {},
            warning: "",
            error: data.detail || "Registration failed",
          });
          createdSessionCount.value += 1;
          continue;
        }

        if (!rowResults.value.length) rowResults.value = data.row_results || [];
        duplicateEmails.value = data.duplicate_emails || [];

        for (const createdJob of data.jobs || []) {
          const job = {
            ...createdJob,
            row_results: createdJob.row_results || [],
            tasks: [],
            raw: {},
            warning: "",
            error: "",
          };
          jobs.value.push(job);
          await pollJobUntilFinished(job);
          createdSessionCount.value += 1;
        }
      }
    }

    hasSubmittedJobs.value = true;
    successMessage.value = duplicateEmails.value.length
      ? "Batch finished. Duplicate emails were detected in the file, so Livestorm may reject some rows."
      : "Batch finished.";
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isSubmitting.value = false;
  }
}

async function submitTransfer() {
  resetMessages();
  if (!transferData.value) { errorMessage.value = "Fetch registrants from a source session first."; return; }
  if (!transferActiveRows.value.length) { errorMessage.value = "No registrants to transfer — all rows have been removed."; return; }
  if (!transferIncludedFields.value.includes("email")) { errorMessage.value = "Email field must be included."; return; }
  if (!parsedSessionIds.value.length) { errorMessage.value = "Enter at least one target session ID."; return; }
  if (!isAuthenticated.value) { errorMessage.value = "Please connect your Livestorm account first."; return; }

  const rows = transferActiveRows.value;
  const chunks = [];
  for (let i = 0; i < rows.length; i += BULK_JOB_CHUNK_SIZE) {
    chunks.push(rows.slice(i, i + BULK_JOB_CHUNK_SIZE));
  }

  isSubmitting.value = true;
  jobs.value = [];
  hasSubmittedJobs.value = false;
  totalSessionCount.value = parsedSessionIds.value.length * chunks.length;
  createdSessionCount.value = 0;

  try {
    for (const sessionId of parsedSessionIds.value) {
      for (let ci = 0; ci < chunks.length; ci++) {
        const response = await fetch("/api/transfer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_session_ids: [sessionId],
            rows: chunks[ci],
            included_fields: transferIncludedFields.value,
          }),
        });
        const data = await readApiResponse(
          response,
          "Transfer failed. The server returned an empty or invalid response.",
        );

        if (!response.ok) {
          jobs.value.push({
            session_id: sessionId,
            job_id: `not-created-transfer-${ci + 1}`,
            status: "failed",
            chunk_index: ci + 1,
            chunk_count: chunks.length,
            row_start: ci * BULK_JOB_CHUNK_SIZE + 2,
            row_count: chunks[ci].length,
            row_results: [],
            tasks: [],
            raw: {},
            warning: "",
            error: data.detail || "Transfer failed",
          });
          createdSessionCount.value += 1;
          continue;
        }

        for (const createdJob of data.jobs || []) {
          const job = {
            ...createdJob,
            row_results: createdJob.row_results || [],
            tasks: [],
            raw: {},
            warning: "",
            error: "",
          };
          jobs.value.push(job);
          await pollJobUntilFinished(job);
          createdSessionCount.value += 1;
        }
      }
    }

    hasSubmittedJobs.value = true;
    successMessage.value = "Transfer complete.";
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isSubmitting.value = false;
  }
}

// ── Reset ──────────────────────────────────────────────────────────────────────

function startNewBatch() {
  sessionIds.value = [];
  selectedFile.value = null;
  preview.value = null;
  columnSettings.value = [];
  duplicateEmails.value = [];
  sourceSessionId.value = "";
  transferData.value = null;
  transferExcludedRows.value = {};
  transferIncludedFields.value = [];
  isSourceLoading.value = false;
  jobs.value = [];
  rowResults.value = [];
  hasSubmittedJobs.value = false;
  retryingSessions.value = {};
  totalSessionCount.value = 0;
  createdSessionCount.value = 0;
  isSubmitting.value = false;
  isPreviewLoading.value = false;
  resetMessages();
  resetSessionFieldsState();
  currentStep.value = 2;
}

watch(
  () => parsedSessionIds.value[0],
  (newId) => {
    if (newId && sourceMode.value === "upload" && preview.value) {
      validateSessionFields();
    } else if (!newId) {
      resetSessionFieldsState();
    }
  },
);
</script>

<template>

  <!-- ── App bar ───────────────────────────────────────────────────────────── -->

  <header class="app-bar">
    <div class="app-bar-brand">
      <img :src="livestormIcon" alt="Livestorm" class="app-bar-logo" />
      <span class="app-bar-sep"></span>
      <span class="app-bar-name">StormBatch</span>
      <span class="app-bar-beta">Beta</span>
    </div>
    <div class="app-bar-auth">
      <span v-if="isAuthLoading" class="auth-status-text">Connecting…</span>
      <template v-else-if="isAuthenticated">
        <button class="bar-btn" type="button" @click="handleLogout">Disconnect</button>
      </template>
    </div>
  </header>

  <main class="page-shell">

    <!-- ── Step track (navigation) ──────────────────────────────────────────── -->

    <div class="step-track">
      <div class="step-item" :class="{ active: currentStep === 1, done: isAuthenticated }">
        <div class="step-circ">
          <svg v-if="isAuthenticated" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <span v-else>1</span>
        </div>
        <span class="step-lbl">Connect</span>
      </div>
      <div class="step-conn" :class="{ done: isAuthenticated }"></div>
      <div
        class="step-item"
        :class="{ active: currentStep === 2, done: currentStep === 3, locked: !isAuthenticated, 'can-navigate': isAuthenticated }"
        @click="goToStep(2)"
      >
        <div class="step-circ">
          <svg v-if="currentStep === 3" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <span v-else>2</span>
        </div>
        <span class="step-lbl">Source</span>
      </div>
      <div class="step-conn" :class="{ done: currentStep === 3 }"></div>
      <div
        class="step-item"
        :class="{ active: currentStep === 3, locked: !isAuthenticated || !sourceReady, 'can-navigate': isAuthenticated && sourceReady }"
        @click="goToStep(3)"
      >
        <div class="step-circ">
          <span>3</span>
        </div>
        <span class="step-lbl">Target</span>
      </div>
    </div>

    <!-- ── Step 1: Onboarding (not connected) ────────────────────────────────── -->

    <div v-if="!isAuthenticated && !isAuthLoading" class="onboarding-state">
      <div class="onboarding-card">
        <div class="onboarding-brand">
          <img :src="livestormIcon" alt="Livestorm" class="onboarding-logo" />
          <span class="onboarding-brand-sep"></span>
          <span class="onboarding-brand-name">StormBatch</span>
        </div>
        <h2 class="onboarding-title">Batch register Livestorm attendees</h2>
        <p class="onboarding-desc">
          Upload a spreadsheet or pull registrants from an existing session,
          then push them to any number of Livestorm sessions at once.
        </p>
        <ul class="onboarding-features">
          <li>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
            Upload .xlsx or .csv files
          </li>
          <li>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
            Transfer registrants between sessions
          </li>
          <li>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
            Register to multiple target sessions at once
          </li>
        </ul>
        <button class="primary-button onboarding-cta" type="button" @click="handleLogin">
          <img :src="livestormIcon" alt="" class="bar-btn-icon" />
          Connect with Livestorm
        </button>
      </div>
    </div>

    <!-- ── Step 2: Source ─────────────────────────────────────────────────────── -->

    <template v-else-if="isAuthenticated && currentStep === 2">

      <div class="panel source-panel">
        <h2 class="step-heading">Choose source</h2>

        <div class="mode-toggle" role="group" aria-label="Source type">
          <button :class="['mode-btn', { active: sourceMode === 'upload' }]" type="button" @click="setSourceMode('upload')">Upload file</button>
          <button :class="['mode-btn', { active: sourceMode === 'transfer' }]" type="button" @click="setSourceMode('transfer')">Transfer from session</button>
        </div>

        <FileUpload
          v-if="sourceMode === 'upload'"
          :selected-file="selectedFile"
          :loading="isPreviewLoading"
          :preview-ready="Boolean(preview)"
          @file-selected="onFileSelected"
          @preview="loadPreview"
        />
        <SourceSessionInput
          v-else
          v-model="sourceSessionId"
          :loading="isSourceLoading"
          :fetched-count="transferData ? transferData.total : null"
          @fetch="fetchSourceRegistrants"
        />
      </div>

      <section v-if="errorMessage" class="notice error centered-notice">{{ errorMessage }}</section>

      <!-- Upload: column mapping + preview table -->
      <section v-if="sourceMode === 'upload' && preview" class="panel preview-panel">
        <div class="panel-header">
          <div>
            <span class="step-label">Preview</span>
            <h2>Preview registrants</h2>
            <p>{{ preview.row_count }} rows · {{ preview.headers.length }} columns</p>
          </div>
          <div class="preview-statuses">
            <div class="status-pill" :class="{ ok: hasEmailColumn, error: !hasEmailColumn }">
              {{ hasEmailColumn ? "Email detected" : "Email column missing" }}
            </div>
            <div v-if="duplicateEmails.length" class="warning-pill">
              Duplicate emails: {{ duplicateEmails.join(", ") }}
            </div>
          </div>
        </div>
        <div class="attribute-preview">
          <div v-for="(item, index) in mappedAttributePreview" :key="item.column" class="column-card" :class="{ included: item.include }">
            <div>
              <strong>{{ item.column }}</strong>
              <span>{{ item.required ? "Required email field" : "Optional field" }}</span>
            </div>
            <div class="column-actions">
              <label class="include-toggle" :class="{ disabled: item.required }">
                <input type="checkbox" :checked="item.include" :disabled="item.required" @change="updateColumnSetting(index, { include: $event.target.checked })" />
                <span class="toggle-track"><span class="toggle-thumb"></span></span>
              </label>
              <strong class="toggle-label">{{ item.include ? "Send" : "Drop" }}</strong>
            </div>
            <input :value="item.attributeId" :disabled="!item.include || item.required" placeholder="Livestorm field ID" @input="updateColumnSetting(index, { attributeId: $event.target.value })" />
          </div>
        </div>
        <PreviewTable :headers="preview.headers" :rows="preview.preview_rows" />
      </section>

      <!-- Transfer: registrant editor -->
      <section v-if="sourceMode === 'transfer' && transferData" class="panel preview-panel">
        <div class="panel-header">
          <div>
            <span class="step-label">Registrants</span>
            <h2>{{ transferData.total }} registrants</h2>
            <p class="source-session-id">from session {{ transferData.session_id }}</p>
          </div>
          <div class="preview-statuses">
            <div class="status-pill ok">{{ transferActiveRows.length }} included</div>
            <div v-if="transferExcludedCount" class="status-pill error">{{ transferExcludedCount }} removed</div>
          </div>
        </div>
        <div class="field-toggles-section">
          <span class="field-toggles-label">Columns to transfer</span>
          <div class="attribute-preview">
            <div v-for="field in transferData.headers" :key="field" class="column-card" :class="{ included: transferIncludedFields.includes(field) }">
              <div>
                <strong>{{ field }}</strong>
                <span>{{ field === 'email' ? 'Required' : 'Optional' }}</span>
              </div>
              <div class="column-actions">
                <label class="include-toggle" :class="{ disabled: field === 'email' }">
                  <input type="checkbox" :checked="transferIncludedFields.includes(field)" :disabled="field === 'email'" @change="toggleTransferField(field)" />
                  <span class="toggle-track"><span class="toggle-thumb"></span></span>
                </label>
                <strong class="toggle-label">{{ transferIncludedFields.includes(field) ? "Send" : "Drop" }}</strong>
              </div>
            </div>
          </div>
        </div>
        <div class="registrant-table-wrap">
          <table class="registrant-table">
            <thead>
              <tr>
                <th class="action-th"></th>
                <th v-for="field in transferIncludedFields" :key="field">{{ field }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in transferData.rows" :key="index" :class="{ 'row-removed': transferExcludedRows[index] }">
                <td class="action-td">
                  <button v-if="!transferExcludedRows[index]" class="row-action-btn remove" type="button" title="Remove this registrant" @click="removeTransferRow(index)">✕</button>
                  <button v-else class="row-action-btn restore" type="button" title="Restore this registrant" @click="restoreTransferRow(index)">↩</button>
                </td>
                <td v-for="field in transferIncludedFields" :key="field">{{ row[field] || "" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Next button -->
      <div v-if="sourceReady" class="step-nav">
        <button class="primary-button step-next-btn" type="button" @click="goToStep(3)">
          Next: Set target sessions →
        </button>
      </div>

    </template>

    <!-- ── Step 3: Target ─────────────────────────────────────────────────────── -->

    <template v-else-if="isAuthenticated && currentStep === 3">

      <button class="back-btn" type="button" @click="goToStep(2)">
        ← Back to source
      </button>

      <div class="panel target-panel">
        <h2 class="step-heading">Target sessions</h2>
        <SessionIdsInput v-model="sessionIds" />
      </div>

      <!-- ── Attribute Mapping Check (upload mode only) ──────────────────────── -->

      <section v-if="sourceMode === 'upload' && preview" class="panel mapping-check-panel">
        <div class="panel-header">
          <div>
            <span class="step-label">Attribute Mapping Check</span>
            <h2>Field compatibility</h2>
            <p v-if="sessionFieldsState.loading">Checking field compatibility…</p>
            <p v-else-if="!parsedSessionIds.length">Enter a target session ID above to validate your field mapping.</p>
            <p v-else-if="sessionFieldsState.validated && sessionFieldsState.hasPeople">
              Validated against session <code class="inline-code">{{ sessionFieldsState.sessionId }}</code>
            </p>
            <p v-else-if="sessionFieldsState.validated && !sessionFieldsState.hasPeople">No registrants found — field names could not be auto-checked.</p>
            <p v-else>Validate your column names match the session's registration form fields.</p>
          </div>
          <button
            class="bar-btn"
            type="button"
            :disabled="!parsedSessionIds.length || sessionFieldsState.loading"
            @click="validateSessionFields">
            {{ sessionFieldsState.loading ? 'Checking…' : sessionFieldsState.validated ? 'Re-check' : 'Check fields' }}
          </button>
        </div>

        <div v-if="sessionFieldsState.error" class="notice error" style="margin-bottom: 0">{{ sessionFieldsState.error }}</div>

        <div v-if="sessionFieldsState.validated && !sessionFieldsState.hasPeople" class="notice warning" style="margin-bottom: 0">
          No registrants found in session <code>{{ sessionFieldsState.sessionId }}</code>.
          Field names could not be auto-validated — ensure your column IDs use underscore separators (e.g., <code>first_name</code>, <code>last_name</code>).
        </div>

        <template v-if="sessionFieldsState.validated && sessionFieldsState.hasPeople">
          <div class="mapping-check-list">
            <div
              v-for="(item, idx) in columnSettings"
              :key="item.column"
              class="mapping-check-row"
              :class="{
                'check-valid': item.include && (item.attributeId === 'email' || validFieldIds.has(item.attributeId)),
                'check-invalid': item.include && item.attributeId !== 'email' && !validFieldIds.has(item.attributeId),
                'check-dropped': !item.include,
              }">
              <span class="check-icon">
                <svg v-if="item.include && (item.attributeId === 'email' || validFieldIds.has(item.attributeId))" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                <svg v-else-if="item.include" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/></svg>
              </span>
              <span class="check-column">{{ item.column }}</span>
              <span class="check-arrow">→</span>
              <input
                v-if="item.attributeId !== 'email'"
                class="check-attr-input"
                :value="item.attributeId"
                placeholder="field_id"
                :title="!item.include ? 'Edit to correct the slug and re-enable this field' : 'Edit field ID'"
                @change="onCheckAttrChange(idx, $event.target.value)"
              />
              <code v-else class="check-attr">{{ item.attributeId }}</code>
              <span class="check-status">
                <template v-if="!item.include">Dropped — edit to fix</template>
                <template v-else-if="item.attributeId === 'email'">Required</template>
                <template v-else-if="validFieldIds.has(item.attributeId)">Valid</template>
                <template v-else>Invalid — auto-disabled</template>
              </span>
            </div>
          </div>

          <div class="available-fields-block">
            <span class="available-fields-label">Fields available in this session</span>
            <div class="available-fields-list">
              <span
                v-for="field in sessionFieldsState.fields"
                :key="field.id"
                class="session-field-chip"
                :class="{
                  'chip-required': field.required,
                  'chip-mapped': isFieldMapped(field.id),
                }">
                {{ field.id }}<em v-if="field.required"> · req.</em>
              </span>
            </div>
          </div>
        </template>
      </section>

      <section v-if="errorMessage" class="notice error centered-notice">{{ errorMessage }}</section>
      <section v-if="successMessage" class="notice success centered-notice">{{ successMessage }}</section>

      <section v-if="isReadyToSubmit" class="cta-card">
        <div>
          <h2>Ready to register?</h2>
          <p v-if="sourceMode === 'upload'">
            This will create {{ expectedJobCount }} Livestorm job(s) in batches of {{ BULK_JOB_CHUNK_SIZE }} registrants or fewer.
          </p>
          <p v-else>
            {{ transferActiveRows.length }} registrant(s) will be transferred to {{ parsedSessionIds.length }} session(s) in batches of {{ BULK_JOB_CHUNK_SIZE }}.
          </p>
          <p v-if="hasInvalidIncludedMappings" class="invalid-mapping-warning">
            Some columns are mapped to unknown field IDs. Go back to source and fix or disable them before registering.
          </p>
        </div>
        <div class="cta-actions">
          <button class="primary-button" :disabled="isSubmitting || isPollingJobs || !canSubmit" @click="handleSubmit">
            {{ isSubmitting ? (sourceMode === "transfer" ? "Transferring…" : "Creating jobs…") : (sourceMode === "transfer" ? "Transfer now" : "Batch register now") }}
          </button>
        </div>
      </section>

      <section v-if="jobs.length || isSubmitting" class="panel progress-panel">
        <div class="panel-header">
          <div>
            <span class="step-label">Job progress</span>
            <h2>{{ progressTitle }}</h2>
            <p>{{ progressMessage }}</p>
          </div>
          <strong class="progress-percent">{{ progressPercent }}%</strong>
        </div>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${progressPercent}%` }"></div>
        </div>
      </section>

      <section v-if="hasSubmittedJobs && !isPollingJobs && jobs.length" class="confirmation-card" :class="{ failed: registrationSummary.failedJobs }">
        <div class="confirmation-icon">
          <svg v-if="!registrationSummary.failedJobs" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        </div>
        <div>
          <h2>{{ completionTitle }}</h2>
          <p>{{ completionMessage }}</p>
        </div>
        <button class="new-batch-button" type="button" @click="startNewBatch">New Batch</button>
      </section>

      <section v-if="visibleResultJobs.length" class="panel">
        <div class="panel-header results-header">
          <div>
            <span class="step-label">Results</span>
            <h2>Rows needing attention</h2>
          </div>
        </div>
        <JobResults :jobs="visibleResultJobs" :retrying-sessions="retryingSessions" @retry-failed="retryFailedRows" />
      </section>

    </template>

    <!-- ── Beta notice footer ──────────────────────────────────────────────── -->

    <div class="beta-notice">
      <span class="beta-notice-chip">Beta</span>
      Early-access helper, not an official Livestorm product.
      <button class="beta-notice-link" type="button" @click="showBetaInfo = true">Read more</button>
    </div>

  </main>

  <BetaInfoModal v-if="showBetaInfo" @close="showBetaInfo = false" />
</template>

<style>
/* ── Viewport lock ────────────────────────────────── */

html,
body {
  height: 100%;
  overflow: hidden;
}

#app {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* ── App bar ──────────────────────────────────────── */

.app-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 56px;
  background: var(--color-surface-neutral-100);
  border-bottom: 1px solid var(--color-borders-neutral-light);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18);
}

.app-bar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-bar-logo {
  width: 22px;
  height: 22px;
  object-fit: contain;
  flex-shrink: 0;
}

.app-bar-sep {
  display: block;
  width: 1px;
  height: 16px;
  background: var(--color-borders-neutral-light);
  flex-shrink: 0;
}

.app-bar-name {
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.app-bar-auth {
  display: flex;
  align-items: center;
  gap: 10px;
}

.auth-status-text {
  font-size: var(--text-content-legends-regular-md);
  color: var(--color-text-neutral-tertiary);
}

.auth-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 6px;
  background: var(--color-surface-success-300);
  border: 1px solid var(--color-borders-success-light);
  color: var(--color-text-success-secondary);
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.bar-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 7px;
  padding: 7px 14px;
  font-size: var(--text-content-text-bold-md);
  font-weight: var(--text-content-text-bold-md--font-weight);
  line-height: var(--text-content-text-bold-md--line-height);
  color: var(--color-text-neutral-secondary);
  background: transparent;
  border: 1px solid var(--color-borders-neutral-default);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.bar-btn:hover {
  background: var(--color-actions-neutral-hover-overlay);
  border-color: var(--color-borders-neutral-strong);
}

.bar-btn.primary {
  color: var(--color-text-neutral-complementary-base);
  background: var(--color-actions-primary-idle);
  border-color: transparent;
}

.bar-btn.primary:hover {
  background: var(--color-actions-primary-idle-alpha-strong);
  box-shadow: 0 0 0 1px var(--color-actions-primary-idle);
}

.bar-btn-icon {
  width: 16px;
  height: 16px;
  object-fit: contain;
}

/* ── Step track ───────────────────────────────────── */

.step-track {
  display: flex;
  align-items: flex-start;
  margin-bottom: 28px;
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
}

.step-circ {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid var(--color-borders-neutral-light);
  background: transparent;
  color: var(--color-text-neutral-tertiary);
  font-size: 13px;
  font-weight: 600;
  display: grid;
  place-items: center;
  transition: border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}

.step-item.active .step-circ {
  border-color: var(--color-actions-primary-idle);
  color: var(--color-actions-primary-idle);
  background: var(--color-actions-primary-idle-alpha-light);
}

.step-item.done .step-circ {
  border-color: var(--color-actions-success-idle);
  background: var(--color-actions-success-idle);
  color: #fff;
}

.step-lbl {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-text-neutral-tertiary);
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.step-item.active .step-lbl,
.step-item.done .step-lbl {
  color: var(--color-text-neutral-base);
}

.step-conn {
  flex: 1;
  height: 2px;
  background: var(--color-borders-neutral-light);
  margin-top: 15px;
  transition: background 0.25s ease;
}

.step-conn.done {
  background: var(--color-actions-success-idle);
}

/* ── Shell ────────────────────────────────────────── */

.page-shell {
  flex: 1;
  max-width: 1180px;
  width: 100%;
  margin: 0 auto;
  padding: 32px 20px 64px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* ── Steps grid ───────────────────────────────────── */

.steps-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 20px;
  align-items: start;
  margin-bottom: 24px;
}

/* ── Panels ───────────────────────────────────────── */

.panel {
  background: var(--color-surface-neutral-200);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.step-panel {
  margin-bottom: 0;
}

.preview-panel {
  border-color: var(--color-borders-neutral-default);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.panel-header h2,
.cta-card h2,
.confirmation-card h2 {
  margin: 0 0 6px;
  color: var(--color-text-neutral-base);
  font-size: var(--text-title-md);
  line-height: var(--text-title-md--line-height);
  letter-spacing: var(--text-title-md--letter-spacing);
  font-weight: var(--text-title-md--font-weight);
}

.panel-header p,
.confirmation-card p {
  margin: 0;
  color: var(--color-text-neutral-secondary);
}

/* ── Step heading ─────────────────────────────────── */

.step-heading {
  margin: 0 0 16px;
  color: var(--color-text-neutral-base);
  font-size: var(--text-title-sm, 16px);
  font-weight: 600;
}

/* ── Step labels ──────────────────────────────────── */

.step-label {
  display: inline-flex;
  width: fit-content;
  margin-bottom: 16px;
  color: var(--color-actions-primary-idle);
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1px solid var(--color-borders-primary-light);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  letter-spacing: 0.04em;
}

/* ── Mode toggle ──────────────────────────────────── */

.mode-toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px;
  padding: 3px;
  border-radius: 10px;
  background: var(--color-surface-neutral-300);
  margin-bottom: 16px;
}

.mode-btn {
  border-radius: 7px;
  padding: 8px 10px;
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
  color: var(--color-text-neutral-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
  white-space: nowrap;
  text-align: center;
}

.mode-btn.active {
  background: var(--color-surface-neutral-100);
  color: var(--color-text-neutral-base);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

/* ── Notices ──────────────────────────────────────── */

.notice {
  margin-top: 4px;
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 10px;
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
}

.notice.error {
  background: var(--color-surface-danger-300);
  color: var(--color-text-danger-secondary);
  border: 1px solid var(--color-borders-danger-light);
}

.notice.success {
  background: var(--color-surface-success-300);
  color: var(--color-text-success-secondary);
  border: 1px solid var(--color-borders-success-light);
}

.warning-pill {
  background: var(--color-surface-warning-300);
  color: var(--color-text-warning-secondary);
  border: 1px solid var(--color-borders-warning-light);
  padding: 8px 12px;
  border-radius: 8px;
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
}

.preview-statuses {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.status-pill.ok {
  color: var(--color-text-neutral-secondary);
  background: transparent;
  border: 1px solid var(--color-borders-neutral-light);
}

.status-pill.error {
  color: var(--color-text-danger-secondary);
  background: var(--color-surface-danger-300);
  border: 1px solid var(--color-borders-danger-light);
}

/* ── Column mapping ───────────────────────────────── */

.attribute-preview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.column-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 10px;
  background: var(--color-surface-neutral-100);
  transition: border-color 0.15s ease;
}

.column-card.included {
  border-color: var(--color-borders-success-light);
  background: var(--color-surface-success-300);
}

.column-card > div:first-child strong,
.column-card > div:first-child span {
  display: block;
}

.column-card > div:first-child span {
  margin-top: 3px;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.column-card input[type="text"],
.column-card > input {
  width: 100%;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--color-text-neutral-base);
  background: var(--color-surface-neutral-100);
  transition: border-color 0.15s ease;
}

.column-card > input:focus {
  border-color: var(--color-borders-primary-strong);
  outline: none;
}

.column-card > input:disabled {
  color: var(--color-text-neutral-tertiary);
  background: var(--color-surface-neutral-200);
}

/* ── Toggle switch ────────────────────────────────── */

.column-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 34px;
}

.include-toggle {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  cursor: pointer;
}

.include-toggle.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.include-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.toggle-track {
  display: inline-flex;
  align-items: center;
  width: 44px;
  height: 26px;
  padding: 3px;
  border-radius: 13px;
  background: var(--color-surface-neutral-300);
  transition: background 0.2s ease;
}

.toggle-label {
  line-height: 1;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-md);
}

.toggle-thumb {
  width: 20px;
  height: 20px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.6);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  transition: transform 0.2s ease, background 0.2s ease;
}

.include-toggle input:checked + .toggle-track {
  background: var(--color-actions-success-idle);
}

.include-toggle input:checked + .toggle-track .toggle-thumb {
  transform: translateX(18px);
  background: #ffffff;
}

.include-toggle input:focus-visible + .toggle-track {
  outline: 3px solid var(--color-focus-ring);
  outline-offset: 2px;
}

/* ── Transfer: field toggles section ─────────────── */

.field-toggles-section {
  margin-bottom: 20px;
}

.field-toggles-label {
  display: block;
  margin-bottom: 10px;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.source-session-id {
  font-size: var(--text-content-legends-regular-md);
  word-break: break-all;
}

/* ── Transfer: registrant table ───────────────────── */

.registrant-table-wrap {
  overflow-x: auto;
  overflow-y: auto;
  max-height: 480px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 10px;
}

.registrant-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-content-text-regular-md, 14px);
}

.registrant-table thead {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-surface-neutral-200);
}

.registrant-table th {
  padding: 10px 14px;
  text-align: left;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  border-bottom: 1px solid var(--color-borders-neutral-light);
  white-space: nowrap;
}

.registrant-table td {
  padding: 9px 14px;
  color: var(--color-text-neutral-base);
  border-bottom: 1px solid var(--color-borders-neutral-light);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.registrant-table tbody tr:last-child td {
  border-bottom: none;
}

.registrant-table tbody tr:hover:not(.row-removed) {
  background: var(--color-actions-neutral-hover-overlay);
}

.registrant-table tbody tr.row-removed {
  opacity: 0.35;
}

.action-th,
.action-td {
  width: 36px;
  min-width: 36px;
  padding: 6px 8px !important;
}

.row-action-btn {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 12px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.12s ease, border-color 0.12s ease;
}

.row-action-btn.remove {
  color: var(--color-text-danger-secondary);
  background: transparent;
}

.row-action-btn.remove:hover {
  background: var(--color-surface-danger-300);
  border-color: var(--color-borders-danger-light);
}

.row-action-btn.restore {
  color: var(--color-text-primary-base);
  background: transparent;
}

.row-action-btn.restore:hover {
  background: var(--color-surface-primary-100);
  border-color: var(--color-borders-primary-light);
}

/* ── CTA card ─────────────────────────────────────── */

.cta-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 18px;
  align-items: center;
  margin-bottom: 20px;
  background: var(--color-surface-neutral-200);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 12px;
  padding: 22px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.cta-card p {
  margin: 6px 0 0;
  color: var(--color-text-neutral-secondary);
}

/* ── Buttons ──────────────────────────────────────── */

.primary-button {
  width: 100%;
  border-radius: 8px;
  padding: 14px 18px;
  font-size: var(--text-action-button-lg);
  line-height: var(--text-action-button-lg--line-height);
  letter-spacing: var(--text-action-button-lg--letter-spacing);
  font-weight: var(--text-action-button-lg--font-weight);
  color: var(--color-text-neutral-complementary-base);
  background: var(--color-actions-primary-idle);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
}

.primary-button:hover:not(:disabled) {
  background: var(--color-actions-primary-idle-alpha-strong);
  box-shadow: 0 0 0 1px var(--color-actions-primary-idle);
}

.primary-button:active:not(:disabled) {
  transform: translateY(1px);
}

.primary-button:disabled {
  color: var(--color-text-neutral-tertiary);
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  cursor: not-allowed;
}

/* ── Progress ─────────────────────────────────────── */

.progress-panel {
  border-color: var(--color-borders-primary-light);
}

.progress-percent {
  font-size: var(--text-title-lg);
  line-height: var(--text-title-lg--line-height);
  color: var(--color-text-primary-base);
  font-variant-numeric: tabular-nums;
}

.progress-track {
  height: 8px;
  overflow: hidden;
  border-radius: 99px;
  background: var(--color-surface-neutral-300);
}

.progress-fill {
  height: 100%;
  min-width: 8px;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--color-actions-primary-idle) 0%, #7ba2fe 100%);
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}

/* ── Confirmation card ────────────────────────────── */

.confirmation-card {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding: 20px 24px;
  border-radius: 12px;
  border: 1px solid var(--color-borders-success-light);
  background: var(--color-surface-success-300);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.confirmation-card.failed {
  border-color: var(--color-borders-danger-light);
  background: var(--color-surface-danger-300);
}

.confirmation-icon {
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: var(--color-actions-success-idle);
  color: var(--color-text-neutral-complementary-base);
  flex-shrink: 0;
}

.confirmation-card.failed .confirmation-icon {
  background: var(--color-actions-danger-idle);
}

/* ── New batch button ─────────────────────────────── */

.new-batch-button {
  flex: 0 0 auto;
  border: 1px solid var(--color-borders-neutral-default);
  border-radius: 8px;
  padding: 10px 16px;
  color: var(--color-text-neutral-base);
  background: transparent;
  font-size: var(--text-action-button-md);
  line-height: var(--text-action-button-md--line-height);
  font-weight: var(--text-action-button-md--font-weight);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.new-batch-button:hover {
  background: var(--color-actions-neutral-hover-overlay);
  border-color: var(--color-borders-neutral-strong);
}

.results-header {
  margin-bottom: 14px;
}

/* ── User profile badge ───────────────────────────── */

.user-badge {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1.5px solid var(--color-borders-primary-light);
  display: grid;
  place-items: center;
  overflow: hidden;
  flex-shrink: 0;
}

.user-avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-initials {
  font-size: 11px;
  font-weight: 700;
  color: var(--color-actions-primary-idle);
  letter-spacing: 0.03em;
  line-height: 1;
}

.user-name {
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  color: var(--color-text-neutral-secondary);
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Onboarding state ─────────────────────────────── */

.onboarding-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px 0;
}

.onboarding-card {
  width: 100%;
  max-width: 480px;
  background: var(--color-surface-neutral-200);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35);
  display: grid;
  gap: 20px;
}

.onboarding-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.onboarding-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.onboarding-brand-sep {
  display: block;
  width: 1px;
  height: 18px;
  background: var(--color-borders-neutral-light);
}

.onboarding-brand-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-neutral-secondary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.onboarding-title {
  margin: 0;
  font-size: var(--text-title-lg);
  line-height: var(--text-title-lg--line-height);
  font-weight: var(--text-title-lg--font-weight);
  color: var(--color-text-neutral-base);
}

.onboarding-desc {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  line-height: 1.6;
  font-size: var(--text-content-text-regular-md, 14px);
}

.onboarding-features {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 12px;
}

.onboarding-features li {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--text-content-text-regular-md, 14px);
  color: var(--color-text-neutral-secondary);
}

.onboarding-features li svg {
  color: var(--color-actions-success-idle);
  flex-shrink: 0;
}

.onboarding-cta {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: auto !important;
  padding: 12px 20px !important;
  margin-top: 4px;
}

/* ── Step locked state ────────────────────────────── */

.step-item.locked .step-circ {
  border-color: var(--color-borders-neutral-light);
  color: var(--color-text-neutral-tertiary);
  opacity: 0.4;
}

.step-item.locked .step-lbl {
  color: var(--color-text-neutral-tertiary);
  opacity: 0.4;
}

/* ── Slide-up transition ──────────────────────────── */

.slide-up-enter-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.slide-up-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(14px);
}

/* ── Source / target panel variants ──────────────── */

.source-panel,
.target-panel {
  max-width: 780px;
  margin-left: auto;
  margin-right: auto;
}

.centered-notice {
  max-width: 780px;
  margin-left: auto;
  margin-right: auto;
}

/* ── Step navigation buttons ──────────────────────── */

.step-nav {
  max-width: 780px;
  margin: 4px auto 0;
  display: flex;
  justify-content: flex-end;
}

.step-next-btn {
  width: auto !important;
  padding: 12px 28px !important;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0;
  margin-bottom: 12px;
  background: none;
  border: none;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-text-regular-md, 14px);
  cursor: pointer;
  transition: color 0.15s ease;
}

.back-btn:hover {
  color: var(--color-text-neutral-base);
}

/* ── Navigable step items ─────────────────────────── */

.step-item.can-navigate {
  cursor: pointer;
}

.step-item.can-navigate:hover:not(.active):not(.locked) .step-circ {
  border-color: var(--color-actions-primary-idle);
  color: var(--color-actions-primary-idle);
}

/* ── App bar beta chip ────────────────────────────── */

.app-bar-beta {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 5px;
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1px solid var(--color-borders-primary-light);
  color: var(--color-actions-primary-idle);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  line-height: 1;
}

/* ── Beta notice footer ───────────────────────────── */

.beta-notice {
  margin-top: auto;
  padding-top: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--color-text-neutral-tertiary);
  font-size: 12px;
  line-height: 1.5;
  text-align: center;
}

.beta-notice-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  color: var(--color-text-neutral-tertiary);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  flex-shrink: 0;
}

.beta-notice-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--color-actions-primary-idle);
  font-size: inherit;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: opacity 0.15s ease;
}

.beta-notice-link:hover {
  opacity: 0.75;
}

/* ── Responsive ───────────────────────────────────── */

@media (max-width: 800px) {
  .steps-grid,
  .cta-card {
    grid-template-columns: 1fr;
  }

  .app-bar {
    padding: 0 16px;
  }
}

@media (max-width: 540px) {
  .page-shell {
    padding: 20px 16px 40px;
  }

  .panel,
  .confirmation-card,
  .cta-card {
    padding: 16px;
  }

  .confirmation-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .step-track {
    margin-bottom: 20px;
  }
}

/* ── Attribute mapping check panel ─────────────────── */

.notice.warning {
  background: var(--color-surface-warning-300);
  color: var(--color-text-warning-secondary);
  border: 1px solid var(--color-borders-warning-light);
}

.inline-code {
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 0.85em;
  background: var(--color-surface-neutral-300);
  padding: 1px 5px;
  border-radius: 4px;
}

.mapping-check-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 20px;
}

.mapping-check-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid var(--color-borders-neutral-light);
  background: var(--color-surface-neutral-100);
  font-size: var(--text-content-text-regular-md, 14px);
}

.mapping-check-row.check-valid {
  border-color: var(--color-borders-success-light);
  background: var(--color-surface-success-300);
}

.mapping-check-row.check-invalid {
  border-color: var(--color-borders-danger-light);
  background: var(--color-surface-danger-300);
}

.mapping-check-row.check-dropped {
  opacity: 0.45;
}

.check-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  width: 16px;
}

.check-valid .check-icon { color: var(--color-actions-success-idle); }
.check-invalid .check-icon { color: var(--color-text-danger-secondary); }
.check-dropped .check-icon { color: var(--color-text-neutral-tertiary); }

.check-column {
  font-weight: 600;
  color: var(--color-text-neutral-base);
  min-width: 80px;
  flex-shrink: 0;
}

.check-arrow {
  color: var(--color-text-neutral-tertiary);
  flex-shrink: 0;
}

.check-attr {
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 0.875em;
  flex: 1;
  color: var(--color-text-neutral-base);
  word-break: break-all;
}

.check-attr-input {
  flex: 1;
  min-width: 0;
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 0.875em;
  color: var(--color-text-neutral-base);
  background: transparent;
  border: none;
  border-bottom: 1px dashed var(--color-borders-neutral-default);
  border-radius: 0;
  padding: 1px 2px;
  outline: none;
  word-break: break-all;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.check-attr-input:focus {
  border-bottom-color: var(--color-borders-primary-strong);
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px 4px 0 0;
}

.check-attr-input::placeholder {
  color: var(--color-text-neutral-tertiary);
  font-style: italic;
}

.check-invalid .check-attr-input {
  border-bottom-color: var(--color-borders-danger-light);
  color: var(--color-text-danger-secondary);
}

.check-dropped .check-attr-input {
  border-bottom-style: dashed;
  opacity: 1;
}

.check-status {
  font-size: var(--text-content-legends-regular-md);
  color: var(--color-text-neutral-secondary);
  flex-shrink: 0;
  text-align: right;
  white-space: nowrap;
}

.check-valid .check-status { color: var(--color-text-success-secondary); }
.check-invalid .check-status { color: var(--color-text-danger-secondary); font-weight: 600; }

/* ── Available session fields ─────────────────────── */

.available-fields-block {
  border-top: 1px solid var(--color-borders-neutral-light);
  padding-top: 16px;
  margin-top: 4px;
}

.available-fields-label {
  display: block;
  margin-bottom: 10px;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.available-fields-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.session-field-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 5px 10px;
  border-radius: 8px;
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 12px;
  color: var(--color-text-neutral-base);
}

.session-field-chip.chip-required {
  border-color: var(--color-borders-primary-light);
  background: var(--color-actions-primary-idle-alpha-light);
  color: var(--color-actions-primary-idle);
}

.session-field-chip.chip-mapped {
  border-color: var(--color-borders-success-light);
  background: var(--color-surface-success-300);
  color: var(--color-text-success-secondary);
}

.session-field-chip em {
  font-style: normal;
  opacity: 0.65;
  font-size: 10px;
}

/* ── Invalid mapping warning in CTA ─────────────────── */

.invalid-mapping-warning {
  margin-top: 8px !important;
  color: var(--color-text-danger-secondary) !important;
  font-size: var(--text-content-legends-regular-md) !important;
}
</style>
