<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { requestJson, wait } from "../api";

const props = defineProps({
  session: { type: Object, required: true },
});

const emit = defineEmits(["busy-change", "registrants-changed"]);

// 0.25 s between contact updates → 4 req/s, safely under Livestorm's 5 req/s burst limit.
const CONTACT_UPDATE_DELAY_MS = 250;

const contactsData = ref(null); // { session_id, headers, people: [{ id, fields }], total }
const contactDrafts = ref({}); // { [personId]: { fieldId: value } }
const contactSaveStates = ref({}); // { [personId]: { saving?, saved?, error?, confirmDelete?, deleting? } }
const isLoading = ref(false);
const isSavingAll = ref(false);
const errorMessage = ref("");

const editableHeaders = computed(() =>
  contactsData.value ? contactsData.value.headers.filter((h) => h !== "email") : [],
);

function isContactDirty(person) {
  const draft = contactDrafts.value[person.id];
  if (!draft) return false;
  return editableHeaders.value.some((fid) => (draft[fid] ?? "") !== (person.fields[fid] ?? ""));
}

function isFieldChanged(person, fieldId) {
  const draft = contactDrafts.value[person.id];
  if (!draft) return false;
  return (draft[fieldId] ?? "") !== (person.fields[fieldId] ?? "");
}

const dirtyCount = computed(() =>
  contactsData.value ? contactsData.value.people.filter(isContactDirty).length : 0,
);

const contactsWithErrors = computed(() =>
  contactsData.value ? contactsData.value.people.filter((p) => contactSaveStates.value[p.id]?.error) : [],
);

const savedCount = computed(() =>
  contactsData.value ? contactsData.value.people.filter((p) => contactSaveStates.value[p.id]?.saved).length : 0,
);

const isBusy = computed(
  () => isSavingAll.value || Object.values(contactSaveStates.value).some((s) => s.saving || s.deleting),
);

watch(isBusy, (busy) => emit("busy-change", busy));

function setSaveState(personId, state) {
  contactSaveStates.value = { ...contactSaveStates.value, [personId]: state };
}

async function fetchContacts() {
  errorMessage.value = "";
  isLoading.value = true;
  try {
    const data = await requestJson("/api/session-contacts", {
      method: "POST",
      body: { session_id: props.session.id },
      fallbackMessage: "We couldn't load the registrants of this session.",
    });
    contactsData.value = data;
    contactDrafts.value = Object.fromEntries(data.people.map((p) => [p.id, { ...p.fields }]));
    contactSaveStates.value = {};
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isLoading.value = false;
  }
}

function onFieldInput(personId, fieldId, value) {
  contactDrafts.value = {
    ...contactDrafts.value,
    [personId]: { ...contactDrafts.value[personId], [fieldId]: value },
  };
  if (contactSaveStates.value[personId]) setSaveState(personId, {});
}

function resetRow(person) {
  contactDrafts.value = { ...contactDrafts.value, [person.id]: { ...person.fields } };
  setSaveState(person.id, {});
}

async function saveContact(person) {
  const draft = contactDrafts.value[person.id] || {};
  const changedFields = editableHeaders.value
    .filter((fid) => (draft[fid] ?? "") !== (person.fields[fid] ?? ""))
    .map((fid) => ({ id: fid, value: (draft[fid] ?? "").trim() }));
  if (!changedFields.length) return;

  setSaveState(person.id, { saving: true });
  try {
    await requestJson("/api/update-contact", {
      method: "POST",
      body: {
        session_id: props.session.id,
        person_id: person.id,
        email: person.fields.email || "",
        fields: changedFields,
      },
      fallbackMessage: "Update failed.",
    });
    person.fields = {
      ...person.fields,
      ...Object.fromEntries(changedFields.map((f) => [f.id, f.value])),
    };
    contactDrafts.value = { ...contactDrafts.value, [person.id]: { ...person.fields } };
    setSaveState(person.id, { saved: true });
  } catch (error) {
    setSaveState(person.id, { error: error.message });
  }
}

async function deleteContact(person) {
  setSaveState(person.id, { deleting: true });
  try {
    await requestJson("/api/delete-contact", {
      method: "POST",
      body: { session_id: props.session.id, person_id: person.id },
      fallbackMessage: "Deletion failed.",
    });
    contactsData.value = {
      ...contactsData.value,
      people: contactsData.value.people.filter((p) => p.id !== person.id),
      total: contactsData.value.total - 1,
    };
    const drafts = { ...contactDrafts.value };
    delete drafts[person.id];
    contactDrafts.value = drafts;
    const states = { ...contactSaveStates.value };
    delete states[person.id];
    contactSaveStates.value = states;
    emit("registrants-changed");
  } catch (error) {
    setSaveState(person.id, { error: error.message });
  }
}

async function saveAll() {
  if (!contactsData.value || isSavingAll.value) return;
  isSavingAll.value = true;
  try {
    for (const person of contactsData.value.people) {
      if (!isContactDirty(person)) continue;
      await saveContact(person);
      await wait(CONTACT_UPDATE_DELAY_MS);
    }
  } finally {
    isSavingAll.value = false;
  }
}

onMounted(fetchContacts);
</script>

<template>
  <p v-if="isLoading && !contactsData" class="loading-line" role="status">Loading registrants…</p>
  <section v-if="errorMessage" class="notice error" role="alert">{{ errorMessage }}</section>

  <section v-if="contactsData" class="panel preview-panel">
    <div class="panel-header">
      <div>
        <span class="step-label">Registrants</span>
        <h2>{{ contactsData.total }} registrant{{ contactsData.total === 1 ? "" : "s" }}</h2>
        <p>Click a value to edit it, then save the row. Email is protected by Livestorm and can't be changed.</p>
      </div>
      <div class="preview-statuses">
        <div v-if="savedCount" class="status-pill ok">{{ savedCount }} saved</div>
        <div v-if="dirtyCount" class="warning-pill">
          {{ dirtyCount }} unsaved change{{ dirtyCount === 1 ? "" : "s" }}
        </div>
        <button class="bar-btn" type="button" :disabled="isBusy || isLoading" @click="fetchContacts">
          {{ isLoading ? "Refreshing…" : "Refresh" }}
        </button>
        <button class="bar-btn primary" type="button" :disabled="!dirtyCount || isSavingAll" @click="saveAll">
          {{ isSavingAll ? "Saving…" : "Save all changes" }}
        </button>
      </div>
    </div>

    <p class="contacts-hint">Deleting a registrant unregisters them from this session permanently.</p>

    <div class="registrant-table-wrap">
      <table class="registrant-table contacts-table">
        <thead>
          <tr>
            <th class="del-th"><span class="sr-only">Unregister</span></th>
            <th v-for="field in contactsData.headers" :key="field">
              {{ field }}<span v-if="field === 'email'" class="th-lock">read-only</span>
            </th>
            <th class="save-th"><span class="sr-only">Save</span></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="person in contactsData.people"
            :key="person.id"
            :class="{
              'row-dirty': isContactDirty(person),
              'row-save-error': contactSaveStates[person.id]?.error,
              'row-confirm-delete': contactSaveStates[person.id]?.confirmDelete,
            }"
          >
            <td class="del-td">
              <span v-if="contactSaveStates[person.id]?.deleting" class="save-status">Deleting…</span>
              <div v-else-if="contactSaveStates[person.id]?.confirmDelete" class="delete-confirm">
                <button class="confirm-delete-btn" type="button" @click="deleteContact(person)">Delete</button>
                <button class="row-action-btn restore" type="button" aria-label="Cancel" @click="setSaveState(person.id, {})">↩</button>
              </div>
              <button
                v-else
                class="row-action-btn remove"
                type="button"
                :aria-label="`Unregister ${person.fields.email} from this session`"
                :disabled="contactSaveStates[person.id]?.saving || isSavingAll"
                @click="setSaveState(person.id, { confirmDelete: true })"
              >✕</button>
            </td>
            <td v-for="field in contactsData.headers" :key="field" class="contact-cell">
              <span v-if="field === 'email'" class="contact-email">{{ person.fields.email }}</span>
              <input
                v-else
                class="contact-input"
                :class="{ changed: isFieldChanged(person, field) }"
                :value="(contactDrafts[person.id] || {})[field] ?? ''"
                placeholder="—"
                :aria-label="`${field} for ${person.fields.email}`"
                :disabled="contactSaveStates[person.id]?.saving || isSavingAll"
                @input="onFieldInput(person.id, field, $event.target.value)"
              />
            </td>
            <td class="save-td">
              <div class="save-actions">
                <span v-if="contactSaveStates[person.id]?.saving" class="save-status">Saving…</span>
                <template v-else-if="isContactDirty(person)">
                  <button class="row-save-btn" type="button" @click="saveContact(person)">
                    {{ contactSaveStates[person.id]?.error ? "Retry" : "Save" }}
                  </button>
                  <button class="row-action-btn restore" type="button" aria-label="Discard changes" @click="resetRow(person)">↩</button>
                </template>
                <span v-else-if="contactSaveStates[person.id]?.saved" class="save-status saved">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                  Saved
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="contactsWithErrors.length" class="contact-errors" role="alert">
      <div v-for="person in contactsWithErrors" :key="person.id" class="notice error contact-error-item">
        <strong>{{ person.fields.email }}</strong> — {{ contactSaveStates[person.id].error }}
      </div>
    </div>
  </section>
</template>

<style scoped>
.loading-line {
  margin: 0 0 var(--spacing-space-4);
  color: var(--color-text-neutral-secondary);
}

.bar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
