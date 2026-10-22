<script setup>
import { computed, onMounted, ref } from "vue";
import ActionChooser from "./components/ActionChooser.vue";
import BetaInfoModal from "./components/BetaInfoModal.vue";
import ConnectCard from "./components/ConnectCard.vue";
import ContactsEditor from "./components/ContactsEditor.vue";
import ImportFlow from "./components/ImportFlow.vue";
import SessionHeader from "./components/SessionHeader.vue";
import SessionPicker from "./components/SessionPicker.vue";
import UploadFlow from "./components/UploadFlow.vue";
import { SESSION_EXPIRED_MESSAGE, onSessionExpired } from "./api";
import { fetchSession } from "./sessions";
import { livestormLogo, theme, toggleTheme } from "./theme";

const showBetaInfo = ref(false);

// ── Auth ───────────────────────────────────────────────────────────────────────

const isAuthenticated = ref(false);
const isAuthLoading = ref(true);
const errorMessage = ref("");

async function checkAuthStatus() {
  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    isAuthenticated.value = data.authenticated;
  } catch {
    isAuthenticated.value = false;
  } finally {
    isAuthLoading.value = false;
  }
}

function handleLogin() {
  window.location.href = "/api/auth/livestorm/login";
}

async function handleLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
  isAuthenticated.value = false;
  resetSession();
}

onSessionExpired(() => {
  isAuthenticated.value = false;
  resetSession();
  errorMessage.value = SESSION_EXPIRED_MESSAGE;
});

onMounted(() => {
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth_error");
  if (authError) {
    errorMessage.value = `Livestorm connection failed: ${authError.replace(/_/g, " ")}.`;
    window.history.replaceState({}, "", window.location.pathname);
  }
  checkAuthStatus();
});

// ── Session and action ─────────────────────────────────────────────────────────

const selectedSession = ref(null); // detail from /api/sessions/{id}
const isOpeningSession = ref(false);
const action = ref(null); // null | "upload" | "import" | "contacts"
const isActionBusy = ref(false);

const currentStep = computed(() => {
  if (!isAuthenticated.value) return 1;
  return selectedSession.value ? 3 : 2;
});

function resetSession() {
  selectedSession.value = null;
  action.value = null;
  isActionBusy.value = false;
}

async function openSession(summary) {
  errorMessage.value = "";
  isOpeningSession.value = true;
  try {
    selectedSession.value = await fetchSession(summary.id);
    action.value = null;
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isOpeningSession.value = false;
  }
}

// Registrant counts change after a batch, so reload the session quietly.
async function refreshSession() {
  if (!selectedSession.value) return;
  try {
    selectedSession.value = await fetchSession(selectedSession.value.id);
  } catch {
    // Keep showing the previous details; the count is informational.
  }
}

function changeSession() {
  if (isActionBusy.value) return;
  errorMessage.value = "";
  resetSession();
}

function backToActions() {
  if (isActionBusy.value) return;
  action.value = null;
  refreshSession();
}
</script>

<template>

  <!-- ── App bar ───────────────────────────────────────────────────────────── -->

  <header class="app-bar">
    <div class="app-bar-brand">
      <img :src="livestormLogo" alt="Livestorm" class="app-bar-logo" />
      <span class="app-bar-sep"></span>
      <span class="app-bar-name">StormBatch</span>
      <span class="app-bar-beta">Beta</span>
    </div>
    <div class="app-bar-auth">
      <button
        class="bar-btn icon-btn"
        type="button"
        :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
        :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
        @click="toggleTheme"
      >
        <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
        <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
      </button>
      <span v-if="isAuthLoading" class="auth-status-text">Connecting…</span>
      <button v-else-if="isAuthenticated" class="bar-btn" type="button" @click="handleLogout">Disconnect</button>
    </div>
  </header>

  <main class="page-shell">

    <!-- ── Step track ────────────────────────────────────────────────────────── -->

    <nav class="step-track" aria-label="Progress">
      <div class="step-item" :class="{ active: currentStep === 1, done: isAuthenticated }">
        <div class="step-circ">
          <svg v-if="isAuthenticated" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <span v-else>1</span>
        </div>
        <span class="step-lbl">Connect</span>
      </div>
      <div class="step-conn" :class="{ done: isAuthenticated }"></div>
      <button
        class="step-item step-button"
        type="button"
        :class="{
          active: currentStep === 2,
          done: currentStep === 3,
          locked: !isAuthenticated,
          'can-navigate': currentStep === 3 && !isActionBusy,
        }"
        :disabled="currentStep !== 3 || isActionBusy"
        @click="changeSession"
      >
        <span class="step-circ">
          <svg v-if="currentStep === 3" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          <span v-else>2</span>
        </span>
        <span class="step-lbl">Session</span>
      </button>
      <div class="step-conn" :class="{ done: currentStep === 3 && action }"></div>
      <div class="step-item" :class="{ active: currentStep === 3, locked: currentStep !== 3 }">
        <div class="step-circ"><span>3</span></div>
        <span class="step-lbl">Action</span>
      </div>
    </nav>

    <!-- ── Step 1: Connect ───────────────────────────────────────────────────── -->

    <ConnectCard
      v-if="!isAuthenticated && !isAuthLoading"
      :error-message="errorMessage"
      @login="handleLogin"
    />

    <template v-else-if="isAuthenticated">
      <section v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</section>

      <!-- ── Step 2: Pick a session ──────────────────────────────────────────── -->

      <section v-if="!selectedSession" class="panel">
        <h1 class="step-heading">Choose a session</h1>
        <p class="step-intro">
          {{ isOpeningSession ? "Opening session…" : "Pick the session you want to register people into." }}
        </p>
        <SessionPicker :disabled="isOpeningSession" @select="openSession" />
      </section>

      <!-- ── Step 3: Choose and run an action ────────────────────────────────── -->

      <template v-else>
        <SessionHeader :session="selectedSession" :can-change="!isActionBusy" @change="changeSession" />

        <ActionChooser
          v-if="!action"
          :registrants-count="selectedSession.registrants_count"
          @choose="action = $event"
        />

        <template v-else>
          <button class="back-btn" type="button" :disabled="isActionBusy" @click="backToActions">
            ← Choose another action
          </button>
          <UploadFlow
            v-if="action === 'upload'"
            :session="selectedSession"
            @busy-change="isActionBusy = $event"
            @done="backToActions"
          />
          <ImportFlow
            v-else-if="action === 'import'"
            :session="selectedSession"
            @busy-change="isActionBusy = $event"
            @done="backToActions"
          />
          <ContactsEditor
            v-else-if="action === 'contacts'"
            :session="selectedSession"
            @busy-change="isActionBusy = $event"
            @registrants-changed="refreshSession"
          />
        </template>
      </template>
    </template>

    <!-- ── Beta notice footer ──────────────────────────────────────────────── -->

    <div class="beta-notice">
      <span class="beta-notice-chip">Beta</span>
      Early-access helper, not an official Livestorm product.
      <button class="beta-notice-link" type="button" @click="showBetaInfo = true">Read more</button>
    </div>

  </main>

  <BetaInfoModal v-if="showBetaInfo" @close="showBetaInfo = false" />
</template>
