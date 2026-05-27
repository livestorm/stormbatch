<script setup>
import { ref } from "vue";

const props = defineProps({
  modelValue: { type: Array, required: true },
});
const emit = defineEmits(["update:modelValue"]);

const inputValue = ref("");
const inputRef = ref(null);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValid(id) {
  return UUID_RE.test(id);
}

function addTokens(raw) {
  const tokens = raw
    .split(/[\s,\n]+/)
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s && !props.modelValue.includes(s));
  if (tokens.length) emit("update:modelValue", [...props.modelValue, ...tokens]);
}

function confirm() {
  const v = inputValue.value.trim();
  if (!v) return;
  addTokens(v);
  inputValue.value = "";
}

function onKeydown(e) {
  if (e.key === "Enter" || e.key === "Tab" || e.key === ",") {
    e.preventDefault();
    confirm();
  } else if (
    e.key === "Backspace" &&
    !inputValue.value &&
    props.modelValue.length > 0
  ) {
    emit("update:modelValue", props.modelValue.slice(0, -1));
  }
}

function onPaste(e) {
  e.preventDefault();
  const text = (e.clipboardData || window.clipboardData).getData("text");
  addTokens(inputValue.value + text);
  inputValue.value = "";
}

function remove(index) {
  const next = [...props.modelValue];
  next.splice(index, 1);
  emit("update:modelValue", next);
}

function focusInput() {
  inputRef.value?.focus();
}
</script>

<template>
  <div class="session-field">
    <div class="field-row">
      <span class="field-label">Session IDs</span>
      <span v-if="modelValue.length" class="count-badge">{{ modelValue.length }}</span>
    </div>

    <div class="tag-box" @click="focusInput">
      <div
        v-for="(id, i) in modelValue"
        :key="id"
        class="tag"
        :class="{ invalid: !isValid(id) }"
        :title="id"
      >
        <code class="tag-id">{{ id }}</code>
        <button class="tag-remove" type="button" @click.stop="remove(i)" aria-label="Remove">
          <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="1" y1="1" x2="11" y2="11"/><line x1="11" y1="1" x2="1" y2="11"/></svg>
        </button>
      </div>
      <input
        ref="inputRef"
        v-model="inputValue"
        class="tag-input"
        :placeholder="modelValue.length === 0 ? 'Paste or type a session ID…' : 'Add another…'"
        @keydown="onKeydown"
        @paste="onPaste"
        @blur="confirm"
      />
    </div>

    <p class="hint">Paste one or several IDs — we'll split them automatically.</p>
  </div>
</template>

<style scoped>
.session-field {
  display: grid;
  gap: 8px;
}

.field-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  font-weight: var(--text-content-legends-bold-md--font-weight);
  line-height: var(--text-content-legends-bold-md--line-height);
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 20px;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1px solid var(--color-borders-primary-light);
  color: var(--color-actions-primary-idle);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
}

.tag-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 52px;
  padding: 10px 12px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 10px;
  background: var(--color-surface-neutral-100);
  cursor: text;
  transition: border-color 0.15s ease;
}

.tag-box:focus-within {
  border-color: var(--color-borders-primary-strong);
}

.tag {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 7px;
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  transition: border-color 0.12s ease;
}

.tag.invalid {
  background: var(--color-surface-danger-300);
  border-color: var(--color-borders-danger-light);
}

.tag-id {
  font-family: ui-monospace, "SFMono-Regular", "Fira Code", monospace;
  font-size: 12px;
  color: var(--color-text-neutral-base);
  word-break: break-all;
  flex: 1;
  line-height: 1.4;
}

.tag.invalid .tag-id {
  color: var(--color-text-danger-secondary);
}

.tag-remove {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 5px;
  border: none;
  background: transparent;
  color: var(--color-text-neutral-tertiary);
  cursor: pointer;
  transition: background 0.12s ease, color 0.12s ease;
}

.tag-remove:hover {
  background: var(--color-actions-neutral-hover-overlay);
  color: var(--color-text-neutral-base);
}

.tag-input {
  width: 100%;
  min-width: 120px;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-regular-md, 14px);
  line-height: 1.5;
  padding: 2px 0;
}

.tag-input::placeholder {
  color: var(--color-text-neutral-tertiary);
}

.hint {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}
</style>
