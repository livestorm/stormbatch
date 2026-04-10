<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true,
  },
});

defineEmits(["update:modelValue"]);
</script>

<template>
  <label class="field">
    <span>Livestorm API key</span>
    <input
      :value="modelValue"
      type="password"
      placeholder="Paste your API key"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  </label>
</template>

<style scoped>
.field {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

span {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

input {
  width: 100%;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  padding: 12px 14px;
  color: var(--color-text-neutral-base);
  background: var(--color-surface-neutral-100);
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
}

input::placeholder {
  color: var(--color-text-neutral-tertiary);
}
</style>
