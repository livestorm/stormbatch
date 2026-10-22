import { computed, ref } from "vue";
import { fetchRegisteredEmails } from "../sessions";

// Emails already registered to a session, so batches can skip them instead of
// collecting "already registered" failures. Never blocks submitting: if the
// check is slow, fails or is skipped, Livestorm still refuses duplicates.
export function useRegisteredEmails(session) {
  const registeredEmails = ref(new Set());
  // "idle" until checkRegistered() runs; then "checking", "done", "failed",
  // or "too-large" when the session has too many registrants to list.
  const registeredCheck = ref("idle");
  const registrantsCount = ref(session.registrants_count || 0);

  // Listing registrants costs Livestorm API calls, so it only runs once there
  // are rows to compare, and only once per flow.
  async function checkRegistered() {
    if (registeredCheck.value !== "idle") return;
    if (!session.registrants_count) {
      registeredCheck.value = "done";
      return;
    }
    registeredCheck.value = "checking";
    try {
      const data = await fetchRegisteredEmails(session.id);
      registrantsCount.value = data.registrants_count ?? registrantsCount.value;
      if (!data.checked) {
        registeredCheck.value = "too-large";
        return;
      }
      registeredEmails.value = new Set(data.emails);
      registeredCheck.value = "done";
    } catch {
      registeredCheck.value = "failed";
    }
  }

  function isRegistered(email) {
    return registeredEmails.value.has(String(email).trim().toLowerCase());
  }

  const registeredCheckNote = computed(() => {
    switch (registeredCheck.value) {
      case "checking":
        return "Checking who's already registered to this session…";
      case "failed":
        return "We couldn't check who's already registered. Livestorm will refuse duplicates on its side.";
      case "too-large":
        return `This session has ${registrantsCount.value.toLocaleString()} registrants, too many to check ahead without using up Livestorm API calls. Livestorm will refuse anyone already registered.`;
      default:
        return "";
    }
  });

  return { checkRegistered, isRegistered, registeredCheckNote };
}
