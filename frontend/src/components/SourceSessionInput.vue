<script setup>
defineProps({
  modelValue: {
    type: String,
    default: "",
  },
  loading: {
    type: Boolean,
    default: false,
  },
  fetchedCount: {
    type: Number,
    default: null,
  },
  label: {
    type: String,
    default: "Source session ID",
  },
  buttonLabel: {
    type: String,
    default: "Fetch registrants",
  },
  fetchedNoun: {
    type: String,
    default: "registrant",
  },
});

defineEmits(["update:modelValue", "fetch"]);
</script>

<template>
  <div class="source-session-block">
    <label class="source-label">{{ label }}</label>
    <div class="source-input-row">
      <input
        :value="modelValue"
        type="text"
        placeholder="e.g. 91ca6a71-a2a0-4d8f-9ef8-828c1fa70a4a"
        :disabled="loading"
        @input="$emit('update:modelValue', $event.target.value)"
        @keyup.enter="$emit('fetch')"
      />
      <button
        class="fetch-btn"
        type="button"
        :disabled="loading || !modelValue.trim()"
        @click="$emit('fetch')"
      >
        {{ loading ? "Fetching…" : buttonLabel }}
      </button>
    </div>
    <div v-if="fetchedCount !== null" class="fetch-badge">
      <span class="dot"></span>
      {{ fetchedCount }} {{ fetchedNoun }}{{ fetchedCount === 1 ? "" : "s" }} found
    </div>
  </div>
</template>

<style scoped>
.source-session-block {
  display: grid;
  gap: 8px;
}

.source-label {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.source-input-row {
  display: grid;
  gap: 8px;
}

.source-input-row input {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  padding: 10px 12px;
  color: var(--color-text-neutral-base);
  background: var(--color-surface-neutral-100);
  font-size: var(--text-content-text-regular-md, 14px);
  line-height: 1.5;
  font-family: ui-monospace, "SFMono-Regular", monospace;
}

.source-input-row input::placeholder {
  color: var(--color-text-neutral-tertiary);
  font-family: inherit;
}

.source-input-row input:focus {
  border-color: var(--color-borders-primary-strong);
  outline: none;
}

.source-input-row input:disabled {
  opacity: 0.6;
}

.fetch-btn {
  justify-self: end;
  padding: 10px 20px;
  border-radius: 8px;
  background: var(--color-actions-primary-idle);
  color: var(--color-text-neutral-complementary-base);
  border: none;
  font-size: var(--text-action-button-md);
  line-height: var(--text-action-button-md--line-height);
  font-weight: var(--text-action-button-md--font-weight);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease;
}

.fetch-btn:hover:not(:disabled) {
  background: var(--color-actions-primary-idle-alpha-strong);
}

.fetch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.fetch-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #F3FCFB;
  border: 1px solid #DFF7F3;
  color: #0C7C59;
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0C7C59;
  flex-shrink: 0;
}
</style>
