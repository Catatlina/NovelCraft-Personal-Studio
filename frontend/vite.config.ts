import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
      "/openapi.json": process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000",
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          tiptap: ["@tiptap/react", "@tiptap/starter-kit", "@tiptap/extension-placeholder"],
          icons: ["lucide-react"],
        },
      },
    },
  },
});
