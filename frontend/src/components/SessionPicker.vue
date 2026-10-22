<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  isSessionId,
  localDayBounds,
  registrantsLabel,
  searchSessions,
  sessionStart,
  statusLabel,
} from "../sessions";

const props = defineProps({
  // "upcoming" lists upcoming and live sessions only; "any" also finds past
  // sessions through title search, ID or date.
  scope: { type: String, default: "upcoming" },
  // Hidden from results, e.g. the target session when picking a source.
  excludeId: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["select"]);

const SEARCH_DEBOUNCE_MS = 300;

const query = ref("");
const date = ref("");
const sessions = ref([]);
const nextPage = ref(null);
const isLoading = ref(false);
const isLoadingMore = ref(false);
const errorMessage = ref("");

let requestSeq = 0;
let debounceTimer = null;

const trimmedQuery = computed(() => query.value.trim());
const isIdQuery = computed(() => isSessionId(trimmedQuery.value));
const visibleSessions = computed(() => sessions.value.filter((s) => s.id !== props.excludeId));
const upcomingWord = computed(() => (props.scope === "upcoming" ? "upcoming " : ""));

const dateLabel = computed(() => {
  if (!date.value) return "";
  const [year, month, day] = date.value.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" })
    .format(new Date(year, month - 1, day));
});

const caption = computed(() => {
  if (isIdQuery.value) return "Session with this ID";
  const onDate = date.value ? ` on ${dateLabel.value}` : "";
  if (trimmedQuery.value) return `Sessions whose event title contains “${trimmedQuery.value}”${onDate}`;
  if (date.value) return `${props.scope === "upcoming" ? "Upcoming sessions" : "Sessions"}${onDate}`;
  return props.scope === "upcoming"
    ? "Upcoming sessions, soonest first"
    : "Upcoming sessions, soonest first. Search by title or ID to find past ones.";
});

const emptyMessage = computed(() => {
  if (isIdQuery.value) {
    return trimmedQuery.value.toLowerCase() === props.excludeId.toLowerCase()
      ? "That's the session you're registering people into. Pick a different one."
      : "No session found with this ID in your workspace.";
  }
  if (trimmedQuery.value) return `No ${upcomingWord.value}sessions match “${trimmedQuery.value}”.`;
  if (date.value) return `No ${upcomingWord.value}sessions on ${dateLabel.value}.`;
  return "No upcoming sessions in this workspace. Schedule one in Livestorm, or paste a session ID above.";
});

async function load({ append = false } = {}) {
  const seq = ++requestSeq;
  errorMessage.value = "";
  if (append) isLoadingMore.value = true;
  else isLoading.value = true;

  try {
    const bounds = date.value ? localDayBounds(date.value) : null;
    const data = await searchSessions({
      query: trimmedQuery.value,
      scope: props.scope,
      dateFrom: bounds?.from ?? null,
      dateTo: bounds?.to ?? null,
      page: append ? nextPage.value : 0,
    });
    // A newer search started while this one was in flight.
    if (seq !== requestSeq) return;
    if (append) {
      const known = new Set(sessions.value.map((s) => s.id));
      sessions.value = [...sessions.value, ...data.sessions.filter((s) => !known.has(s.id))];
    } else {
      sessions.value = data.sessions;
    }
    nextPage.value = data.next_page;
  } catch (error) {
    if (seq !== requestSeq) return;
    errorMessage.value = error.message;
    if (!append) {
      sessions.value = [];
      nextPage.value = null;
    }
  } finally {
    if (seq === requestSeq) {
      isLoading.value = false;
      isLoadingMore.value = false;
    }
  }
}

watch(query, (value) => {
  clearTimeout(debounceTimer);
  // Dim the current results and drop any in-flight answer right away, so the
  // list never shows results for an older query under the new caption.
  requestSeq += 1;
  isLoading.value = true;
  // A pasted ID is complete, so look it up right away.
  debounceTimer = setTimeout(() => load(), isSessionId(value) ? 0 : SEARCH_DEBOUNCE_MS);
});

watch(date, () => load());

onMounted(() => load());
onBeforeUnmount(() => clearTimeout(debounceTimer));
</script>

<template>
  <div class="picker">
    <div class="picker-filters">
      <label class="picker-search">
        <span class="sr-only">Search by event title or session ID</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          v-model="query"
          type="search"
          placeholder="Search by event title or paste a session ID"
          autocomplete="off"
          spellcheck="false"
        />
      </label>
      <label class="picker-date">
        <span class="sr-only">Session date</span>
        <input v-model="date" type="date" />
      </label>
      <button v-if="date" class="link-button" type="button" @click="date = ''">Any date</button>
    </div>

    <p class="picker-caption" role="status">
      {{ isLoading && !isLoadingMore ? "Loading sessions…" : caption }}
    </p>

    <div v-if="errorMessage" class="notice error picker-error">
      <span>{{ errorMessage }}</span>
      <button class="bar-btn" type="button" @click="load()">Try again</button>
    </div>

    <ul v-if="isLoading && !visibleSessions.length" class="picker-list" aria-hidden="true">
      <li v-for="n in 3" :key="n" class="session-row skeleton">
        <span class="session-date-tile"></span>
        <span class="skeleton-lines"><span></span><span></span></span>
      </li>
    </ul>

    <ul v-else-if="visibleSessions.length" class="picker-list" :class="{ stale: isLoading }">
      <li v-for="session in visibleSessions" :key="session.id">
        <button
          class="session-row"
          type="button"
          :disabled="disabled"
          @click="emit('select', session)"
        >
          <span class="session-date-tile">
            <template v-if="sessionStart(session)">
              <span class="session-date-weekday">{{ sessionStart(session).weekday }}</span>
              <span class="session-date-day">{{ sessionStart(session).day }}</span>
              <span class="session-date-time">{{ sessionStart(session).time }}</span>
            </template>
            <span v-else class="session-date-time">No date</span>
          </span>
          <span class="session-main">
            <span class="session-title">{{ session.title }}</span>
            <span class="session-meta">
              <span
                v-if="session.status && session.status !== 'upcoming'"
                class="session-status"
                :class="`status-${session.status}`"
              >{{ statusLabel(session.status) }}</span>
              <span v-if="session.name" class="meta-item">{{ session.name }}</span>
              <span class="meta-item">{{ registrantsLabel(session.registrants_count) }}</span>
            </span>
          </span>
          <svg class="session-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
        </button>
      </li>
    </ul>

    <p v-else-if="!errorMessage" class="picker-empty">{{ emptyMessage }}</p>

    <button
      v-if="nextPage !== null && !errorMessage && !isLoading"
      class="bar-btn picker-more"
      type="button"
      :disabled="isLoadingMore"
      @click="load({ append: true })"
    >
      {{ isLoadingMore ? "Loading…" : "Load more sessions" }}
    </button>
  </div>
</template>

<style scoped>
.picker {
  display: grid;
  gap: var(--spacing-space-4);
}

.picker-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-space-3);
}

.picker-search {
  flex: 1 1 320px;
  display: flex;
  align-items: center;
  gap: var(--spacing-space-2);
  padding: 0 var(--spacing-space-3);
  border: 1px solid var(--color-borders-neutral-default);
  border-radius: var(--spacing-rounded-lg);
  background: var(--color-surface-neutral-100);
  color: var(--color-text-neutral-tertiary);
  transition: border-color 0.15s ease;
}

.picker-search:focus-within,
.picker-date input:focus {
  border-color: var(--color-borders-primary-strong);
}

.picker-search input {
  flex: 1;
  min-width: 0;
  padding: var(--spacing-space-3) 0;
  border: none;
  background: transparent;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
}

.picker-search input:focus-visible {
  outline: none;
}

.picker-search input::placeholder {
  color: var(--color-text-neutral-tertiary);
}

.picker-date input {
  padding: var(--spacing-space-3);
  border: 1px solid var(--color-borders-neutral-default);
  border-radius: var(--spacing-rounded-lg);
  background: var(--color-surface-neutral-100);
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
  color-scheme: dark;
}

.picker-caption,
.picker-empty {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.picker-empty {
  padding: var(--spacing-space-6) 0;
  text-align: center;
  font-size: var(--text-content-text-regular-md);
}

.picker-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-space-3);
  margin: 0;
}

.picker-list {
  display: grid;
  gap: var(--spacing-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
  transition: opacity 0.15s ease;
}

.picker-list.stale {
  opacity: 0.5;
}

.session-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--spacing-space-4);
  width: 100%;
  padding: var(--spacing-space-2);
  padding-right: var(--spacing-space-4);
  border: none;
  border-radius: var(--spacing-rounded-lg);
  background: var(--color-surface-neutral-100);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.session-row:hover:not(:disabled) {
  background-image: linear-gradient(
    var(--color-actions-neutral-hover-overlay),
    var(--color-actions-neutral-hover-overlay)
  );
}

.session-row:disabled {
  cursor: progress;
  opacity: 0.6;
}

.session-main {
  display: grid;
  gap: var(--spacing-space-1);
  min-width: 0;
}

.session-title {
  overflow: hidden;
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-md);
  line-height: var(--text-content-text-bold-md--line-height);
  font-weight: var(--text-content-text-bold-md--font-weight);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-space-2);
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-legends-regular-md);
  line-height: var(--text-content-legends-regular-md--line-height);
}

.meta-item + .meta-item::before {
  content: "·";
  margin-right: var(--spacing-space-2);
  color: var(--color-text-neutral-tertiary);
}

.session-chevron {
  color: var(--color-text-neutral-tertiary);
}

.skeleton {
  cursor: default;
}

.skeleton .session-date-tile {
  height: 64px;
}

.skeleton-lines {
  display: grid;
  gap: var(--spacing-space-2);
}

.skeleton-lines span {
  height: 12px;
  width: 60%;
  border-radius: var(--spacing-rounded-sm);
  background: var(--color-surface-neutral-300);
}

.skeleton-lines span + span {
  width: 30%;
}

@media (prefers-reduced-motion: no-preference) {
  .skeleton .session-date-tile,
  .skeleton-lines span {
    animation: pulse 1.4s ease-in-out infinite;
  }
}

@keyframes pulse {
  50% {
    opacity: 0.5;
  }
}

.picker-more {
  justify-self: center;
}

@media (max-width: 540px) {
  .picker-date {
    flex: 1 1 auto;
  }

  .picker-date input {
    width: 100%;
  }
}
</style>
