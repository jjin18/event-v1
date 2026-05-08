import {
  enqueue,
  getPendingQueue,
  incrementRetry,
  markQueueItemDone,
  markScoreSynced,
} from "./db.js";
import { submitScore } from "./api.js";

let _syncing = false;
let _listeners = [];

export function onSyncStatusChange(fn) {
  _listeners.push(fn);
  return () => {
    _listeners = _listeners.filter((l) => l !== fn);
  };
}

function emit(status) {
  _listeners.forEach((fn) => fn(status));
}

export async function queueScore(judgeId, scoreData) {
  await enqueue({ type: "score", judgeId, scoreData });
  flushQueue();
}

export async function flushQueue() {
  if (_syncing) return;
  if (!navigator.onLine) {
    emit("offline");
    return;
  }
  _syncing = true;
  emit("syncing");

  try {
    const pending = await getPendingQueue();
    for (const item of pending) {
      try {
        if (item.type === "score") {
          await submitScore(item.scoreData);
          await markScoreSynced(item.judgeId, item.scoreData.project_id);
        }
        await markQueueItemDone(item.id);
      } catch {
        await incrementRetry(item.id);
      }
    }
    const remaining = await getPendingQueue();
    emit(remaining.length === 0 ? "synced" : "pending");
  } catch {
    emit("error");
  } finally {
    _syncing = false;
  }
}

// Poll every 20s as fallback when service worker Background Sync is unavailable
let _pollTimer = null;

export function startSyncPoller() {
  if (_pollTimer) return;
  _pollTimer = setInterval(() => {
    if (navigator.onLine) flushQueue();
  }, 20_000);

  window.addEventListener("online", () => flushQueue());
}

export function stopSyncPoller() {
  if (_pollTimer) {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }
}
