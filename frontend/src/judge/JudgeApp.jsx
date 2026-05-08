import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { authByQR } from "../lib/api.js";
import {
  loadProfile, saveProfile,
  saveProjects, saveScore,
  loadScores, loadProjects,
} from "../lib/db.js";
import Dashboard from "./Dashboard.jsx";

export default function JudgeApp() {
  const [params] = useSearchParams();
  const [state, setState] = useState(null);  // null = loading, false = unauthed, object = ready
  const [error, setError] = useState("");

  useEffect(() => {
    bootstrap();
  }, []);

  async function bootstrap() {
    // 1. QR token in URL — takes priority
    const token = params.get("token");
    if (token) {
      try {
        const data = await authByQR(token);
        const ready = await buildState(data, token);
        setState(ready);
        return;
      } catch {
        setError("QR code is invalid or expired.");
        setState(false);
        return;
      }
    }

    // 2. Existing token in localStorage
    const existingToken = localStorage.getItem("judge_token");
    if (!existingToken) {
      window.location.replace("/");
      return;
    }

    // 3. Load session from IndexedDB
    try {
      const profile = await loadProfile();
      if (profile?.judge && profile?.event) {
        const age = Date.now() - (profile.savedAt || 0);
        if (age < 30 * 24 * 60 * 60 * 1000) {
          const [projects, scores] = await Promise.all([loadProjects(), loadScores()]);
          setState({
            judge: profile.judge,
            event: profile.event,
            projects: sortByTable(projects),
            scores,
          });
          return;
        }
      }
    } catch { /* IndexedDB unavailable */ }

    // No valid session — back to login
    localStorage.removeItem("judge_token");
    window.location.replace("/");
  }

  async function buildState(data, token) {
    if (token) localStorage.setItem("judge_token", token);
    await saveProfile({ judge: data.judge, event: data.event, token, savedAt: Date.now() });
    if (data.projects?.length) await saveProjects(data.projects);
    if (data.scores?.length) {
      for (const s of data.scores) {
        await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
      }
    }
    const scores = await loadScores();
    return {
      judge: data.judge,
      event: data.event,
      projects: sortByTable(data.projects || await loadProjects()),
      scores,
    };
  }

  function sortByTable(list) {
    return [...(list || [])].sort(
      (a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
    );
  }

  // Loading
  if (state === null) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center">
        {error ? (
          <div className="text-center">
            <p className="text-red-400 mb-4">{error}</p>
            <a href="/" className="text-blue-300 underline text-sm">Back to login</a>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-blue-300">Loading your session…</span>
          </div>
        )}
      </div>
    );
  }

  // Unauthed — redirect handled above, this is just a safety fallback
  if (!state) {
    return null;
  }

  return <Dashboard {...state} />;
}
