import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地要看「线上版本」：构建后用 preview 跑 dist，并把 /api 代理到线上后端
//   $env:CLAUSELENS_API="https://api.dohub.tech"; npm run build; npm run preview
// 默认仍指向本机 8787（本地后端），改一行环境变量就能对齐线上，不用改代码。
const API = process.env.CLAUSELENS_API || "http://127.0.0.1:8787";
const proxy = { "/api": { target: API, changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
