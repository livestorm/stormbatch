<script setup>
const props = defineProps({
  jobs: {
    type: Array,
    required: true,
  },
  retryingSessions: {
    type: Object,
    default: () => ({}),
  },
});

const emit = defineEmits(["retry-failed"]);

const FINAL_STATUSES = ["ended", "failed", "completed"];

function isFinal(job) {
  return FINAL_STATUSES.includes(String(job.status).toLowerCase());
}

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
    || normalized.includes("has already been taken")
    || normalized.includes("already been registered");
}

function displayError(task) {
  const error = taskError(task);
  return isAlreadyRegisteredMessage(error)
    ? "Already registered"
    : error || "Livestorm did not provide a row-level error.";
}

function rowLabel(task) {
  const row = task?.row_result || {};
  return [row.email, `Excel row ${row.row_number || "?"}`].filter(Boolean).join(" - ");
}

function failedTasks(job) {
  return (job.tasks || []).filter(
    (task) => String(taskStatus(task)).toLowerCase() === "failed",
  );
}

function alreadyRegisteredTasks(job) {
  return failedTasks(job).filter((task) => isAlreadyRegisteredMessage(taskError(task)));
}

function actionableFailedTasks(job) {
  return failedTasks(job).filter((task) => !isAlreadyRegisteredMessage(taskError(task)));
}

function succeededTasks(job) {
  return (job.tasks || []).filter(
    (task) => String(taskStatus(task)).toLowerCase() === "succeeded",
  );
}

function retryResults(job) {
  return job.retry_results || [];
}

function summaryText(job) {
  if (!isFinal(job)) {
    return "Livestorm is still processing this session.";
  }
  if (!job.tasks?.length) {
    return String(job.status).toLowerCase() === "failed"
      ? "The job failed before Livestorm returned row-level task details."
      : "The job finished successfully. Livestorm did not return row-level task details.";
  }
  const failed = failedTasks(job).length;
  const alreadyRegistered = alreadyRegisteredTasks(job).length;
  const actionable = actionableFailedTasks(job).length;
  const succeeded = succeededTasks(job).length;
  if (!failed) {
    return `${succeeded} registrant(s) succeeded.`;
  }
  if (!actionable) {
    return `${succeeded} succeeded, ${alreadyRegistered} already registered.`;
  }
  return `${succeeded} succeeded, ${alreadyRegistered} already registered, ${actionable} need attention.`;
}

function displayStatus(job) {
  if (failedTasks(job).length && !actionableFailedTasks(job).length) {
    return "Already registered";
  }
  return job.status;
}

function cardClass(job) {
  if (!isFinal(job)) {
    return "processing";
  }
  if (failedTasks(job).length && !actionableFailedTasks(job).length) {
    return "succeeded";
  }
  return actionableFailedTasks(job).length || String(job.status).toLowerCase() === "failed"
    ? "has-failures"
    : "succeeded";
}
</script>

<template>
  <div class="jobs-grid">
    <article
      v-for="job in props.jobs"
      :key="`${job.session_id}-${job.job_id}`"
      class="job-card"
      :class="cardClass(job)"
    >
      <div class="job-header">
        <div>
          <span class="session-label">Session</span>
          <h3>{{ job.session_id }}</h3>
          <p>{{ summaryText(job) }}</p>
        </div>
        <span class="status">{{ displayStatus(job) }}</span>
      </div>

      <p v-if="job.error" class="job-error">{{ job.error }}</p>
      <p v-if="job.warning" class="job-warning">{{ job.warning }}</p>

      <div v-if="failedTasks(job).length" class="failed-panel">
        <div class="failed-header">
          <strong>{{ actionableFailedTasks(job).length ? "Registrants needing attention" : "Already registered" }}</strong>
          <button
            v-if="actionableFailedTasks(job).length"
            class="retry-button"
            type="button"
            :disabled="props.retryingSessions[job.session_id]"
            @click="emit('retry-failed', job)"
          >
            {{ props.retryingSessions[job.session_id] ? "Retrying..." : "Retry failed rows" }}
          </button>
        </div>

        <div
          v-for="task in failedTasks(job)"
          :key="task.id || rowLabel(task)"
          class="failed-row"
          :class="{ duplicate: isAlreadyRegisteredMessage(taskError(task)) }"
        >
          <div>
            <strong>{{ rowLabel(task) }}</strong>
            <p>{{ displayError(task) }}</p>
          </div>
        </div>
      </div>

      <div v-if="retryResults(job).length" class="retry-results">
        <strong>Retry results</strong>
        <div v-for="result in retryResults(job)" :key="`${result.email}-${result.row_number}`" class="retry-row">
          <span>{{ result.email }}</span>
          <span :class="['retry-status', result.status]">
            {{ result.status === "registered" ? "Already registered" : result.status }}
          </span>
          <p v-if="result.error">{{ result.error }}</p>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.jobs-grid {
  display: grid;
  gap: 14px;
}

.job-card {
  border: 1px solid var(--color-borders-neutral-light);
  background: var(--color-surface-neutral-100);
  border-radius: 10px;
  padding: 18px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.job-card.succeeded {
  border-color: var(--color-borders-success-light);
  background: var(--color-surface-success-300);
}

.job-card.has-failures {
  border-color: var(--color-borders-danger-light);
  background: var(--color-surface-danger-300);
}

.job-card.processing {
  background: var(--color-surface-warning-300);
}

.job-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  flex-wrap: wrap;
}

h3,
p {
  margin: 0;
}

h3 {
  margin: 4px 0 6px;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-lg);
  line-height: var(--text-content-text-bold-lg--line-height);
  font-weight: var(--text-content-text-bold-lg--font-weight);
  overflow-wrap: anywhere;
}

.session-label {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.status {
  background: var(--color-surface-primary-100);
  color: var(--color-text-primary-base);
  border: 1px solid var(--color-borders-primary-light);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
  text-transform: capitalize;
}

.failed-panel,
.retry-results {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--color-borders-neutral-light);
}

.failed-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.failed-row,
.retry-row {
  padding: 12px;
  background: var(--color-surface-neutral-100);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  transition: border-color 0.15s ease;
}

.failed-row p,
.retry-row p,
.job-error {
  margin-top: 4px;
  color: var(--color-text-danger-secondary);
}

.job-warning {
  margin-top: 4px;
  color: var(--color-text-warning-secondary);
}

.failed-row.duplicate p {
  color: var(--color-text-primary-secondary);
}

.retry-button {
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 9px 14px;
  color: var(--color-text-neutral-complementary-base);
  background: var(--color-actions-primary-idle);
  font-size: var(--text-action-button-md);
  line-height: var(--text-action-button-md--line-height);
  font-weight: var(--text-action-button-md--font-weight);
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.retry-button:hover:not(:disabled) {
  background: var(--color-actions-primary-idle-alpha-strong);
  box-shadow: 0 0 0 1px var(--color-actions-primary-idle);
}

.retry-button:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.retry-row {
  display: grid;
  gap: 6px;
}

.retry-status {
  width: fit-content;
  border-radius: 8px;
  padding: 5px 9px;
  font-size: var(--text-content-badges-bold-md);
  line-height: var(--text-content-badges-bold-md--line-height);
  font-weight: var(--text-content-badges-bold-md--font-weight);
  text-transform: capitalize;
}

.retry-status.succeeded {
  background: var(--color-surface-success-300);
  color: var(--color-text-success-secondary);
}

.retry-status.registered {
  background: var(--color-surface-primary-100);
  color: var(--color-text-primary-secondary);
}

.retry-status.failed {
  background: var(--color-surface-danger-300);
  color: var(--color-text-danger-secondary);
}
</style>
