<script setup>
defineProps({
  registrantsCount: { type: Number, default: 0 },
});

const emit = defineEmits(["choose"]);
</script>

<template>
  <section class="panel">
    <h2 class="step-heading">What do you want to do with this session?</h2>

    <div class="action-grid">
      <button class="action-card" type="button" @click="emit('choose', 'upload')">
        <span class="action-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 12 15 15"/></svg>
        </span>
        <span class="action-title">Upload a spreadsheet</span>
        <span class="action-desc">Register people from an .xlsx or .csv file.</span>
      </button>

      <button class="action-card" type="button" @click="emit('choose', 'import')">
        <span class="action-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </span>
        <span class="action-title">Import from another session</span>
        <span class="action-desc">Register the people already registered to another Livestorm session.</span>
      </button>
    </div>

    <p class="action-secondary">
      <template v-if="registrantsCount">
        Need to fix existing registrations?
        <button class="link-button" type="button" @click="emit('choose', 'contacts')">
          Edit this session's registrants
        </button>
      </template>
      <template v-else>Nobody is registered to this session yet.</template>
    </p>
  </section>
</template>

<style scoped>
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--spacing-space-4);
}

.action-card {
  display: grid;
  justify-items: start;
  align-content: start;
  gap: var(--spacing-space-2);
  padding: var(--spacing-space-6);
  border: none;
  border-radius: var(--spacing-rounded-lg);
  background: var(--color-surface-neutral-100);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.12s ease;
}

.action-card:hover {
  background-image: linear-gradient(
    var(--color-actions-neutral-hover-overlay),
    var(--color-actions-neutral-hover-overlay)
  );
}

.action-icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  margin-bottom: var(--spacing-space-2);
  border-radius: var(--spacing-rounded-md);
  background: var(--color-actions-primary-idle-alpha-light);
  color: var(--color-text-primary-base);
}

.action-title {
  color: var(--color-text-neutral-base);
  font-size: var(--text-content-text-bold-lg);
  line-height: var(--text-content-text-bold-lg--line-height);
  font-weight: var(--text-content-text-bold-lg--font-weight);
}

.action-desc {
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
}

.action-secondary {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--spacing-space-2);
  margin: var(--spacing-space-6) 0 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md);
  line-height: var(--text-content-text-regular-md--line-height);
}
</style>
