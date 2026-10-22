import { computed, reactive, ref } from "vue";
import { errorDetail, readApiResponse, requestJson, wait } from "../api";

export const BULK_JOB_CHUNK_SIZE = 50;
const JOB_STATUS_POLL_INTERVAL_MS = 5000;
// 0.25 s between job creations → 4 req/s, safely under Livestorm's 5 req/s burst limit.
const JOB_CREATION_DELAY_MS = 250;
const FINAL_STATUSES = ["ended", "failed", "completed"];

export function isFinalStatus(status) {
  return FINAL_STATUSES.includes(String(status).toLowerCase());
}

export function taskStatus(task) {
  return task?.attributes?.status || task?.status || "unknown";
}

export function taskError(task) {
  const attrs = task?.attributes || {};
  const errors = attrs.errors || task?.errors;
  if (Array.isArray(errors)) {
    return errors.map((e) => e.detail || e.title || e.message || String(e)).join(", ");
  }
  return attrs.error || attrs.message || task?.error || task?.message || "";
}

export function isAlreadyRegisteredMessage(message) {
  const n = String(message).toLowerCase();
  return (
    n.includes("already been invited") ||
    n.includes("already registered") ||
    n.includes("has already been taken") ||
    n.includes("already been registered")
  );
}

export function failedJobTasks(job) {
  return (job.tasks || []).filter((t) => String(taskStatus(t)).toLowerCase() === "failed");
}

export function hasActionableFailure(job) {
  const failed = failedJobTasks(job);
  if (failed.length) return failed.some((t) => !isAlreadyRegisteredMessage(taskError(t)));
  return String(job.status).toLowerCase() === "failed";
}

// Rows still not registered once Livestorm answered and any retry ran, with the
// reason. "Already registered" rows are not failures.
export function failedRows(jobs) {
  return jobs.flatMap((job) => {
    const fixedByRetry = new Set(
      (job.retry_results || [])
        .filter((result) => result.status !== "failed")
        .map((result) => String(result.email).toLowerCase()),
    );
    const failedTasks = failedJobTasks(job).filter((t) => !isAlreadyRegisteredMessage(taskError(t)));
    if (failedTasks.length) {
      return failedTasks
        .filter((t) => !fixedByRetry.has(String(t.row_result.email).toLowerCase()))
        .map((t) => ({
          sessionId: job.session_id,
          row: t.row_result,
          error: taskError(t) || "Livestorm did not give a reason.",
        }));
    }
    if (String(job.status).toLowerCase() === "failed" && !job.tasks?.length) {
      return job.row_results.map((row) => ({
        sessionId: job.session_id,
        row,
        error: job.error || "The batch failed before Livestorm returned row details.",
      }));
    }
    return [];
  });
}

// A registrant is { fields: [{ id, value }], row_result: { row_number, email,
// source_index, fields } }; row_result travels with the job for results,
// retries and the failed-rows download.
function chunkRegistrants(registrants) {
  const chunks = [];
  for (let start = 0; start < registrants.length; start += BULK_JOB_CHUNK_SIZE) {
    chunks.push(registrants.slice(start, start + BULK_JOB_CHUNK_SIZE));
  }
  return chunks;
}

export function countJobs(registrantCount) {
  return Math.ceil(registrantCount / BULK_JOB_CHUNK_SIZE);
}

function attachRowResults(tasks, job) {
  return tasks.map((task, index) => ({
    ...task,
    row_result: job.row_results[index] || { row_number: null, email: "", fields: [] },
  }));
}

async function checkJobStatus(job) {
  const fallbackMessage = "We couldn't check this batch's status.";
  const response = await fetch("/api/job-status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: job.session_id, job_id: job.job_id }),
  });
  const data = await readApiResponse(response, fallbackMessage);

  if (!response.ok) {
    const detail = errorDetail(data, fallbackMessage);
    if (detail.toLowerCase().includes("throttle limit")) {
      job.warning = "Livestorm is rate limiting status checks. StormBatch will keep waiting and try again.";
      return;
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
}

// One batch run: a Livestorm bulk job per (session, chunk of 50).
export function useBatchJobs() {
  const jobs = ref([]);
  const isSubmitting = ref(false);
  const hasSubmittedJobs = ref(false);
  const totalJobCount = ref(0);
  const createdJobCount = ref(0);
  const retryingSessions = ref({});

  const doneJobCount = computed(() => jobs.value.filter((j) => isFinalStatus(j.status)).length);
  const isPollingJobs = computed(() => jobs.value.some((j) => !isFinalStatus(j.status)));
  const isBusy = computed(() => isSubmitting.value || isPollingJobs.value);

  function reset() {
    jobs.value = [];
    isSubmitting.value = false;
    hasSubmittedJobs.value = false;
    totalJobCount.value = 0;
    createdJobCount.value = 0;
    retryingSessions.value = {};
  }

  // `targets` is [{ sessionId, registrants }]. Every job is created first so
  // Livestorm works through them while we wait, then the oldest unfinished job
  // is followed: Livestorm runs them in order, so one status check at a time is enough.
  async function run({ targets, fallbackMessage }) {
    reset();
    const planned = targets.flatMap(({ sessionId, registrants }) => {
      const chunks = chunkRegistrants(registrants);
      return chunks.map((chunk, i) => ({ sessionId, chunk, index: i + 1, count: chunks.length }));
    });
    totalJobCount.value = planned.length;

    isSubmitting.value = true;
    try {
      for (const [position, { sessionId, chunk, index, count }] of planned.entries()) {
        if (position > 0) await wait(JOB_CREATION_DELAY_MS);
        // Poll through the reactive proxy: a plain object pushed into the
        // array would update without notifying the progress UI.
        const job = reactive({
          session_id: sessionId,
          job_id: `not-created-${sessionId}-${index}`,
          status: "pending",
          chunk_index: index,
          chunk_count: count,
          row_results: chunk.map((registrant) => registrant.row_result),
          tasks: [],
          raw: {},
          warning: "",
          error: "",
        });
        jobs.value.push(job);
        try {
          const created = await requestJson("/api/bulk-jobs", {
            method: "POST",
            body: { session_id: sessionId, registrants: chunk.map(({ fields }) => ({ fields })) },
            fallbackMessage,
          });
          job.job_id = created.job_id;
          job.status = created.status || "pending";
        } catch (error) {
          if (error.status === 401) throw error;
          job.status = "failed";
          job.error = error.message;
        }
        createdJobCount.value += 1;
      }
    } finally {
      isSubmitting.value = false;
    }

    let job;
    while ((job = jobs.value.find((j) => !isFinalStatus(j.status)))) {
      await checkJobStatus(job);
      if (!isFinalStatus(job.status)) await wait(JOB_STATUS_POLL_INTERVAL_MS);
    }
    hasSubmittedJobs.value = true;
  }

  async function retryFailedRows(job) {
    const registrants = failedJobTasks(job)
      .map((t) => t.row_result)
      .filter((r) => r?.email);
    if (!registrants.length) {
      job.error = "No failed row details were available to retry with single registration.";
      return;
    }

    retryingSessions.value = { ...retryingSessions.value, [job.session_id]: true };
    try {
      const data = await requestJson("/api/retry-failed", {
        method: "POST",
        body: { session_id: job.session_id, registrants },
        fallbackMessage: "Retry failed.",
      });
      job.retry_results = data.results || [];
    } catch (error) {
      job.error = error.message;
    } finally {
      retryingSessions.value = { ...retryingSessions.value, [job.session_id]: false };
    }
  }

  return reactive({
    jobs,
    isSubmitting,
    hasSubmittedJobs,
    totalJobCount,
    createdJobCount,
    doneJobCount,
    retryingSessions,
    isPollingJobs,
    isBusy,
    reset,
    run,
    retryFailedRows,
  });
}
