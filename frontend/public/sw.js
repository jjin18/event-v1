// Service Worker — offline-first score submission
const CACHE_NAME = "hackathon-judge-v1";
const STATIC_ASSETS = ["/", "/judge", "/judge/login"];

self.addEventListener("install", (e) => {
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(clients.claim());
});

// Intercept POST /api/judge/scores — fake 200 offline, queue for later
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  if (e.request.method === "POST" && url.pathname === "/api/judge/scores") {
    e.respondWith(handleScorePost(e.request.clone()));
    return;
  }

  // For GET requests, try network first, fall back to cache
  if (e.request.method === "GET" && !url.pathname.startsWith("/api/")) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
  }
});

async function handleScorePost(request) {
  if (navigator.onLine) {
    try {
      const response = await fetch(request);
      return response;
    } catch {
      // Fall through to offline handling
    }
  }

  // Offline: store in IndexedDB sync queue via postMessage
  const body = await request.json().catch(() => ({}));
  const token = request.headers.get("Authorization") || "";

  // Notify all clients to enqueue
  const allClients = await clients.matchAll({ type: "window" });
  for (const client of allClients) {
    client.postMessage({ type: "QUEUE_SCORE", body, token });
  }

  // Return fake 200
  return new Response(JSON.stringify({ ok: true, queued: true }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

// Background Sync
self.addEventListener("sync", (e) => {
  if (e.tag === "score-sync") {
    e.waitUntil(flushQueueFromSW());
  }
});

async function flushQueueFromSW() {
  const allClients = await clients.matchAll({ type: "window" });
  for (const client of allClients) {
    client.postMessage({ type: "FLUSH_QUEUE" });
  }
}
