<script setup>
const emit = defineEmits(["close"]);

function onOverlayClick(e) {
  if (e.target === e.currentTarget) emit("close");
}
</script>

<template>
  <div class="modal-overlay" @click="onOverlayClick" role="dialog" aria-modal="true" aria-labelledby="beta-modal-title">
    <div class="modal-panel">
      <div class="modal-header">
        <div class="modal-title-row">
          <span class="beta-chip">Beta</span>
          <h2 id="beta-modal-title">About StormBatch</h2>
        </div>
        <button class="modal-close" type="button" @click="emit('close')" aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="1" y1="1" x2="11" y2="11"/><line x1="11" y1="1" x2="1" y2="11"/></svg>
        </button>
      </div>

      <div class="modal-body">

        <section class="info-section">
          <h3>What is StormBatch?</h3>
          <p>
            StormBatch is an early-access, unofficial helper tool built for Livestorm power users
            who need to batch-register attendees across multiple sessions.
            It is <strong>not developed, endorsed, or officially supported by Livestorm</strong>.
          </p>
        </section>

        <section class="info-section">
          <h3>How it works</h3>
          <ol class="steps-list">
            <li>You authenticate with your Livestorm account via OAuth 2.0 — no API key ever leaves your browser session.</li>
            <li>Choose a source: upload a <code>.xlsx</code> or <code>.csv</code> file, or pull registrants directly from an existing Livestorm session.</li>
            <li>Map columns to Livestorm field IDs (e.g. <code>email</code>, <code>first_name</code>).</li>
            <li>Enter one or more target session IDs.</li>
            <li>StormBatch creates <strong>bulk registration jobs</strong> via the Livestorm API in chunks of 50 registrants, then polls each job until it reaches a terminal state.</li>
          </ol>
        </section>

        <section class="info-section">
          <h3>Livestorm API endpoints used</h3>
          <div class="endpoint-list">
            <div class="endpoint-row">
              <code class="method get">GET</code>
              <code class="path">/v1/me</code>
              <span>Fetch your profile (name, email, avatar) after login.</span>
            </div>
            <div class="endpoint-row">
              <code class="method get">GET</code>
              <code class="path">/v1/sessions/{id}/people</code>
              <span>Paginate through all registrants in a source session (transfer mode).</span>
            </div>
            <div class="endpoint-row">
              <code class="method post">POST</code>
              <code class="path">/v1/sessions/{id}/bulk_jobs</code>
              <span>Create a bulk registration job for up to 50 registrants at a time.</span>
            </div>
            <div class="endpoint-row">
              <code class="method get">GET</code>
              <code class="path">/v1/sessions/{id}/bulk_jobs/{job_id}</code>
              <span>Poll job status until it reaches <code>ended</code>, <code>completed</code>, or <code>failed</code>.</span>
            </div>
            <div class="endpoint-row">
              <code class="method post">POST</code>
              <code class="path">/v1/sessions/{id}/people</code>
              <span>Single-person retry fallback for rows that failed in a bulk job.</span>
            </div>
          </div>
        </section>

        <section class="info-section">
          <h3>Data handling</h3>
          <ul class="info-list">
            <li>No attendee data is persisted server-side. Uploaded files and registrant rows are processed in memory and discarded after the request.</li>
            <li>Your Livestorm OAuth token is stored only in a signed, server-side session cookie (httpOnly). It is never exposed to client-side JavaScript.</li>
            <li>There is no database. StormBatch has no persistent storage of any kind.</li>
            <li>Session cookies expire when your browser session ends, or when you click <strong>Disconnect</strong>.</li>
          </ul>
        </section>

        <section class="info-section">
          <h3>Rate limits</h3>
          <p>The Livestorm API enforces a <strong>5 requests/second burst limit</strong> and a rolling quota of <strong>10,000 API calls per 30 days</strong>.</p>
          <ul class="info-list">
            <li>StormBatch spaces bulk job creations <strong>250 ms apart</strong> (≈ 4 req/s) to stay safely under the burst limit.</li>
            <li>Pagination requests between session-people pages include a <strong>300 ms delay</strong>.</li>
            <li>On a <strong>429 Too Many Requests</strong> response, StormBatch reads the <code>Retry-After</code> header and waits before retrying automatically (up to 3 times).</li>
          </ul>
        </section>

        <section class="info-section">
          <h3>OAuth scopes requested</h3>
          <div class="scope-list">
            <code>events:read</code>
            <code>events:write</code>
          </div>
          <p class="scope-note">These are the minimum scopes required to read registrant lists and create bulk registration jobs. StormBatch does not read or modify event settings, recordings, or any other workspace data.</p>
        </section>

      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-panel {
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  background: var(--color-surface-neutral-200);
  border: 1px solid var(--color-borders-neutral-light);
  border-radius: 16px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px 18px;
  border-bottom: 1px solid var(--color-borders-neutral-light);
  flex-shrink: 0;
}

.modal-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.modal-title-row h2 {
  margin: 0;
  font-size: var(--text-title-md);
  font-weight: var(--text-title-md--font-weight);
  color: var(--color-text-neutral-base);
}

.beta-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 5px;
  background: var(--color-actions-primary-idle-alpha-light);
  border: 1px solid var(--color-borders-primary-light);
  color: var(--color-actions-primary-idle);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.modal-close {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 7px;
  border: 1px solid var(--color-borders-neutral-light);
  background: transparent;
  color: var(--color-text-neutral-tertiary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.12s ease, color 0.12s ease;
}

.modal-close:hover {
  background: var(--color-actions-neutral-hover-overlay);
  color: var(--color-text-neutral-base);
}

.modal-body {
  overflow-y: auto;
  padding: 24px;
  display: grid;
  gap: 28px;
}

.info-section h3 {
  margin: 0 0 10px;
  font-size: var(--text-content-text-bold-md);
  font-weight: var(--text-content-text-bold-md--font-weight);
  color: var(--color-text-neutral-base);
}

.info-section p {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md, 14px);
  line-height: 1.65;
}

.info-section strong {
  color: var(--color-text-neutral-base);
  font-weight: 600;
}

.steps-list,
.info-list {
  margin: 0;
  padding-left: 20px;
  display: grid;
  gap: 8px;
  color: var(--color-text-neutral-secondary);
  font-size: var(--text-content-text-regular-md, 14px);
  line-height: 1.6;
}

.steps-list li,
.info-list li {
  padding-left: 4px;
}

.endpoint-list {
  display: grid;
  gap: 8px;
}

.endpoint-row {
  display: grid;
  grid-template-columns: 52px 1fr;
  column-gap: 10px;
  row-gap: 2px;
  align-items: start;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  font-size: 13px;
}

.endpoint-row .method {
  grid-row: 1;
  grid-column: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 0;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.method.get {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.method.post {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.endpoint-row .path {
  grid-row: 1;
  grid-column: 2;
  font-family: ui-monospace, "SFMono-Regular", monospace;
  color: var(--color-text-neutral-base);
  font-size: 12px;
  line-height: 1.5;
  word-break: break-all;
}

.endpoint-row > span {
  grid-row: 2;
  grid-column: 2;
  color: var(--color-text-neutral-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.scope-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.scope-list code {
  padding: 4px 10px;
  border-radius: 6px;
  background: var(--color-surface-neutral-300);
  border: 1px solid var(--color-borders-neutral-light);
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 13px;
  color: var(--color-text-neutral-base);
}

.scope-note {
  margin: 0;
  color: var(--color-text-neutral-secondary);
  font-size: 13px;
  line-height: 1.6;
}

code {
  font-family: ui-monospace, "SFMono-Regular", monospace;
  font-size: 0.9em;
}
</style>
