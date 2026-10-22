import { onMounted, ref } from "vue";
import { fetchRegisteredEmails } from "../sessions";

// Emails already registered to a session, so batches can skip them instead of
// collecting "already registered" failures. Never blocks submitting: if the
// check is slow or fails, Livestorm still refuses duplicates on its side.
export function useRegisteredEmails(session) {
  const registeredEmails = ref(new Set());
  const registeredCheck = ref("idle"); // "checking" | "done" | "failed"

  onMounted(async () => {
    if (!session.registrants_count) {
      registeredCheck.value = "done";
      return;
    }
    registeredCheck.value = "checking";
    try {
      const data = await fetchRegisteredEmails(session.id);
      registeredEmails.value = new Set(data.emails);
      registeredCheck.value = "done";
    } catch {
      registeredCheck.value = "failed";
    }
  });

  function isRegistered(email) {
    return registeredEmails.value.has(String(email).trim().toLowerCase());
  }

  return { registeredCheck, isRegistered };
}
