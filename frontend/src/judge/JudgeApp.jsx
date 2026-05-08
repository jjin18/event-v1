import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { authByQR, fetchJudgeProjects, fetchJudgeScores } from "../lib/api.js";
import {
  loadProfile, saveProfile,
  saveProjects, saveScore,
  loadScores, loadProjects,
} from "../lib/db.js";
import { scoreKey } from "../lib/db.js";
import Dashboard from "./Dashboard.jsx";

export default function JudgeApp() {
  const [params] = useSearchParams();
  const [state, setState] = useState(null);   // null=loading, false=unauthed, obj=ready
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => { bootstrap(); }, []);

  async function bootstrap() {
    // 1. QR token in URL
    const token = params.get("token");
    if (token) {
      try {
        const data = await authByQR(token);
        persistSession(data, token);
        setState(buildState(data.judge, data.event, data.projects || [], data.scores || []));
      } catch {
        setErrorMsg("QR code is invalid or expired.");
        setState(false);
      }
      return;
    }

    // 2. No token at all → back to login
    const savedToken = localStorage.getItem("judge_token");
    if (!savedToken) {
      window.location.replace("/");
      return;
    }

    // 3. Try IndexedDB (full offline-first path)
    try {
      const profile = await loadProfile();
      if (profile?.judge) {
        const age = Date.now() - (profile.savedAt || 0);
        if (age < 30 * 24 * 60 * 60 * 1000) {
          const [projects, scores] = await Promise.all([loadProjects(), loadScores()]);
          setState(buildState(profile.judge, profile.event, projects, Object.values(scores)));
          return;
        }
      }
    } catch { /* IndexedDB unavailable — try next fallback */ }

    // 4. localStorage fallback profile + fetch from server
    try {
      const saved = JSON.parse(localStorage.getItem("judge_data") || "null");
      if (saved?.judge) {
        const [projRes, scoresRes] = await Promise.all([
          fetchJudgeProjects().catch(() => ({ projects: [] })),
          fetchJudgeScores().catch(() => ({ scores: [] })),
        ]);
        setState(buildState(
          saved.judge,
          saved.event,
          projRes?.projects || [],
          scoresRes?.scores || [],
        ));
        return;
      }
    } catch { /* Server unreachable */ }

    // 5. Give up — clear stale tokens and send to login
    localStorage.removeItem("judge_token");
    localStorage.removeItem("judge_data");
    window.location.replace("/");
  }

  function buildState(judge, event, projectsArr, scoresArr) {
    const projects = sortByTable(projectsArr);
    const scores = {};
    for (const s of scoresArr) {
      const k = scoreKey(s.judge_id ?? judge.id, s.project_id ?? s.projectId);
      scores[k] = { ...s, key: k, syncStatus: s.syncStatus || "synced" };
    }
    return { judge, event, projects, scores };
  }

  function persistSession(data, token) {
    if (token) localStorage.setItem("judge_token", token);
    localStorage.setItem("judge_data", JSON.stringify({
      judge: data.judge,
      event: data.event,
      savedAt: Date.now(),
    }));
    // Best-effort IndexedDB — don't await, don't block render
    (async () => {
      try {
        await saveProfile({ judge: data.judge, event: data.event, token, savedAt: Date.now() });
        if (data.projects?.length) await saveProjects(data.projects);
        if (data.scores?.length) {
          for (const s of data.scores) {
            await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
          }
        }
      } catch {}
    })();
  }

  function sortByTable(list) {
    return [...(list || [])].sort(
      (a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
    );
  }

  if (state === null && !errorMsg) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <span className="text-blue-300">Loading your session…</span>
        </div>
      </div>
    );
  }

  if (errorMsg || !state) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{errorMsg || "Session expired."}</p>
          <a href="/" className="text-blue-300 underline text-sm">Back to login</a>
        </div>
      </div>
    );
  }

  return <Dashboard {...state} />;
}
