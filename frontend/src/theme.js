import { computed, ref } from "vue";
import darkBackgroundLogo from "../assets/Icon-Livestorm-Tertiary-Light.png";
import lightBackgroundLogo from "../assets/Icon-Livestorm-Primary.png";

// The Livestorm tokens switch between their light and dark palettes on this
// attribute. index.html sets it before first paint; this module keeps it in sync.
const THEME_ATTRIBUTE = "data-colors-semantic";
const STORAGE_KEY = "stormbatch-theme";

export const theme = ref(document.documentElement.getAttribute(THEME_ATTRIBUTE) === "light" ? "light" : "dark");

export const livestormLogo = computed(() =>
  theme.value === "light" ? lightBackgroundLogo : darkBackgroundLogo,
);

function savedTheme() {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function applyTheme(value) {
  theme.value = value;
  document.documentElement.setAttribute(THEME_ATTRIBUTE, value);
}

export function toggleTheme() {
  const next = theme.value === "dark" ? "light" : "dark";
  applyTheme(next);
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Storage can be blocked; the choice then lasts until the page reloads.
  }
}

// Follow the system setting until the viewer picks a theme themselves.
window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", (event) => {
  if (!savedTheme()) applyTheme(event.matches ? "light" : "dark");
});
