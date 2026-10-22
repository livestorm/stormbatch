<script setup>
import { computed, ref, watch } from "vue";
import BatchProgress from "./BatchProgress.vue";
import RegisterCard from "./RegisterCard.vue";
import SessionPicker from "./SessionPicker.vue";
import { requestJson } from "../api";
import { BULK_JOB_CHUNK_SIZE, countJobs, useBatchJobs } from "../composables/useBatchJobs";
import { useRegisteredEmails } from "../composables/useRegisteredEmails";
import { downloadCsv, fileSlug } from "../csv";
import { peopleLabel, registrantsLabel, sessionStartLabel } from "../sessions";

const props = defineProps({
  // Target session detail from /api/sessions/{id}, including its form fields.
  session: { type: Object, required: true },
});

const emit = defineEmits(["busy-change", "done"]);

const source = ref(null);
const transferData = ref(null); // { session_id, headers, rows, total }
const excludedRows = ref({}); // { [rowIndex]: true }
const includedFields = ref([]);
const isSourceLoading = ref(false);
const errorMessage = ref("");
const extraSessionIds = ref([]);
const batch = useBatchJobs();
const { checkRegistered, isRegistered, registeredCheckNote } = useRegisteredEmails(props.session);

watch(() => batch.isBusy, (busy) => emit("busy-change", busy));

// Email is implicit in every registration form and not always listed.
const canCheckFields = computed(() => props.session.fields.length > 0);
const targetFieldIds = computed(() => new Set(["email", ...props.session.fields.map((f) => f.id)]));

function isInTargetForm(fieldId) {
  return !canCheckFields.value || targetFieldIds.value.has(fieldId);
}

// Kept rows as registrants; row numbers follow the source list.
const registrants = computed(() => {
  if (!transferData.value) return [];
  return transferData.value.rows.flatMap((row, index) => {
    if (excludedRows.value[index]) return [];
    return [{
      fields: includedFields.value
        .map((id) => ({ id, value: (row[id] || "").trim() }))
        .filter((field) => field.value),
      row_result: {
        row_number: index + 1,
        email: row.email,
        source_index: index,
        fields: includedFields.value.map((id) => ({ attribute_id: id, value: row[id] || "" })),
      },
    }];
  });
});
// People already registered to this session are skipped for it, but still
// sent to any other session added on the register card.
const newRegistrants = computed(() => registrants.value.filter((r) => !isRegistered(r.row_result.email)));
const alreadyRegisteredCount = computed(() => registrants.value.length - newRegistrants.value.length);
const excludedCount = computed(() => Object.keys(excludedRows.value).length);
const fieldsMissingFromTarget = computed(() =>
  transferData.value ? transferData.value.headers.filter((f) => !isInTargetForm(f)) : [],
);

async function pickSource(session) {
  source.value = session;
  transferData.value = null;
  excludedRows.value = {};
  includedFields.value = [];
  errorMessage.value = "";
  isSourceLoading.value = true;
  try {
    const data = await requestJson("/api/session-people", {
      method: "POST",
      body: { session_id: session.id },
      fallbackMessage: "We couldn't load the registrants of this session.",
    });
    transferData.value = data;
    includedFields.value = data.headers.filter(isInTargetForm);
    checkRegistered();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isSourceLoading.value = false;
  }
}

function changeSource() {
  source.value = null;
  transferData.value = null;
  errorMessage.value = "";
  batch.reset();
}

function toggleField(fieldId) {
  if (fieldId === "email" || !isInTargetForm(fieldId)) return;
  includedFields.value = includedFields.value.includes(fieldId)
    ? includedFields.value.filter((f) => f !== fieldId)
    : [...includedFields.value, fieldId];
}

function removeRow(index) {
  excludedRows.value = { ...excludedRows.value, [index]: true };
}

function restoreRow(index) {
  const next = { ...excludedRows.value };
  delete next[index];
  excludedRows.value = next;
}

const registerNotes = computed(() => {
  const notes = [];
  if (alreadyRegisteredCount.value) {
    notes.push(`${peopleLabel(alreadyRegisteredCount.value)} already registered to this session will be skipped.`);
  }
  if (registeredCheckNote.value) notes.push(registeredCheckNote.value);
  return notes;
});

const registerDescription = computed(() => {
  const count = newRegistrants.value.length;
  if (!registrants.value.length) return "Everyone has been removed from the list.";
  if (!count) return "Everyone on this list is already registered to this session.";
  const jobs = countJobs(count);
  return `${peopleLabel(count)} will be registered in ${jobs} batch${jobs === 1 ? "" : "es"} of up to ${BULK_JOB_CHUNK_SIZE}.`;
});

async function submit(targetSessionIds) {
  errorMessage.value = "";
  if (!registrants.value.length) {
    errorMessage.value = "Everyone has been removed from the list. Restore at least one person to import.";
    return;
  }
  const targets = targetSessionIds
    .map((sessionId) => ({
      sessionId,
      registrants: sessionId === props.session.id ? newRegistrants.value : registrants.value,
    }))
    .filter((target) => target.registrants.length);
  try {
    await batch.run({ targets, fallbackMessage: "Import failed." });
  } catch (error) {
    errorMessage.value = error.message;
  }
}

function downloadFailedRows(rows) {
  const headers = transferData.value.headers;
  const severalSessions = new Set(rows.map((r) => r.sessionId)).size > 1;
  downloadCsv(
    `stormbatch-failed-rows-${fileSlug(props.session.title)}.csv`,
    [...headers, "stormbatch_error", ...(severalSessions ? ["stormbatch_session_id"] : [])],
    rows.map(({ sessionId, row, error }) => [
      ...headers.map((header) => transferData.value.rows[row.source_index]?.[header] ?? ""),
      error,
      ...(severalSessions ? [sessionId] : []),
    ]),
  );
}
</script>

<template>
  <section v-if="!source" class="panel">
    <h2 class="step-heading">Which session do you want to import people from?</h2>
    <SessionPicker scope="any" :exclude-id="session.id" @select="pickSource" />
  </section>

  <template v-else>
    <section class="panel source-summary">
      <div>
        <span class="step-label">Import from</span>
        <h2>{{ source.title }}</h2>
        <p>{{ sessionStartLabel(source) }} · {{ registrantsLabel(source.registrants_count) }}</p>
      </div>
      <button class="bar-btn" type="button" :disabled="batch.isBusy || isSourceLoading" @click="changeSource">
        Change source
      </button>
    </section>

    <p v-if="isSourceLoading" class="loading-line" role="status">Loading registrants…</p>
    <section v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</section>

    <section v-if="transferData" class="panel preview-panel">
      <div class="panel-header">
        <div>
          <span class="step-label">Registrants</span>
          <h2>{{ transferData.total }} {{ transferData.total === 1 ? "person" : "people" }} to import</h2>
          <p>Remove anyone you don't want to register, and choose which details to copy.</p>
        </div>
        <div class="preview-statuses">
          <div class="status-pill ok">{{ newRegistrants.length }} to import</div>
          <div v-if="alreadyRegisteredCount" class="status-pill ok">{{ alreadyRegisteredCount }} already registered</div>
          <div v-if="excludedCount" class="status-pill error">{{ excludedCount }} removed</div>
        </div>
      </div>

      <div class="field-toggles-section">
        <span class="field-toggles-label">Details to copy</span>
        <div class="attribute-preview">
          <div
            v-for="field in transferData.headers"
            :key="field"
            class="column-card"
            :class="{ included: includedFields.includes(field) }"
          >
            <div>
              <strong>{{ field }}</strong>
              <span v-if="field === 'email'">Required</span>
              <span v-else-if="!isInTargetForm(field)">Not in this session's form</span>
              <span v-else>Optional</span>
            </div>
            <div class="column-actions">
              <label class="include-toggle" :class="{ disabled: field === 'email' || !isInTargetForm(field) }">
                <input
                  type="checkbox"
                  :checked="includedFields.includes(field)"
                  :disabled="field === 'email' || !isInTargetForm(field)"
                  :aria-label="`Copy ${field}`"
                  @change="toggleField(field)"
                />
                <span class="toggle-track"><span class="toggle-thumb"></span></span>
              </label>
              <strong class="toggle-label">{{ includedFields.includes(field) ? "Copy" : "Skip" }}</strong>
            </div>
          </div>
        </div>
        <p v-if="fieldsMissingFromTarget.length" class="fields-hint">
          {{ fieldsMissingFromTarget.join(", ") }}
          {{ fieldsMissingFromTarget.length === 1 ? "isn't" : "aren't" }} in this session's
          registration form, so Livestorm would reject {{ fieldsMissingFromTarget.length === 1 ? "it" : "them" }}.
        </p>
      </div>

      <div class="registrant-table-wrap">
        <table class="registrant-table">
          <thead>
            <tr>
              <th class="action-th"><span class="sr-only">Remove or restore</span></th>
              <th v-for="field in includedFields" :key="field">{{ field }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in transferData.rows" :key="index" :class="{ 'row-removed': excludedRows[index] }">
              <td class="action-td">
                <button
                  v-if="!excludedRows[index]"
                  class="row-action-btn remove"
                  type="button"
                  :aria-label="`Don't import ${row.email}`"
                  :disabled="batch.isBusy"
                  @click="removeRow(index)"
                >✕</button>
                <button
                  v-else
                  class="row-action-btn restore"
                  type="button"
                  :aria-label="`Import ${row.email} again`"
                  :disabled="batch.isBusy"
                  @click="restoreRow(index)"
                >↩</button>
              </td>
              <td v-for="field in includedFields" :key="field">
                {{ row[field] || "" }}
                <span v-if="field === 'email' && isRegistered(row.email)" class="session-status registered-badge">
                  Already registered
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <RegisterCard
      v-if="transferData"
      v-model:extra-session-ids="extraSessionIds"
      :session-id="session.id"
      title="Ready to import?"
      :description="registerDescription"
      :notes="registerNotes"
      button-label="Import now"
      busy-label="Importing…"
      :busy="batch.isBusy"
      :disabled="!newRegistrants.length && !(extraSessionIds.length && registrants.length)"
      @submit="submit"
    />

    <BatchProgress
      :batch="batch"
      running-title="Importing…"
      @new-batch="emit('done')"
      @download-failed="downloadFailedRows"
    />
  </template>
</template>

<style scoped>
.source-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-space-4);
}

.source-summary h2 {
  margin: 0 0 var(--spacing-space-1);
  color: var(--color-text-neutral-base);
  font-size: var(--text-title-sm);
  line-height: var(--text-title-sm--line-height);
  font-weight: var(--text-title-sm--font-weight);
}

.source-summary p {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
}

.source-summary .step-label {
  margin-bottom: var(--spacing-space-2);
}

.source-summary .bar-btn:disabled,
.row-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-line {
  margin: 0 0 var(--spacing-space-4);
  color: var(--color-text-neutral-secondary);
}

.registered-badge {
  margin-left: var(--spacing-space-2);
}

.fields-hint {
  margin: var(--spacing-space-3) 0 0;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}
</style>
