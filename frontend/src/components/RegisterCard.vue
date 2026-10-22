<script setup>
import { computed, ref } from "vue";
import SessionIdsInput from "./SessionIdsInput.vue";
import { isSessionId } from "../sessions";

const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: "" },
  // What will be skipped and why, one sentence each.
  notes: { type: Array, default: () => [] },
  warning: { type: String, default: "" },
  buttonLabel: { type: String, required: true },
  busyLabel: { type: String, required: true },
  busy: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  // The selected session; extra sessions are optional additional targets.
  sessionId: { type: String, required: true },
});

const emit = defineEmits(["submit"]);

const extraSessionIds = defineModel("extraSessionIds", { type: Array, default: () => [] });
const showExtra = ref(extraSessionIds.value.length > 0);

const invalidExtraIds = computed(() => extraSessionIds.value.filter((id) => !isSessionId(id)));

const targetSessionIds = computed(() => [
  props.sessionId,
  ...extraSessionIds.value.filter((id) => id !== props.sessionId && isSessionId(id)),
]);

function toggleExtra() {
  showExtra.value = !showExtra.value;
  // Hidden IDs must not be submitted.
  if (!showExtra.value) extraSessionIds.value = [];
}

function submit() {
  if (invalidExtraIds.value.length) return;
  emit("submit", targetSessionIds.value);
}
</script>

<template>
  <section class="cta-card">
    <div class="register-copy">
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
      <ul v-if="notes.length" class="register-notes">
        <li v-for="note in notes" :key="note">{{ note }}</li>
      </ul>
      <p v-if="warning" class="invalid-mapping-warning">{{ warning }}</p>

      <button
        class="link-button extra-toggle"
        type="button"
        :aria-expanded="showExtra"
        :disabled="busy"
        @click="toggleExtra"
      >
        {{ showExtra ? "Register into this session only" : "Also register into other sessions" }}
      </button>
      <div v-if="showExtra" class="extra-sessions">
        <SessionIdsInput v-model="extraSessionIds" label="Other session IDs" />
        <p v-if="invalidExtraIds.length" class="invalid-mapping-warning">
          Remove or fix the highlighted IDs before registering.
        </p>
      </div>
    </div>
    <div class="cta-actions">
      <button
        class="primary-button"
        type="button"
        :disabled="busy || disabled || (showExtra && invalidExtraIds.length > 0)"
        @click="submit"
      >
        {{ busy ? busyLabel : buttonLabel }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.register-copy {
  display: grid;
  gap: var(--spacing-space-2);
  justify-items: start;
}

.register-copy h2,
.register-copy p {
  margin: 0;
}

.register-notes {
  display: grid;
  gap: var(--spacing-space-1);
  margin: 0;
  padding-left: var(--spacing-space-4);
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.extra-toggle {
  margin-top: var(--spacing-space-2);
}

.extra-sessions {
  width: 100%;
}
</style>
