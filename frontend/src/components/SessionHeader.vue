<script setup>
import { computed, ref } from "vue";
import { registrantsLabel, sessionStart, statusLabel } from "../sessions";

const props = defineProps({
  session: { type: Object, required: true },
  canChange: { type: Boolean, default: true },
});

const emit = defineEmits(["change"]);

const start = computed(() => sessionStart(props.session));
const copied = ref(false);

async function copyId() {
  try {
    await navigator.clipboard.writeText(props.session.id);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1500);
  } catch {
    // Clipboard access can be denied; the ID stays selectable.
  }
}
</script>

<template>
  <section class="panel session-header" aria-label="Selected session">
    <span class="session-date-tile">
      <template v-if="start">
        <span class="session-date-weekday">{{ start.weekday }}</span>
        <span class="session-date-day">{{ start.day }}</span>
        <span class="session-date-time">{{ start.time }}</span>
      </template>
      <span v-else class="session-date-time">No date</span>
    </span>

    <div class="session-header-main">
      <h2>{{ session.title }}</h2>
      <p class="session-header-meta">
        <span
          v-if="session.status && session.status !== 'upcoming'"
          class="session-status"
          :class="`status-${session.status}`"
        >{{ statusLabel(session.status) }}</span>
        <span v-if="session.name">{{ session.name }}</span>
        <span>{{ registrantsLabel(session.registrants_count) }}</span>
        <span class="session-header-id">
          <code>{{ session.id }}</code>
          <button class="link-button" type="button" @click="copyId">
            {{ copied ? "Copied" : "Copy ID" }}
          </button>
        </span>
      </p>
    </div>

    <button class="bar-btn" type="button" :disabled="!canChange" @click="emit('change')">
      Change session
    </button>
  </section>
</template>

<style scoped>
.session-header {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--spacing-space-4);
}

.session-header-main {
  display: grid;
  gap: var(--spacing-space-1);
  min-width: 0;
}

.session-header-main h2 {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-neutral-base);
  font-size: var(--text-title-sm);
  line-height: var(--text-title-sm--line-height);
  font-weight: var(--text-title-sm--font-weight);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-header-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-space-1) var(--spacing-space-3);
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.session-header-id {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-space-2);
  min-width: 0;
}

.session-header-id code {
  overflow: hidden;
  color: var(--color-text-neutral-tertiary);
  font-family: ui-monospace, "SFMono-Regular", monospace;
  text-overflow: ellipsis;
}

.session-header-id .link-button {
  font-size: inherit;
}

.bar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 640px) {
  .session-header {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .session-header > .bar-btn {
    grid-column: 1 / -1;
    justify-self: start;
  }
}
</style>
