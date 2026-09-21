import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      // "@/components/..." means "src/components/..." everywhere in our code (shadcn needs this)
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // While you develop, every request that starts with /api is passed on to our Python backend.
    // Start it with:  uvicorn app.api:app --port 8000
    proxy: { "/api": "http://localhost:8000" },
  },
})