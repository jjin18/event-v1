import React, { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import UnifiedLogin from "./UnifiedLogin.jsx";
import JudgeDashboard from "./judge/Dashboard.jsx";
import AdminWorkspace from "./admin/AdminApp.jsx";

/**
 * Root router.
 *
 * Auth state lives here so both apps share the same resolved identity.
 * UnifiedLogin resolves who you are (judge vs admin) then calls the
 * appropriate setter; subsequent renders skip the login screen entirely.
 */
export default function App() {
  const [judgeState, setJudgeState] = useState(null);  // {judge, event, projects, scores}
  const [adminState, setAdminState] = useState(null);  // {token, ...}

  function handleJudgeLogin(data) {
    setJudgeState({
      judge: data.judge,
      event: data.event,
      projects: (data.projects || []).sort(
        (a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
      ),
      scores: data.scores || {},
    });
  }

  function handleAdminLogin(data) {
    setAdminState(data);
  }

  return (
    <Routes>
      {/* ── Unified entry point ── */}
      <Route
        path="/"
        element={
          judgeState ? (
            <Navigate to="/judge" replace />
          ) : adminState ? (
            <Navigate to="/admin" replace />
          ) : (
            <UnifiedLogin
              onJudgeLogin={handleJudgeLogin}
              onAdminLogin={handleAdminLogin}
            />
          )
        }
      />

      {/* ── QR token landing: /judge?token=... goes through UnifiedLogin ── */}
      <Route
        path="/judge"
        element={
          judgeState ? (
            <JudgeDashboard {...judgeState} />
          ) : (
            <UnifiedLogin
              onJudgeLogin={handleJudgeLogin}
              onAdminLogin={handleAdminLogin}
            />
          )
        }
      />

      {/* ── Admin workspace ── */}
      <Route
        path="/admin/*"
        element={
          adminState ? (
            <AdminWorkspace initialToken={adminState.token} />
          ) : (
            <UnifiedLogin
              onJudgeLogin={handleJudgeLogin}
              onAdminLogin={handleAdminLogin}
            />
          )
        }
      />

      {/* ── Fallback ── */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
