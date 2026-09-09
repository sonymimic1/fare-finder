import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Pure client-side SPA: no SSR, no server entry. `vite build` emits static
// assets to dist/; deep links (e.g. /app) are handled by vercel.json rewrites.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // resolves "@/..." from tsconfig.json paths
    tsconfigPaths: true,
  },
  build: {
    outDir: "dist",
  },
});
