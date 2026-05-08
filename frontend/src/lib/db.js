import { openDB } from "idb";

const DB_NAME = "hackathon_judge";
const DB_VERSION = 1;

let _db = null;

export async function getDB() {
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

// Judge profile (auth state)
export async function saveProfile(profile) {
  const db = await getDB();
  await db.put("judgeProfile", { key: "profile", ...profile });
}

export async function loadProfile() {
  const db = await getDB();
  return db.get("judgeProfile", "profile");
}

export async function clearProfile() {
  const db = await getDB();
  await db.delete("judgeProfile", "profile");
}

// Projects cache
export async function saveProjects(projects) {
  const db = await getDB();
  const tx = db.transaction("projects", "readwrite");
  await Promise.all(projects.map((p) => tx.store.put(p)));
  await tx.done;
}

export async function loadProjects() {
  const db = await getDB();
  return db.getAll("projects");
}

// Scores
export function scoreKey(judgeId, projectId) {
  return `judge_${judgeId}_project_${projectId}`;
}

export async function saveScore(judgeId, projectId, data) {
  const db = await getDB();
  await db.put("scores", {
    key: scoreKey(judgeId, projectId),
    judgeId,
    projectId,
    ...data,
    syncStatus: data.syncStatus || "pending",
    updatedAt: new Date().toISOString(),
  });
}

export async function loadScores() {
  const db = await getDB();
  const all = await db.getAll("scores");
  const map = {};
  for (const s of all) {
    map[s.key] = s;
  }
  return map;
}

export async function loadScoreForProject(judgeId, projectId) {
  const db = await getDB();
  return db.get("scores", scoreKey(judgeId, projectId));
}

export async function markScoreSynced(judgeId, projectId) {
  const db = await getDB();
  const key = scoreKey(judgeId, projectId);
  const existing = await db.get("scores", key);
  if (existing) {
    await db.put("scores", { ...existing, syncStatus: "synced" });
  }
}

// Sync queue
export async function enqueue(item) {
  const db = await getDB();
  await db.add("syncQueue", { ...item, status: "pending", retryCount: 0, createdAt: new Date().toISOString() });
}

export async function getPendingQueue() {
  const db = await getDB();
  return db.getAllFromIndex("syncQueue", "by_status", "pending");
}

export async function markQueueItemDone(id) {
  const db = await getDB();
  await db.delete("syncQueue", id);
}

export async function incrementRetry(id) {
  const db = await getDB();
  const item = await db.get("syncQueue", id);
  if (item) {
    item.retryCount = (item.retryCount || 0) + 1;
    if (item.retryCount >= 10) {
      item.status = "failed";
    }
    await db.put("syncQueue", item);
  }
}
