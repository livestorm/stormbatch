<script setup>
import { computed, ref, watch } from "vue";
import BatchProgress from "./BatchProgress.vue";
import FileUpload from "./FileUpload.vue";
import PreviewTable from "./PreviewTable.vue";
import RegisterCard from "./RegisterCard.vue";
import { requestJson } from "../api";
import { BULK_JOB_CHUNK_SIZE, countJobs, useBatchJobs } from "../composables/useBatchJobs";
import { useRegisteredEmails } from "../composables/useRegisteredEmails";
import { downloadCsv, fileSlug } from "../csv";
import { peopleLabel } from "../sessions";

const props = defineProps({
  // Session detail from /api/sessions/{id}, including its form fields.
  session: { type: Object, required: true },
});

const emit = defineEmits(["busy-change", "done"]);

const selectedFile = ref(null);
const preview = ref(null);
const columnSettings = ref([]); // [{ column, attributeId }]; "" means the column isn't sent
const isPreviewLoading = ref(false);
const errorMessage = ref("");
const noticeMessage = ref("");
const extraSessionIds = ref([]);
const batch = useBatchJobs();
const { checkRegistered, isRegistered, registeredCheckNote } = useRegisteredEmails(props.session);

watch(() => batch.isBusy, (busy) => emit("busy-change", busy));

// ── Form fields ──────────────────────────────────────────────────────────────

// Email is implicit in every registration form and not always listed.
const formFieldIds = computed(() => props.session.fields.map((f) => f.id));
const canCheckFields = computed(() => formFieldIds.value.length > 0);
const validFieldIds = computed(() => new Set(["email", ...formFieldIds.value]));
const fieldOptions = computed(() => ["email", ...formFieldIds.value.filter((id) => id !== "email")]);

// ── Mapping state ────────────────────────────────────────────────────────────

const mapping = computed(() =>
  Object.fromEntries(
    columnSettings.value.filter((c) => c.attributeId).map((c) => [c.column, c.attributeId]),
  ),
);
const mappedIds = computed(() => Object.values(mapping.value));
const emailColumn = computed(
  () => columnSettings.value.find((c) => c.attributeId === "email")?.column || "",
);
const duplicateFieldIds = computed(() => [
  ...new Set(mappedIds.value.filter((id, i) => mappedIds.value.indexOf(id) !== i)),
]);
const duplicateEmails = computed(() =>
  emailColumn.value ? preview.value?.duplicate_email_columns[emailColumn.value] || [] : [],
);
const unmappedRequiredFields = computed(() =>
  props.session.fields.filter((f) => f.required && f.id !== "email" && !mappedIds.value.includes(f.id)),
);

const mappingProblem = computed(() => {
  if (!preview.value) return "";
  if (!emailColumn.value) return "Choose which column holds the email addresses.";
  if (!preparedRows.value.registrants.length) return `No row has an email in the ${emailColumn.value} column.`;
  if (duplicateFieldIds.value.length) {
    return `Each field can only be filled by one column: ${duplicateFieldIds.value.join(", ")}.`;
  }
  return "";
});

function columnState(item) {
  if (!item.attributeId) return "dropped";
  if (duplicateFieldIds.value.includes(item.attributeId)) return "duplicate";
  return "valid";
}

const COLUMN_STATUS = {
  dropped: "Not sent",
  duplicate: "Used twice",
  valid: "Will be sent",
};

function sampleValue(column) {
  return preview.value?.rows.slice(0, 5).find((row) => row[column])?.[column] || "";
}

function setAttribute(index, value) {
  columnSettings.value = columnSettings.value.map((c, i) =>
    i === index ? { ...c, attributeId: value.trim() } : c,
  );
}

// Map each column to the form field its header names, each field at most once.
function initialColumnSettings(data) {
  const used = new Set();
  return data.headers.map((header) => {
    const candidates = [data.normalized_headers[header], data.suggestions[header]].filter(Boolean);
    if (!canCheckFields.value) return { column: header, attributeId: candidates[0] || "" };
    const match = candidates.find((id) => validFieldIds.value.has(id) && !used.has(id)) || "";
    if (match) used.add(match);
    return { column: header, attributeId: match };
  });
}

// ── File handling ────────────────────────────────────────────────────────────

function onFileSelected(file) {
  selectedFile.value = file;
  preview.value = null;
  columnSettings.value = [];
  batch.reset();
  loadPreview();
}

async function loadPreview() {
  if (!selectedFile.value) return;
  errorMessage.value = "";
  noticeMessage.value = "";
  isPreviewLoading.value = true;
  try {
    const formData = new FormData();
    formData.append("file", selectedFile.value);
    const data = await requestJson("/api/preview", {
      method: "POST",
      body: formData,
      fallbackMessage: "We couldn't read this file. Check that it's a valid .xlsx or .csv file.",
    });
    preview.value = data;
    columnSettings.value = initialColumnSettings(data);
    checkRegistered();
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isPreviewLoading.value = false;
  }
}

// ── Rows to send ─────────────────────────────────────────────────────────────

// Every row with an email, as registrants; rows without one are reported.
const preparedRows = computed(() => {
  const registrants = [];
  const rowsWithoutEmail = [];
  if (!preview.value || !emailColumn.value) return { registrants, rowsWithoutEmail };
  const mapped = Object.entries(mapping.value);
  preview.value.rows.forEach((row, index) => {
    const rowNumber = index + 2; // row 1 holds the headers
    const email = (row[emailColumn.value] || "").trim();
    if (!email) {
      rowsWithoutEmail.push(rowNumber);
      return;
    }
    registrants.push({
      fields: mapped
        .map(([column, id]) => ({ id, value: (row[column] || "").trim() }))
        .filter((field) => field.value),
      row_result: {
        row_number: rowNumber,
        email,
        source_index: index,
        fields: mapped.map(([column, id]) => ({ column, attribute_id: id, value: row[column] || "" })),
      },
    });
  });
  return { registrants, rowsWithoutEmail };
});

// People already registered to this session are skipped for it, but still
// sent to any other session added on the register card.
const newRegistrants = computed(() =>
  preparedRows.value.registrants.filter((r) => !isRegistered(r.row_result.email)),
);
const alreadyRegisteredCount = computed(
  () => preparedRows.value.registrants.length - newRegistrants.value.length,
);

function rowList(numbers) {
  const shown = numbers.slice(0, 5).join(", ");
  return numbers.length > 5 ? `${shown} and ${numbers.length - 5} more` : shown;
}

const registerNotes = computed(() => {
  const notes = [];
  const { rowsWithoutEmail } = preparedRows.value;
  if (rowsWithoutEmail.length) {
    const one = rowsWithoutEmail.length === 1;
    notes.push(`${one ? "Row" : "Rows"} ${rowList(rowsWithoutEmail)} ${one ? "has" : "have"} no email and will be skipped.`);
  }
  if (alreadyRegisteredCount.value) {
    notes.push(`${peopleLabel(alreadyRegisteredCount.value)} already registered to this session will be skipped.`);
  }
  if (registeredCheckNote.value) notes.push(registeredCheckNote.value);
  return notes;
});

const registerDescription = computed(() => {
  const count = newRegistrants.value.length;
  if (!count) return "Everyone in this file is already registered to this session.";
  const jobs = countJobs(count);
  return `${peopleLabel(count)} will be registered in ${jobs} batch${jobs === 1 ? "" : "es"} of up to ${BULK_JOB_CHUNK_SIZE}.`;
});

async function submit(targetSessionIds) {
  errorMessage.value = "";
  noticeMessage.value = "";
  if (mappingProblem.value) {
    errorMessage.value = mappingProblem.value;
    return;
  }
  const targets = targetSessionIds
    .map((sessionId) => ({
      sessionId,
      registrants: sessionId === props.session.id ? newRegistrants.value : preparedRows.value.registrants,
    }))
    .filter((target) => target.registrants.length);
  try {
    await batch.run({ targets, fallbackMessage: "Registration failed." });
    if (duplicateEmails.value.length) {
      noticeMessage.value = "The file has duplicate emails, so Livestorm may have rejected some rows.";
    }
  } catch (error) {
    errorMessage.value = error.message;
  }
}

// ── Downloads ────────────────────────────────────────────────────────────────

function downloadTemplate() {
  // Headers are the form's field IDs, so the columns map themselves on upload.
  downloadCsv(`stormbatch-template-${fileSlug(props.session.title)}.csv`, fieldOptions.value, []);
}

function downloadFailedRows(rows) {
  const headers = preview.value.headers;
  const severalSessions = new Set(rows.map((r) => r.sessionId)).size > 1;
  downloadCsv(
    `stormbatch-failed-rows-${fileSlug(props.session.title)}.csv`,
    [...headers, "stormbatch_error", ...(severalSessions ? ["stormbatch_session_id"] : [])],
    rows.map(({ sessionId, row, error }) => [
      ...headers.map((header) => preview.value.rows[row.source_index]?.[header] ?? ""),
      error,
      ...(severalSessions ? [sessionId] : []),
    ]),
  );
}
</script>

<template>
  <section class="panel">
    <FileUpload
      :selected-file="selectedFile"
      :loading="isPreviewLoading"
      :preview-ready="Boolean(preview)"
      @file-selected="onFileSelected"
      @preview="loadPreview"
    />
    <p v-if="canCheckFields" class="template-hint">
      Starting from scratch?
      <button class="link-button" type="button" @click="downloadTemplate">Download a template</button>
      with this session's registration fields.
    </p>
  </section>

  <section v-if="errorMessage" class="notice error centered-notice" role="alert">{{ errorMessage }}</section>

  <section v-if="preview" class="panel preview-panel">
    <div class="panel-header">
      <div>
        <span class="step-label">Columns</span>
        <h2>Match your columns</h2>
        <p>
          {{ preview.row_count }} rows · {{ preview.headers.length }} columns.
          <template v-if="canCheckFields">Fields come from this session's registration form.</template>
        </p>
      </div>
      <div class="preview-statuses">
        <div class="status-pill" :class="{ ok: emailColumn, error: !emailColumn }">
          {{ emailColumn ? `Email: ${emailColumn}` : "No email column chosen" }}
        </div>
        <div v-if="duplicateEmails.length" class="warning-pill">
          Duplicate emails: {{ duplicateEmails.join(", ") }}
        </div>
      </div>
    </div>

    <div v-if="!canCheckFields" class="notice warning">
      We couldn't read this session's registration form, so field IDs can't be checked.
      Use Livestorm field IDs with underscores, such as <code>first_name</code>.
    </div>

    <div class="mapping-check-list">
      <div
        v-for="(item, idx) in columnSettings"
        :key="item.column"
        class="mapping-check-row"
        :class="{
          'check-valid': columnState(item) === 'valid',
          'check-invalid': columnState(item) === 'duplicate',
          'check-dropped': columnState(item) === 'dropped',
        }"
      >
        <span class="check-icon">
          <svg v-if="columnState(item) === 'valid'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <svg v-else-if="columnState(item) !== 'dropped'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </span>
        <span class="check-column">
          {{ item.column }}
          <small v-if="sampleValue(item.column)" class="check-sample">{{ sampleValue(item.column) }}</small>
        </span>
        <span class="check-arrow" aria-hidden="true">→</span>
        <select
          v-if="canCheckFields"
          class="check-attr-select"
          :value="item.attributeId"
          :aria-label="`Livestorm field for the ${item.column} column`"
          @change="setAttribute(idx, $event.target.value)"
        >
          <option value="">Don't send</option>
          <option v-for="id in fieldOptions" :key="id" :value="id">{{ id }}</option>
        </select>
        <input
          v-else
          class="check-attr-input"
          :value="item.attributeId"
          placeholder="field_id (empty = don't send)"
          :aria-label="`Livestorm field ID for the ${item.column} column`"
          @change="setAttribute(idx, $event.target.value)"
        />
        <span class="check-status">{{ COLUMN_STATUS[columnState(item)] }}</span>
      </div>
    </div>

    <div v-if="canCheckFields" class="available-fields-block">
      <span class="available-fields-label">Registration form fields</span>
      <div class="available-fields-list">
        <span
          v-for="field in session.fields"
          :key="field.id"
          class="session-field-chip"
          :class="{ 'chip-required': field.required, 'chip-mapped': mappedIds.includes(field.id) }"
        >
          {{ field.id }}<em v-if="field.required"> · req.</em>
        </span>
      </div>
      <p v-if="unmappedRequiredFields.length" class="fields-hint">
        Livestorm only needs an email to register someone. People fill in missing required fields
        ({{ unmappedRequiredFields.map((f) => f.id).join(", ") }}) before they join.
      </p>
    </div>

    <PreviewTable :headers="preview.headers" :rows="preview.rows.slice(0, 5)" />
  </section>

  <RegisterCard
    v-if="preview"
    v-model:extra-session-ids="extraSessionIds"
    :session-id="session.id"
    title="Ready to register?"
    :description="registerDescription"
    :notes="registerNotes"
    :warning="mappingProblem"
    button-label="Register now"
    busy-label="Registering…"
    :busy="batch.isBusy"
    :disabled="Boolean(mappingProblem) || (!newRegistrants.length && !extraSessionIds.length)"
    @submit="submit"
  />

  <section v-if="noticeMessage" class="notice warning centered-notice">{{ noticeMessage }}</section>

  <BatchProgress
    :batch="batch"
    running-title="Registering…"
    @new-batch="emit('done')"
    @download-failed="downloadFailedRows"
  />
</template>

<style scoped>
.check-column {
  display: grid;
  gap: var(--spacing-space-0-5);
  flex: 0 0 220px;
  min-width: 0;
}

.check-sample {
  overflow: hidden;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-regular-md);
  font-weight: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.check-attr-select {
  flex: 1;
  min-width: 0;
  max-width: 280px;
  padding: var(--spacing-space-1-5) var(--spacing-space-2);
  border: 1px solid var(--color-borders-neutral-default);
  border-radius: var(--spacing-rounded-md);
  background: var(--color-surface-neutral-100);
  color: var(--color-text-neutral-base);
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 0.875em;
  color-scheme: dark;
  cursor: pointer;
}

.check-attr-select:focus {
  border-color: var(--color-borders-primary-strong);
}

.check-status {
  margin-left: auto;
}

.template-hint {
  margin: var(--spacing-space-4) 0 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
}

.template-hint .link-button {
  font-size: inherit;
}

.fields-hint {
  margin: var(--spacing-space-3) 0 0;
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.available-fields-block {
  margin-bottom: var(--spacing-space-6);
}

@media (max-width: 640px) {
  .mapping-check-row {
    flex-wrap: wrap;
  }

  .check-column {
    flex: 1 1 calc(100% - 32px);
  }

  .check-arrow {
    display: none;
  }

  .check-attr-select {
    flex: 1 1 auto;
    max-width: none;
  }
}
</style>
