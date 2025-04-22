import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        host: "0.0.0.0",
        port: 5173,
        watch: {
            usePolling: true,
        },
        proxy: {
            "/api/orchestrator": {
                target: "http://orchestrator:8000",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api\/orchestrator/, ""),
            },
            "/api/registry": {
                target: "http://registry:8000",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api\/registry/, ""),
            },
            "/api/broker": {
                target: "http://broker:8000",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/api\/broker/, ""),
            },
        },
    },
});
