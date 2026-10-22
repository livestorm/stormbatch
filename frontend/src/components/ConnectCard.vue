<script setup>
// The brand logo follows the page theme; the icon inside the connect button
// sits on the button's own color, so it keeps the white variant.
import buttonIcon from "../../assets/Icon-Livestorm-Tertiary-Light.png";
import { livestormLogo } from "../theme";

defineProps({
  errorMessage: { type: String, default: "" },
});

const emit = defineEmits(["login"]);

const FEATURES = [
  "Pick from your upcoming sessions, no IDs to copy",
  "Register people from an .xlsx or .csv file",
  "Import the registrants of another session",
  "Edit or unregister people in a session",
];
</script>

<template>
  <div class="onboarding-state">
    <div class="onboarding-card">
      <div class="onboarding-brand">
        <img :src="livestormLogo" alt="Livestorm" class="onboarding-logo" />
        <span class="onboarding-brand-sep"></span>
        <span class="onboarding-brand-name">StormBatch</span>
      </div>
      <h1 class="onboarding-title">Batch register Livestorm attendees</h1>
      <p class="onboarding-desc">
        Pick a session, then register everyone from a spreadsheet or another session in one go.
      </p>
      <ul class="onboarding-features">
        <li v-for="feature in FEATURES" :key="feature">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
          {{ feature }}
        </li>
      </ul>
      <div v-if="errorMessage" class="notice error onboarding-error" role="alert">{{ errorMessage }}</div>
      <button class="primary-button onboarding-cta" type="button" @click="emit('login')">
        <img :src="buttonIcon" alt="" class="bar-btn-icon" />
        Connect with Livestorm
      </button>
    </div>
  </div>
</template>
