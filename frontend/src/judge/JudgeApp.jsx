import React, { useEffect, useState } from "react";
import { Routes, Route, useNavigate, useSearchParams } from "react-router-dom";
import LoginScreen from "./LoginScreen.jsx";
import Dashboard from "./Dashboard.jsx";
import { loadProfile, loadProjects, loadScores, saveProjects, saveScore } from "../lib/db.js";
import { authByQR, fetchJudgeProjects, fetchJudgeScores } from "../lib/api.js";

export default function JudgeApp() {
  const [authState, setAuthState] = useState(null); // null = loading, false = not authed, object = authed
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    restoreSession();
  }, []);

  async function restoreSession() {
    // 1. Try IndexedDB first — instant, no network
    try {
      const profile = await loadProfile();
      if (profile?.token && profile?.judge) {
        // Check token not expired (30 days)
        const age = Date.now() - (profile.savedAt || 0);
        if (age < 30 * 24 * 60 * 60 * 1000) {
          localStorage.setItem("judge_token", profile.token);

          const [projects, scoresMap] = await Promise.all([
            loadProjects(),
            loadScores(),
          ]);

          setAuthState({
            judge: profile.judge,
            event: profile.event,
            projects: projects.sort((a, b) =>
              (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
            ),
            scores: scoresMap,
          });

          // Background: try to refresh from server
          refreshFromServer(profile.token, profile.judge, profile.event, projects, scoresMap);
          return;
        }
      }
    } catch {
      // IndexedDB unavailable — fall through
    }

    // 2. Check for QR token in URL
    const token = searchParams.get("token");
    if (token) {
      try {
        const data = await authByQR(token);
        localStorage.setItem("judge_token", token);
        handleLogin({ ...data, token });
        return;
      } catch {
        // fall through to login screen
      }
    }

    setAuthState(false);
  }

  async function refreshFromServer(token, judge, event, localProjects, localScores) {
    // Silently merge fresher server data without blocking UI
    try {
      const [projRes, scoresRes] = await Promise.all([
        fetchJudgeProjects(),
        fetchJudgeScores(),
      ]);

      if (projRes?.projects?.length) {
        await saveProjects(projRes.projects);
      }
      if (scoresRes?.scores?.length) {
        for (const s of scoresRes.scores) {
          const localKey = `judge_${s.judge_id}_project_${s.project_id}`;
          const local = localScores[localKey];
          if (!local || new Date(s.updated_at) > new Date(local.updatedAt || 0)) {
            await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
          }
        }
      }
    } catch {
      // Offline or server error — local data is fine
    }
  }

  async function handleLogin(data) {
    if (data.projects?.length) await saveProjects(data.projects);

    const scoresMap = await loadScores();

    setAuthState({
      judge: data.judge,
      event: data.event,
      projects: (data.projects || []).sort(
        (a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
      ),
      scores: scoresMap,
    });
    navigate("/judge");
  }

  // Loading state — restore within ~200ms from IndexedDB
  if (authState === null) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="login"
        element={
          authState ? (
            <Dashboard {...authState} />
          ) : (
            <LoginScreen onLogin={handleLogin} />
          )
        }
      />
      <Route
        path="*"
        element={
          authState ? (
            <Dashboard {...authState} />
          ) : (
            <LoginScreen onLogin={handleLogin} />
          )
        }
      />
    </Routes>
  );
}
