import { defineConfig } from "vite";
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

/**
 * Public supplier form build config.
 *
 * The dev/preview servers bind 0.0.0.0 so a phone on the same network can open
 * the form and exercise the real mobile layout — that is the only way this page
 * is ever used in practice.
 */
export default defineConfig({
  plugins: [react(), tailwindcss()],

  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },

  server: {
    host: "0.0.0.0",
    port: 5174,
  },

  preview: {
    host: "0.0.0.0",
    port: 4174,
  },
});
