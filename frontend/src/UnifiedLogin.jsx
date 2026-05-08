import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authByPIN, authByQR, adminLogin } from "./lib/api.js";
import {
  loadProfile,
  saveProfile,
  saveProjects,
  saveScore,
  loadScores,
  loadProjects,
} from "./lib/db.js";

/**
 * Single entry-point login.
 *
 * Resolution order:
 *  1. QR token in URL  → judge auth → /judge
 *  2. Saved judge session in IndexedDB → /judge  (instant, no network)
 *  3. Saved admin token in localStorage → /admin  (instant)
 *  4. Show login form — 6-digit code tries judge PIN, anything else tries admin password
 *     A second "Event ID" field appears only when the input looks like a PIN.
 */
export default function UnifiedLogin({ onJudgeLogin, onAdminLogin }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [code, setCode] = useState("");
  const [eventId, setEventId] = useState("1");
  const [loading, setLoading] = useState(true); // starts true — checking saved sessions
  const [loadingMsg, setLoadingMsg] = useState("Checking saved session…");
  const [error, setError] = useState("");

  const looksLikePin = /^\d{1,6}$/.test(code);

  // ── On mount: restore saved sessions or handle QR token ──────────────────
  useEffect(() => {
    bootstrap();
  }, []);

  async function bootstrap() {
    // 1. QR token in URL — highest priority
    const token = params.get("token");
    if (token) {
      setLoadingMsg("Authenticating via QR code…");
      try {
        const data = await authByQR(token);
        await persistJudge(data, token);
        onJudgeLogin(data);
        navigate("/judge", { replace: true });
        return;
      } catch {
        // Bad / expired token — fall through to form
      }
    }

    // 2. Saved judge session in IndexedDB
    try {
      const profile = await loadProfile();
      if (profile?.token && profile?.judge) {
        const age = Date.now() - (profile.savedAt || 0);
        if (age < 30 * 24 * 60 * 60 * 1000) {
          setLoadingMsg("Restoring your session…");
          localStorage.setItem("judge_token", profile.token);
          const [projects, scores] = await Promise.all([loadProjects(), loadScores()]);
          onJudgeLogin({
            judge: profile.judge,
            event: profile.event,
            projects: sortProjects(projects),
            scores,
          });
          navigate("/judge", { replace: true });
          return;
        }
      }
    } catch { /* IndexedDB unavailable */ }

    // 3. Saved admin token
    const adminToken = localStorage.getItem("admin_token");
    if (adminToken) {
      onAdminLogin({ token: adminToken });
      navigate("/admin", { replace: true });
      return;
    }

    // 4. Show login form
    setLoading(false);
  }

  // ── Submit handler — tries PIN then admin password ────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (looksLikePin) {
      // Try judge PIN
      if (code.length !== 6) {
        setError("Judge PINs are exactly 6 digits.");
        setLoading(false);
        return;
      }
      setLoadingMsg("Verifying PIN…");
      try {
        const data = await authByPIN(code, parseInt(eventId, 10));
        await persistJudge(data, data.token);
        onJudgeLogin(data);
        navigate("/judge", { replace: true });
        return;
      } catch {
        setError("PIN not recognised for that event. Check your event ID or use your QR card.");
        setLoading(false);
        return;
      }
    }

    // Try admin password
    setLoadingMsg("Signing in as organizer…");
    try {
      const data = await adminLogin(code);
      localStorage.setItem("admin_token", data.token);
      onAdminLogin(data);
      navigate("/admin", { replace: true });
    } catch {
      setError("Incorrect password.");
      setLoading(false);
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
  async function persistJudge(data, token) {
    if (token) localStorage.setItem("judge_token", token);
    await saveProfile({ judge: data.judge, event: data.event, token, savedAt: Date.now() });
    if (data.projects?.length) await saveProjects(data.projects);
    if (data.scores?.length) {
      for (const s of data.scores) {
        await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
      }
    }
  }

  function sortProjects(p) {
    return [...p].sort((a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0));
  }

  // ── Loading state ─────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center">
        <div className="text-center text-white">
          <div className="w-10 h-10 border-4 border-blue-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-blue-200 text-sm">{loadingMsg}</p>
        </div>
      </div>
    );
  }

  // ── Login form ────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo / wordmark */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-900/50">
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">Hackathon Judge</h1>
          <p className="text-blue-300 text-sm mt-1">Enter your PIN or admin password to continue</p>
        </div>

        {/* Card */}
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-2xl p-8 space-y-4">
          {/* Contextual hint */}
          <div className={`text-xs rounded-lg px-3 py-2 transition-colors ${
            code === "" ? "bg-gray-50 text-gray-400" :
            looksLikePin ? "bg-blue-50 text-blue-600" : "bg-purple-50 text-purple-600"
          }`}>
            {code === "" && "Judge? Enter your 6-digit PIN.  Organizer? Enter your admin password."}
            {code !== "" && looksLikePin && "Looks like a judge PIN — enter 6 digits to continue."}
            {code !== "" && !looksLikePin && "Looks like an admin password — sign in as organizer."}
          </div>

          {/* Event ID — only shown for PIN flow */}
          {looksLikePin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event ID</label>
              <input
                type="number"
                value={eventId}
                onChange={(e) => setEventId(e.target.value)}
                placeholder="1"
                min="1"
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-center text-lg font-mono tracking-widest focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
              />
              <p className="text-xs text-gray-400 mt-1">Ask the organizer for the event ID if unsure.</p>
            </div>
          )}

          {/* Code / password field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {looksLikePin ? "Judge PIN" : "Access code"}
            </label>
            <input
              type={looksLikePin ? "text" : "password"}
              inputMode={looksLikePin ? "numeric" : "text"}
              maxLength={looksLikePin ? 6 : undefined}
              value={code}
              onChange={(e) => setCode(looksLikePin ? e.target.value.replace(/\D/g, "") : e.target.value)}
              placeholder={looksLikePin ? "000000" : "Password"}
              className={`w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all ${
                looksLikePin ? "text-2xl text-center tracking-[0.5em] font-mono" : "text-base"
              }`}
              autoFocus
              required
            />
          </div>

          {error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-100 px-3 py-2 rounded-lg">{error}</p>
          )}

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold text-base hover:bg-blue-700 active:scale-[0.98] transition-all"
          >
            Continue →
          </button>
        </form>

        <p className="text-center text-blue-400/60 text-xs mt-6">
          Scores are saved offline and sync automatically
        </p>
      </div>
    </div>
  );
}
