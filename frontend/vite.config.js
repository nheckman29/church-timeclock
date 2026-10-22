import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// During development, `npm run dev` serves the UI with hot reload and forwards /api
// calls to the Flask server (python run.py). In production, Flask serves the built
// files from dist/ itself, so only one process runs.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": "http://localhost:8080" },
  },
});
