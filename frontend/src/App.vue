<script setup>
import { computed, ref } from "vue";
import ApiKeyInput from "./components/ApiKeyInput.vue";
import FileUpload from "./components/FileUpload.vue";
import JobResults from "./components/JobResults.vue";
import PreviewTable from "./components/PreviewTable.vue";
import SessionIdsInput from "./components/SessionIdsInput.vue";
import livestormIcon from "../assets/Icon-Livestorm-Primary.png";

const BULK_JOB_CHUNK_SIZE = 50;
const JOB_STATUS_POLL_INTERVAL_MS = 5000;

const apiKey = ref("");
const sessionIds = ref("");
const selectedFile = ref(null);
const preview = ref(null);
const columnSettings = ref([]);
const jobs = ref([]);
const duplicateEmails = ref([]);
const errorMessage = ref("");
const successMessage = ref("");
const isPreviewLoading = ref(false);
const isSubmitting = ref(false);
const rowResults = ref([]);
const hasSubmittedJobs = ref(false);
const retryingSessions = ref({});
const totalSessionCount = ref(0);
const createdSessionCount = ref(0);

const parsedSessionIds = computed(() =>
  sessionIds.value
    .split(/[\n,]/)
    .map((value) => value.trim())
    .filter(Boolean),
);

const emailColumn = computed(() => {
  if (!preview.value) {
    return "";
  }
  return preview.value.headers.find(
    (header) => preview.value.normalized_headers[header] === "email",
  ) || "";
});

const hasEmailColumn = computed(() => Boolean(emailColumn.value));

const autoMapping = computed(() => {
  return Object.fromEntries(
    columnSettings.value
      .filter((column) => column.include)
      .map((column) => [column.column, column.attributeId.trim()]),
  );
});

const mappedAttributePreview = computed(() =>
  columnSettings.value.map((column) => ({
    ...column,
    required: column.attributeId === "email",
  })),
);

const finishedJobs = computed(() =>
  jobs.value.filter((job) =>
    ["ended", "failed", "completed"].includes(String(job.status).toLowerCase()),
  ).length,
);

function taskStatus(task) {
  return task?.attributes?.status || task?.status || "unknown";
}

function taskError(task) {
  const attributes = task?.attributes || {};
  const errors = attributes.errors || task?.errors;
  if (Array.isArray(errors)) {
    return errors
      .map((error) => error.detail || error.title || error.message || String(error))
      .join(", ");
  }
  return attributes.error || attributes.message || task?.error || task?.message || "";
}

function isAlreadyRegisteredMessage(message) {
  const normalized = String(message).toLowerCase();
  return normalized.includes("already been invited")
    || normalized.includes("already registered")
    || normalized.includes("identity has already been taken");
}

function failedJobTasks(job) {
  return (job.tasks || []).filter(
    (task) => String(taskStatus(task)).toLowerCase() === "failed",
  );
}

function hasActionableFailure(job) {
  const status = String(job.status).toLowerCase();
  const failedTasks = failedJobTasks(job);
  if (failedTasks.length) {
    return failedTasks.some((task) => !isAlreadyRegisteredMessage(taskError(task)));
  }
  return status === "failed";
}

const expectedJobCount = computed(() => {
  if (!preview.value || !parsedSessionIds.value.length) {
    return parsedSessionIds.value.length;
  }
  const chunksPerSession = Math.max(
    1,
    Math.ceil(preview.value.row_count / BULK_JOB_CHUNK_SIZE),
  );
  return parsedSessionIds.value.length * chunksPerSession;
});

const progressPercent = computed(() => {
  const total = totalSessionCount.value || jobs.value.length;
  if (!total) {
    return 0;
  }
  return Math.min(100, Math.round((createdSessionCount.value / total) * 100));
});

const isPollingJobs = computed(() =>
  jobs.value.some(
    (job) => !["ended", "failed", "completed"].includes(String(job.status).toLowerCase()),
  ),
);

const visibleResultJobs = computed(() =>
  jobs.value.filter((job) => hasActionableFailure(job) || job.retry_results?.length),
);

const registrationSummary = computed(() => {
  const taskResults = jobs.value.flatMap((job) => job.tasks || []);
  const failedTasks = taskResults.filter((task) => {
    return String(taskStatus(task)).toLowerCase() === "failed";
  }).length;
  const failedJobs = jobs.value.filter((job) => hasActionableFailure(job)).length;

  return {
    jobs: totalSessionCount.value || jobs.value.length || (isSubmitting.value ? expectedJobCount.value : 0),
    created: createdSessionCount.value,
    finished: finishedJobs.value,
    totalTasks: taskResults.length,
    failedTasks,
    failedJobs,
  };
});

const progressTitle = computed(() => {
  if (isSubmitting.value) {
    return "Registering...";
  }
  if (isPollingJobs.value) {
    return "Checking results...";
  }
  return registrationSummary.value.failedJobs ? "Batch finished with failed jobs" : "Batch complete";
});

const progressMessage = computed(() => {
  if (isSubmitting.value) {
    const total = totalSessionCount.value || expectedJobCount.value;
    const current = Math.min(createdSessionCount.value + 1, total);
    return total ? `Processing batch ${current} of ${total}.` : "Sending registrants to Livestorm.";
  }
  if (isPollingJobs.value) {
    return "Checking Livestorm results.";
  }
  return registrationSummary.value.failedJobs
    ? "Review the rows that need attention below."
    : "All done. Review the results below.";
});

const completionTitle = computed(() =>
  registrationSummary.value.failedJobs ? "Some registrants need attention" : "All registrants are in",
);

const completionMessage = computed(() => {
  if (registrationSummary.value.failedJobs) {
    return "Some registrants need attention. Review the details below.";
  }
  return "Nice work. Livestorm accepted the full batch.";
});

function resetMessages() {
  errorMessage.value = "";
  successMessage.value = "";
}

async function readApiResponse(response, fallbackMessage) {
  const text = await response.text();
  if (!text.trim()) {
    if (!response.ok) {
      throw new Error(fallbackMessage);
    }
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    throw new Error(fallbackMessage);
  }
}

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

function startNewBatch() {
  sessionIds.value = "";
  selectedFile.value = null;
  preview.value = null;
  columnSettings.value = [];
  jobs.value = [];
  rowResults.value = [];
  hasSubmittedJobs.value = false;
  duplicateEmails.value = [];
  retryingSessions.value = {};
  totalSessionCount.value = 0;
  createdSessionCount.value = 0;
  isSubmitting.value = false;
  isPreviewLoading.value = false;
  totalSessionCount.value = 0;
  createdSessionCount.value = 0;
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

    const response = await fetch("/api/preview", {
      method: "POST",
      body: formData,
    });
    const data = await readApiResponse(response, "Preview failed. The server returned an empty or invalid response.");

    if (!response.ok) {
      throw new Error(data.detail || "Preview failed");
    }

    preview.value = data;
    columnSettings.value = data.headers.map((header) => {
      const normalized = data.normalized_headers[header];
      return {
        column: header,
        attributeId: normalized,
        include: true,
      };
    });
    const detectedEmailColumn = data.headers.find(
      (header) => data.normalized_headers[header] === "email",
    );
    duplicateEmails.value = detectedEmailColumn
      ? data.duplicate_email_columns[detectedEmailColumn] || []
      : [];
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isPreviewLoading.value = false;
  }
}

function updateColumnSetting(index, patch) {
  columnSettings.value = columnSettings.value.map((column, columnIndex) => {
    if (columnIndex !== index) {
      return column;
    }
    const nextColumn = { ...column, ...patch };
    if (nextColumn.attributeId === "email") {
      nextColumn.include = true;
    }
    return nextColumn;
  });
}

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

function jobFailedTasks(job) {
  return failedJobTasks(job);
}

function wait(milliseconds) {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds);
  });
}

async function pollJobUntilFinished(job) {
  while (!["ended", "failed", "completed"].includes(String(job.status).toLowerCase())) {
    const response = await fetch("/api/job-status", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        api_key: apiKey.value,
        session_id: job.session_id,
        job_id: job.job_id,
      }),
    });
    const data = await readApiResponse(response, "Failed to fetch job status. The server returned an empty or invalid response.");

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
  let failedRegistrants = jobFailedTasks(job)
    .map((task) => task.row_result)
    .filter((row) => row?.email);

  if (!failedRegistrants.length) {
    job.error = "No failed row details were available to retry with single registration.";
    return;
  }

  retryingSessions.value = {
    ...retryingSessions.value,
    [job.session_id]: true,
  };

  try {
    const response = await fetch("/api/retry-failed", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        api_key: apiKey.value,
        session_id: job.session_id,
        registrants: failedRegistrants,
      }),
    });
    const data = await readApiResponse(response, "Retry failed. The server returned an empty or invalid response.");

    if (!response.ok) {
      throw new Error(data.detail || "Retry failed");
    }

    job.retry_results = data.results || [];
  } catch (error) {
    job.error = error.message;
  } finally {
    retryingSessions.value = {
      ...retryingSessions.value,
      [job.session_id]: false,
    };
  }
}

async function submitRegistration() {
  resetMessages();

  if (!selectedFile.value) {
    errorMessage.value = "Please upload an .xlsx or .csv file.";
    return;
  }
  if (!preview.value) {
    errorMessage.value = "Preview the file before submitting.";
    return;
  }
  if (!parsedSessionIds.value.length) {
    errorMessage.value = "Session IDs must not be empty.";
    return;
  }
  if (!hasEmailColumn.value) {
    errorMessage.value = "The file must include an Email column.";
    return;
  }
  const includedAttributeIds = Object.values(autoMapping.value);
  if (!includedAttributeIds.includes("email")) {
    errorMessage.value = "The Email column must be included.";
    return;
  }
  if (includedAttributeIds.some((attributeId) => !attributeId)) {
    errorMessage.value = "Included columns must have a Livestorm field ID.";
    return;
  }
  if (new Set(includedAttributeIds).size !== includedAttributeIds.length) {
    errorMessage.value = "Included columns cannot use the same Livestorm field ID twice.";
    return;
  }
  if (!apiKey.value.trim()) {
    errorMessage.value = "Livestorm API key is required.";
    return;
  }

  isSubmitting.value = true;
  jobs.value = [];
  hasSubmittedJobs.value = false;
  totalSessionCount.value = expectedJobCount.value;
  createdSessionCount.value = 0;

  try {
    for (const sessionId of parsedSessionIds.value) {
      const expectedChunksForSession = Math.max(
        1,
        Math.ceil(preview.value.row_count / BULK_JOB_CHUNK_SIZE),
      );
      for (let chunkIndex = 1; chunkIndex <= expectedChunksForSession; chunkIndex += 1) {
        const formData = new FormData();
        formData.append("api_key", apiKey.value.trim());
        formData.append("session_ids", sessionId);
        formData.append("mapping", JSON.stringify(autoMapping.value));
        formData.append("chunk_index", String(chunkIndex));
        formData.append("chunk_size", String(BULK_JOB_CHUNK_SIZE));
        formData.append("file", selectedFile.value);

        const response = await fetch("/api/register", {
          method: "POST",
          body: formData,
        });
        const data = await readApiResponse(response, "Registration failed. The server returned an empty or invalid response.");

        if (!response.ok) {
          jobs.value.push({
            session_id: sessionId,
            job_id: `not-created-${chunkIndex}`,
            status: "failed",
            chunk_index: chunkIndex,
            chunk_count: expectedChunksForSession,
            row_start: ((chunkIndex - 1) * BULK_JOB_CHUNK_SIZE) + 2,
            row_count: Math.min(
              BULK_JOB_CHUNK_SIZE,
              preview.value.row_count - ((chunkIndex - 1) * BULK_JOB_CHUNK_SIZE),
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

        if (!rowResults.value.length) {
          rowResults.value = data.row_results || [];
        }
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
</script>

<template>
  <main class="page-shell">
    <section class="hero">
      <div>
        <div class="brand-lockup">
          <img :src="livestormIcon" alt="Livestorm" />
          <div>
            <p class="eyebrow">StormBatch</p>
            <span>Powered by Livestorm workflows</span>
          </div>
        </div>
        <h1>Turn an Excel sheet into Livestorm session registrants.</h1>
      </div>
    </section>

    <section class="workflow-grid">
      <div class="panel step-panel">
        <div class="step-label">Step 1</div>
        <ApiKeyInput v-model="apiKey" />
        <SessionIdsInput v-model="sessionIds" :count="parsedSessionIds.length" />
      </div>
      <div class="panel step-panel">
        <div class="step-label">Step 2</div>
        <FileUpload
          :selected-file="selectedFile"
          :loading="isPreviewLoading"
          :preview-ready="Boolean(preview)"
          @file-selected="onFileSelected"
          @preview="loadPreview"
        />
      </div>
    </section>

    <section v-if="errorMessage" class="notice error">{{ errorMessage }}</section>
    <section v-if="successMessage" class="notice success">{{ successMessage }}</section>

    <section v-if="preview" class="panel preview-panel">
      <div class="panel-header">
        <div>
          <span class="step-label">Step 3</span>
          <h2>Preview registrants</h2>
          <p>{{ preview.row_count }} rows, {{ preview.headers.length }} columns</p>
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
        <div
          v-for="(item, index) in mappedAttributePreview"
          :key="item.column"
          class="column-card"
          :class="{ included: item.include }"
        >
          <div>
            <strong>{{ item.column }}</strong>
            <span>{{ item.required ? "Required email field" : "Optional field" }}</span>
          </div>
          <div class="column-actions">
            <label class="include-toggle" :class="{ disabled: item.required }">
              <input
                type="checkbox"
                :checked="item.include"
                :disabled="item.required"
                @change="updateColumnSetting(index, { include: $event.target.checked })"
              />
              <span class="toggle-track">
                <span class="toggle-thumb"></span>
              </span>
            </label>
            <strong class="toggle-label">{{ item.include ? "Send" : "Drop" }}</strong>
          </div>
          <input
            :value="item.attributeId"
            :disabled="!item.include || item.required"
            placeholder="Livestorm field ID"
            @input="updateColumnSetting(index, { attributeId: $event.target.value })"
          />
        </div>
      </div>
      <PreviewTable :headers="preview.headers" :rows="preview.preview_rows" />

      <div class="cta-card">
        <div>
          <span class="step-label">Step 4</span>
          <h2>Ready to batch register?</h2>
          <p>
            This will create {{ expectedJobCount }} Livestorm job(s) in batches of
            {{ BULK_JOB_CHUNK_SIZE }} registrants or fewer.
          </p>
        </div>
        <div class="cta-actions">
          <button
            class="primary-button"
            :disabled="isSubmitting || isPollingJobs"
            @click="submitRegistration"
          >
            {{ isSubmitting ? "Creating jobs..." : "Batch register now" }}
          </button>
        </div>
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

    <section
      v-if="hasSubmittedJobs && !isPollingJobs && jobs.length"
      class="confirmation-card"
      :class="{ failed: registrationSummary.failedJobs }"
    >
      <div>
        <span class="confirmation-icon">{{ registrationSummary.failedJobs ? "!" : "✓" }}</span>
      </div>
      <div>
        <h2>{{ completionTitle }}</h2>
        <p>{{ completionMessage }}</p>
      </div>
      <button class="new-batch-button" type="button" @click="startNewBatch">
        New Batch
      </button>
    </section>

    <section v-if="visibleResultJobs.length" class="panel">
      <div class="panel-header results-header">
        <div>
          <span class="step-label">Results</span>
          <h2>Rows needing attention</h2>
        </div>
      </div>
      <JobResults
        :jobs="visibleResultJobs"
        :retrying-sessions="retryingSessions"
        @retry-failed="retryFailedRows"
      />
    </section>
  </main>
</template>

<style>
.page-shell {
  max-width: 1180px;
  margin: 0 auto;
  padding: 40px 16px 56px;
  min-height: 100vh;
}

.hero {
  display: block;
  margin-bottom: 28px;
}

.brand-lockup {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 18px;
}

.brand-lockup img {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  object-fit: contain;
  box-shadow: none;
}

.brand-lockup span {
  display: block;
  margin-top: 2px;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
  font-weight: var(--text-content-text-regular-md--font-weight);
}

.eyebrow {
  margin: 0;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-lg);
  line-height: var(--text-content-text-bold-lg--line-height);
  letter-spacing: var(--text-content-text-bold-lg--letter-spacing);
  font-weight: var(--text-content-text-bold-lg--font-weight);
}

.hero h1 {
  max-width: 700px;
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-title-md);
  line-height: var(--text-title-md--line-height);
  letter-spacing: var(--text-title-md--letter-spacing);
  font-weight: var(--text-title-md--font-weight);
}

.intro {
  max-width: 760px;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
}

.confirmation-card,
.cta-card {
  border: 1px solid var(--color-borders-neutral-light);
  background: var(--color-surface-neutral-200);
  border-radius: 8px;
  padding: 22px;
  box-shadow: none;
}

.step-label {
  display: inline-flex;
  width: fit-content;
  margin-bottom: 12px;
  color: var(--color-actions-primary-idle);
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1px solid var(--color-borders-primary-light);
  border-radius: 6px;
  padding: 4px 9px;
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.cta-card p {
  margin-bottom: 0;
  color: var(--color-text-neutral-secondary);
}

.workflow-grid {
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  gap: 18px;
  align-items: stretch;
}

.panel {
  background: var(--color-surface-neutral-200);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  padding: 22px;
  margin-bottom: 18px;
  box-shadow: none;
}

.step-panel {
  min-height: 100%;
}

.preview-panel {
  border-color: var(--color-borders-neutral-default);
  margin-top: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 18px;
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

.notice {
  margin-top: 16px;
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 8px;
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
  padding: 10px 12px;
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

.status-pill,
.attribute-chip {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  border-radius: 8px;
  padding: 7px 10px;
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

.attribute-preview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.column-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  background: var(--color-surface-neutral-100);
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
}

.column-card > input:disabled {
  color: var(--color-text-neutral-tertiary);
  background: var(--color-surface-neutral-200);
}

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
  opacity: 0.75;
}

.include-toggle input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.toggle-track {
  display: inline-flex;
  align-items: center;
  width: 48px;
  height: 28px;
  padding: 3px;
  border-radius: 8px;
  background: var(--color-surface-neutral-100);
  transition: background 0.2s ease;
}

.toggle-label {
  line-height: 1;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-md);
}

.toggle-thumb {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--color-surface-neutral-bg-main);
  box-shadow: 0 2px 8px var(--color-shadow-neutral-200);
  transition: transform 0.2s ease;
}

.include-toggle input:checked + .toggle-track {
  background: var(--color-actions-success-idle);
}

.include-toggle input:checked + .toggle-track .toggle-thumb {
  transform: translateX(20px);
}

.include-toggle input:focus-visible + .toggle-track {
  outline: 3px solid var(--color-focus-ring);
  outline-offset: 2px;
}

.cta-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 18px;
  align-items: center;
  margin-top: 20px;
}

.primary-button {
  width: 100%;
  border: none;
  border-radius: 8px;
  padding: 16px 18px;
  font-size: var(--text-action-button-lg);
  line-height: var(--text-action-button-lg--line-height);
  font-weight: var(--text-action-button-lg--font-weight);
  color: var(--color-text-neutral-complementary-base);
  background: var(--color-actions-primary-idle);
  border: 1px solid var(--color-actions-primary-idle);
  cursor: pointer;
  box-shadow: none;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.primary-button:hover:not(:disabled) {
  background: var(--color-actions-primary-idle-alpha-strong);
  border-color: var(--color-actions-primary-idle-alpha-strong);
}

.primary-button:disabled {
  color: var(--color-text-neutral-tertiary);
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  opacity: 1;
  cursor: not-allowed;
  box-shadow: none;
}

.progress-panel {
  border-color: var(--color-borders-primary-light);
}

.progress-percent {
  font-size: var(--text-title-lg);
  line-height: var(--text-title-lg--line-height);
  color: var(--color-text-primary-base);
}

.progress-track {
  height: 14px;
  overflow: hidden;
  border-radius: 8px;
  background: var(--color-surface-neutral-300);
}

.progress-fill {
  height: 100%;
  min-width: 8px;
  border-radius: inherit;
  background: var(--color-actions-primary-idle);
  transition: width 0.4s ease;
}

.confirmation-card {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  border-color: var(--color-borders-success-light);
  background: var(--color-surface-success-300);
}

.confirmation-card.failed {
  border-color: var(--color-borders-danger-light);
  background: var(--color-surface-danger-300);
}

.confirmation-icon {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 8px;
  background: var(--color-actions-success-idle);
  color: var(--color-text-neutral-complementary-base);
  font-size: var(--text-title-md);
  line-height: var(--text-title-md--line-height);
  font-weight: var(--text-title-md--font-weight);
}

.confirmation-card.failed .confirmation-icon {
  background: var(--color-actions-danger-idle);
}

.new-batch-button {
  flex: 0 0 auto;
  border: 1px solid var(--color-borders-neutral-default);
  border-radius: 8px;
  padding: 12px 16px;
  color: var(--color-text-neutral-base);
  background: var(--color-surface-neutral-100);
  font-size: var(--text-action-button-md);
  line-height: var(--text-action-button-md--line-height);
  font-weight: var(--text-action-button-md--font-weight);
  cursor: pointer;
}

.new-batch-button:hover {
  background: var(--color-actions-neutral-hover-overlay);
}

.results-header {
  margin-bottom: 14px;
}

@media (max-width: 860px) {
  .hero,
  .workflow-grid,
  .cta-card {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .page-shell {
    padding: 20px 12px 36px;
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
}
</style>
