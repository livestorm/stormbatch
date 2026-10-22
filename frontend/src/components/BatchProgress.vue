<script setup>
import { computed } from "vue";
import JobResults from "./JobResults.vue";
import {
  failedJobTasks,
  failedRows,
  hasActionableFailure,
  isFinalStatus,
} from "../composables/useBatchJobs";

const props = defineProps({
  // The reactive object returned by useBatchJobs().
  batch: { type: Object, required: true },
  runningTitle: { type: String, default: "Registering…" },
});

const emit = defineEmits(["new-batch", "download-failed"]);

const total = computed(() => props.batch.totalJobCount || props.batch.jobs.length);

// Sending a batch and Livestorm finishing it each count for half.
const progressPercent = computed(() =>
  total.value
    ? Math.min(100, Math.round(((props.batch.createdJobCount + props.batch.doneJobCount) / (2 * total.value)) * 100))
    : 0,
);

const failedJobCount = computed(() => props.batch.jobs.filter(hasActionableFailure).length);

const alreadyRegisteredOnlyJobCount = computed(
  () => props.batch.jobs.filter((j) => failedJobTasks(j).length > 0 && !hasActionableFailure(j)).length,
);

const visibleResultJobs = computed(() =>
  props.batch.jobs.filter((j) => hasActionableFailure(j) || j.retry_results?.length),
);

const isFinished = computed(
  () => props.batch.hasSubmittedJobs && props.batch.jobs.length && props.batch.jobs.every((j) => isFinalStatus(j.status)),
);

const rowsToDownload = computed(() => (isFinished.value ? failedRows(props.batch.jobs) : []));

const progressTitle = computed(() => {
  if (props.batch.isSubmitting) return props.runningTitle;
  if (props.batch.isPollingJobs) return "Checking results…";
  return failedJobCount.value ? "Batch finished with failed jobs" : "Batch complete";
});

const progressMessage = computed(() => {
  if (props.batch.isSubmitting) {
    return `Sending batch ${Math.min(props.batch.createdJobCount + 1, total.value)} of ${total.value} to Livestorm.`;
  }
  if (props.batch.isPollingJobs) {
    return `Livestorm is processing batch ${Math.min(props.batch.doneJobCount + 1, total.value)} of ${total.value}.`;
  }
  return failedJobCount.value ? "Review the rows that need attention below." : "All done.";
});

const completionTitle = computed(() =>
  failedJobCount.value ? "Some registrants need attention" : "All registrants are in",
);

const completionMessage = computed(() => {
  if (failedJobCount.value) return "Some rows couldn't be registered. Check the details below, retry, or download them to fix and re-upload.";
  if (alreadyRegisteredOnlyJobCount.value) return "Nice work. Some were already registered in Livestorm, so they're all set.";
  return "Nice work. Livestorm accepted the full batch.";
});
</script>

<template>
  <section v-if="batch.jobs.length || batch.isSubmitting" class="panel progress-panel" role="status">
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

  <section v-if="isFinished" class="confirmation-card" :class="{ failed: failedJobCount }">
    <div class="confirmation-icon">
      <svg v-if="!failedJobCount" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
      <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
    </div>
    <div>
      <h2>{{ completionTitle }}</h2>
      <p>{{ completionMessage }}</p>
    </div>
    <button class="new-batch-button" type="button" @click="emit('new-batch')">New batch</button>
  </section>

  <section v-if="visibleResultJobs.length" class="panel">
    <div class="panel-header results-header">
      <div>
        <span class="step-label">Results</span>
        <h2>Rows needing attention</h2>
      </div>
      <button
        v-if="rowsToDownload.length"
        class="bar-btn"
        type="button"
        @click="emit('download-failed', rowsToDownload)"
      >
        Download {{ rowsToDownload.length }} failed row{{ rowsToDownload.length === 1 ? "" : "s" }} (.csv)
      </button>
    </div>
    <JobResults
      :jobs="visibleResultJobs"
      :retrying-sessions="batch.retryingSessions"
      @retry-failed="batch.retryFailedRows"
    />
  </section>
</template>
