import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

export default defineConfig({
  plugins: [preact()],
  server: {
    port: 3009,
    proxy: {
      "/api": {
        target: "http://localhost:3008",
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 3009,
  },
});
