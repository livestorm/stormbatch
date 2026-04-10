<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  count: {
    type: Number,
    default: 0,
  },
});

defineEmits(["update:modelValue"]);
</script>

<template>
  <label class="field session-field">
    <div class="field-heading">
      <span>Session IDs</span>
      <strong>{{ count }}</strong>
    </div>
    <textarea
      :value="modelValue"
      rows="4"
      placeholder="91ca6a71-a2a0-4d8f-9ef8-828c1fa70a4a&#10;872bbcfa-96cd-4f8f-99e9-f60cf4582917"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <small>Paste one per line or comma-separated. We will create one Livestorm job per session.</small>
  </label>
</template>

<style scoped>
.field {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.field-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.field-heading span {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.field-heading strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 24px;
  padding: 0 8px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 6px;
  background: var(--color-actions-neutral-hover-overlay);
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

textarea {
  width: 100%;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  padding: 14px 16px;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
  resize: vertical;
  background: var(--color-surface-neutral-100);
  box-shadow: none;
}

textarea::placeholder {
  color: var(--color-text-neutral-tertiary);
}

textarea:focus {
  border-color: var(--color-borders-primary-strong);
}

small {
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}
</style>
