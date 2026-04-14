<script setup>
defineProps({
  authenticated: {
    type: Boolean,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

defineEmits(["login", "logout"]);
</script>

<template>
  <div class="connect-block">
    <span class="connect-label">Livestorm account</span>

    <div v-if="loading" class="connect-status loading">
      <span class="status-dot loading-dot"></span>
      <span>Checking connection…</span>
    </div>

    <div v-else-if="authenticated" class="connect-status connected">
      <span class="status-dot connected-dot"></span>
      <span>Connected</span>
      <button class="disconnect-btn" @click="$emit('logout')">Disconnect</button>
    </div>

    <button v-else class="connect-btn" @click="$emit('login')">
      Connect with Livestorm
    </button>
  </div>
</template>

<style scoped>
.connect-block {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.connect-label {
  color: var(--color-text-neutral-tertiary);
  font-size: var(--text-content-legends-bold-md);
  line-height: var(--text-content-legends-bold-md--line-height);
  font-weight: var(--text-content-legends-bold-md--font-weight);
}

.connect-btn {
  width: 100%;
  padding: 12px 14px;
  background: var(--color-surface-primary-base, #5C5BD4);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.connect-btn:hover {
  opacity: 0.88;
}

.connect-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 8px;
  background: var(--color-surface-neutral-100);
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
  color: var(--color-text-neutral-base);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.connected-dot {
  background: #22c55e;
}

.loading-dot {
  background: var(--color-text-neutral-tertiary);
  opacity: 0.5;
}

.disconnect-btn {
  margin-left: auto;
  background: none;
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: var(--text-content-legends-bold-md, 12px);
  color: var(--color-text-neutral-tertiary);
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.disconnect-btn:hover {
  border-color: var(--color-borders-primary-strong);
  color: var(--color-text-neutral-base);
}
</style>
