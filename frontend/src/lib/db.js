import { openDB } from "idb";

const DB_NAME = "hackathon_judge";
const DB_VERSION = 1;

let _db = null;

async function getDB() {
  if (_db) return _db;
  _db = await openDB(DB_NAME, DB_VERSION, {
    upgrade(db) {
      if (!db.objectStoreNames.contains("scores")) {
        db.createObjectStore("scores", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("projects")) {
        db.createObjectStore("projects", { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains("judgeProfile")) {
        db.createObjectStore("judgeProfile", { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains("syncQueue")) {
        const store = db.createObjectStore("syncQueue", {
          keyPath: "id",
          autoIncrement: true,
        });
        store.createIndex("by_status", "status");
      }
    },
  });
  return _db;
}

// ── localStorage helpers (never throw, always available) ─────────────────────

function lsGet(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}

function lsSet(key, val) {
  try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
}

// ── Score key ─────────────────────────────────────────────────────────────────

export function scoreKey(judgeId, projectId) {
  return `judge_${judgeId}_project_${projectId}`;
}

// ── Scores — dual-write: localStorage first, IndexedDB second ────────────────

export async function saveScore(judgeId, projectId, data) {
  const entry = {
    key: scoreKey(judgeId, projectId),
    judgeId,
    projectId,
    ...data,
    syncStatus: data.syncStatus || "pending",
    updatedAt: new Date().toISOString(),
  };

  // Always write localStorage first — synchronous, never fails
  const ls = lsGet("scores_backup", {});
  ls[entry.key] = entry;
  lsSet("scores_backup", ls);

  // Best-effort IndexedDB
  try {
    const db = await getDB();
    await db.put("scores", entry);
  } catch {}
}

export async function loadScores() {
  const lsScores = lsGet("scores_backup", {});

  try {
    const db = await getDB();
    const all = await db.getAll("scores");
    // Start with localStorage, let IndexedDB entries overwrite (same or newer)
    const map = { ...lsScores };
    for (const s of all) { map[s.key] = s; }
    return map;
  } catch {
    return lsScores;
  }
}

export async function loadScoreForProject(judgeId, projectId) {
  const scores = await loadScores();
  return scores[scoreKey(judgeId, projectId)] ?? null;
}

export async function markScoreSynced(judgeId, projectId) {
  const key = scoreKey(judgeId, projectId);

  // Update localStorage
  const ls = lsGet("scores_backup", {});
  if (ls[key]) { ls[key].syncStatus = "synced"; lsSet("scores_backup", ls); }

  // Best-effort IndexedDB
  try {
    const db = await getDB();
    const existing = await db.get("scores", key);
    if (existing) await db.put("scores", { ...existing, syncStatus: "synced" });
  } catch {}
}

// ── Sync queue — localStorage-backed, IndexedDB optional ─────────────────────

function lsQueueGet() { return lsGet("sync_queue", []); }
function lsQueueSet(q) { lsSet("sync_queue", q); }

export async function enqueue(item) {
  // Write to localStorage queue first
  const q = lsQueueGet();
  const lsEntry = {
    id: `ls_${Date.now()}_${Math.random().toString(36).slice(2)}`,
    ...item,
    status: "pending",
    retryCount: 0,
    createdAt: new Date().toISOString(),
  };
  q.push(lsEntry);
  lsQueueSet(q);

  // Best-effort IndexedDB
  try {
    const db = await getDB();
    await db.add("syncQueue", { ...item, status: "pending", retryCount: 0, createdAt: new Date().toISOString() });
  } catch {}
}

export async function getPendingQueue() {
  const lsItems = lsQueueGet().filter((i) => i.status === "pending");

  try {
    const db = await getDB();
    const idbItems = await db.getAllFromIndex("syncQueue", "by_status", "pending");
    // Merge: use IndexedDB items when available, otherwise localStorage items
    const idbScoreIds = new Set(idbItems.map((i) => i.scoreData?.project_id + "_" + i.judgeId));
    const lsOnly = lsItems.filter(
      (i) => !idbScoreIds.has(i.scoreData?.project_id + "_" + i.judgeId)
    );
    return [...idbItems, ...lsOnly];
  } catch {
    return lsItems;
  }
}

export async function markQueueItemDone(id) {
  // Remove from localStorage queue
  const q = lsQueueGet().filter((i) => i.id !== id);
  lsQueueSet(q);

  // Best-effort IndexedDB (numeric IDs only)
  if (typeof id === "number") {
    try {
      const db = await getDB();
      await db.delete("syncQueue", id);
    } catch {}
  }
}

export async function incrementRetry(id) {
  // Update localStorage queue
  const q = lsQueueGet();
  const item = q.find((i) => i.id === id);
  if (item) {
    item.retryCount = (item.retryCount || 0) + 1;
    if (item.retryCount >= 10) item.status = "failed";
    lsQueueSet(q);
  }

  // Best-effort IndexedDB
  if (typeof id === "number") {
    try {
      const db = await getDB();
      const entry = await db.get("syncQueue", id);
      if (entry) {
        entry.retryCount = (entry.retryCount || 0) + 1;
        if (entry.retryCount >= 10) entry.status = "failed";
        await db.put("syncQueue", entry);
      }
    } catch {}
  }
}

// ── Judge profile ─────────────────────────────────────────────────────────────

export async function saveProfile(profile) {
  try {
    const db = await getDB();
    await db.put("judgeProfile", { key: "profile", ...profile });
  } catch {}
}

export async function loadProfile() {
  try {
    const db = await getDB();
    return db.get("judgeProfile", "profile");
  } catch { return null; }
}

export async function clearProfile() {
  try {
    const db = await getDB();
    await db.delete("judgeProfile", "profile");
  } catch {}
}

// ── Projects cache ────────────────────────────────────────────────────────────

export async function saveProjects(projects) {
  try {
    const db = await getDB();
    const tx = db.transaction("projects", "readwrite");
    await Promise.all(projects.map((p) => tx.store.put(p)));
    await tx.done;
  } catch {}
}

export async function loadProjects() {
  try {
    const db = await getDB();
    return db.getAll("projects");
  } catch { return []; }
}
