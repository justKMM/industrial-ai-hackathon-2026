import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // cases/ lives at the repo root, outside the Vite root, and is read directly
    fs: { allow: [path.resolve(__dirname, "../..")] },
    // The FastAPI backend (src/backend); BACKEND_URL points the app at another address or port
    proxy: { "/api": process.env.BACKEND_URL ?? "http://localhost:8000" },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})