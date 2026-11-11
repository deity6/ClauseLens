// Cloudflare Pages Function：把 /api/* 同源转发到后端容器。
//
// 为什么需要它：页面在 lens.dohub.tech（CF Pages，静态），后端在 api.dohub.tech:8443（腾讯小机）。
// 如果让浏览器直接跨域调 8443，既要开 CORS、又会暴露端口；走这层同源代理后，
// 前端代码里仍然是 `/api/analyze`，SSE 也能原样透传（直接 return fetch(...) 是流式的）。
const BACKEND = "https://api.dohub.tech:8443";

export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const target = BACKEND + url.pathname + url.search;

  const headers = new Headers(request.headers);
  headers.delete("host");

  const init = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
    redirect: "manual",
  };

  const resp = await fetch(target, init);

  // 原样返回，但把 SSE 的缓冲相关头补齐（CF 默认会缓冲）
  const out = new Headers(resp.headers);
  const ct = out.get("content-type") || "";
  if (ct.includes("text/event-stream")) {
    out.set("cache-control", "no-cache, no-transform");
    out.set("x-accel-buffering", "no");
  }
  return new Response(resp.body, { status: resp.status, statusText: resp.statusText, headers: out });
}