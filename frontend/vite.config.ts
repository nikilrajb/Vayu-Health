import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { env } from "node:process";

const apiTarget = env.VAYU_API_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id))
            return "react";
          if (id.includes("/node_modules/leaflet/")) return "maps";
          if (id.includes("/node_modules/")) return "charts";
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": apiTarget,
      "/health": apiTarget,
    },
  },
});
