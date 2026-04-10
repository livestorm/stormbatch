import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const tailwindEntry = fileURLToPath(
  new URL("./node_modules/tailwindcss/index.css", import.meta.url),
);

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      tailwindcss: tailwindEntry,
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
