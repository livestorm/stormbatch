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
      <span class="status-text">Checking connection…</span>
    </div>

    <div v-else-if="authenticated" class="connect-status connected">
      <span class="status-dot connected-dot"></span>
      <span class="status-text">Connected</span>
      <button class="disconnect-btn" @click="$emit('logout')">Disconnect</button>
    </div>

    <button v-else class="connect-btn" @click="$emit('login')">
      <svg class="btn-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 1.5a6.5 6.5 0 110 13 6.5 6.5 0 010-13zm.75 3.25a.75.75 0 00-1.5 0v3.19L7.22 11.97a.75.75 0 101.06 1.06l2.25-2.25a.75.75 0 00.22-.53V6.75z" fill="currentColor"/>
      </svg>
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

/* ── Connect button ─────────────────────────── */
.connect-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 16px;
  background: #0B42C3;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

.connect-btn:hover {
  background: #05299E;
}

.connect-btn:active {
  background: #05299E;
}

.btn-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  opacity: 0.85;
}

/* ── Connected / loading pill ───────────────── */
.connect-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  font-size: var(--text-content-text-regular-lg);
  line-height: var(--text-content-text-regular-lg--line-height);
}

.connect-status.connected {
  background: #F3FCFB;
  border: 1px solid #DFF7F3;
}

.connect-status.loading {
  background: var(--color-surface-neutral-100);
  border: 1px solid var(--color-borders-neutral-light);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.connected-dot {
  background: #0C7C59;
}

.loading-dot {
  background: #A4B5C1;
}

.status-text {
  color: var(--color-text-neutral-base);
  font-weight: 500;
}

.connected .status-text {
  color: #0C7C59;
}

/* ── Disconnect button ──────────────────────── */
.disconnect-btn {
  margin-left: auto;
  background: none;
  border: 1px solid #C8D3DA;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: var(--text-content-legends-bold-md, 12px);
  color: #5D6D79;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.disconnect-btn:hover {
  border-color: #943124;
  color: #943124;
}
</style>
