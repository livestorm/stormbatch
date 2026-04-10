<script setup>
import { ref } from "vue";

defineProps({
  selectedFile: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  previewReady: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["file-selected", "preview"]);
const isDragging = ref(false);

function onChange(event) {
  const [file] = event.target.files;
  if (file) {
    event.target.value = "";
  }
  if (file) {
    // The parent keeps the file reference for preview and submission.
    // This avoids any extra client-side parsing logic.
    return file;
  }
  return null;
}

function selectFile(file) {
  if (file) {
    emit("file-selected", file);
  }
}

function onDrop(event) {
  isDragging.value = false;
  const [file] = event.dataTransfer.files;
  selectFile(file);
}
</script>

<template>
  <div class="upload-card">
    <div class="upload-copy">
      <span>Spreadsheet upload</span>
      <strong>Drop in the registrant list</strong>
      <p>StormBatch reads .xlsx or .csv files, trims headers and values, and previews the first rows before anything is sent.</p>
    </div>

    <label
      class="drop-zone"
      :class="{ selected: selectedFile, dragging: isDragging }"
      @dragenter.prevent="isDragging = true"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
    >
      <input
        type="file"
        accept=".xlsx,.csv"
        @change="
          ($event) => {
            const file = onChange($event);
            selectFile(file);
          }
        "
      />
      <span class="file-icon">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </span>
      <strong>{{ selectedFile ? selectedFile.name : "Choose an .xlsx or .csv file" }}</strong>
      <small>
        {{
          selectedFile
            ? "Ready to preview"
            : isDragging
              ? "Release to upload"
              : "Drag and drop here, or click to browse"
        }}
      </small>
    </label>

    <button class="secondary-button" type="button" :disabled="loading || !selectedFile" @click="emit('preview')">
      <span v-if="loading" class="spinner"></span>
      {{ loading ? "Reading file..." : previewReady ? "Refresh preview" : "Detect columns and preview" }}
    </button>
  </div>
</template>

<style scoped>
.upload-card {
  display: grid;
  gap: 16px;
}

.upload-copy span {
  display: inline-flex;
  width: fit-content;
  margin-bottom: 12px;
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

.upload-copy strong {
  display: block;
  color: var(--color-text-neutral-base);
  font-size: var(--text-title-sm);
  line-height: var(--text-title-sm--line-height);
  font-weight: var(--text-title-sm--font-weight);
}

.upload-copy p {
  margin: 6px 0 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md);
  line-height: 1.6;
}

.drop-zone {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 190px;
  padding: 28px 24px;
  text-align: center;
  border: 2px dashed var(--color-borders-neutral-light);
  border-radius: 10px;
  background: var(--color-surface-neutral-100);
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}

.drop-zone:hover {
  border-color: var(--color-borders-primary-default);
  background: var(--color-surface-primary-alpha-100);
  transform: translateY(-1px);
}

.drop-zone.dragging {
  border-color: var(--color-borders-primary-strong);
  background: var(--color-surface-primary-alpha-200);
  transform: translateY(-2px) scale(1.01);
}

.drop-zone.selected {
  border-style: solid;
  border-color: var(--color-borders-primary-default);
  background: var(--color-surface-primary-alpha-100);
}

.drop-zone input {
  display: none;
}

.file-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 10px;
  color: var(--color-text-neutral-complementary-base);
  background: var(--color-actions-primary-idle);
}

.drop-zone small {
  color: var(--color-text-neutral-secondary);
}

.secondary-button {
  display: inline-flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  border: 1px solid transparent;
  background: var(--color-actions-primary-idle);
  color: var(--color-text-neutral-complementary-base);
  border-radius: 8px;
  padding: 13px 16px;
  font-size: var(--text-action-button-md);
  line-height: var(--text-action-button-md--line-height);
  font-weight: var(--text-action-button-md--font-weight);
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.secondary-button:hover:not(:disabled) {
  background: var(--color-actions-primary-idle-alpha-strong);
  box-shadow: 0 0 0 1px var(--color-actions-primary-idle);
}

.secondary-button:disabled {
  color: var(--color-text-neutral-tertiary);
  background: var(--color-surface-neutral-300);
  border-color: var(--color-borders-neutral-light);
  opacity: 1;
  cursor: not-allowed;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--color-actions-neutral-complementary-idle-alpha-strong);
  border-top-color: var(--color-text-neutral-complementary-base);
  border-radius: 8px;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
