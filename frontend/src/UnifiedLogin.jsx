import React, { useEffect, useRef, useState } from "react";
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

export default function UnifiedLogin({ onJudgeLogin, onAdminLogin }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const [code, setCode] = useState("");
  const [eventId, setEventId] = useState("1");
  const [phase, setPhase] = useState("booting"); // "booting" | "form" | "submitting"
  const [loadingMsg, setLoadingMsg] = useState("Checking saved session…");
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  // "Looks like a PIN" once user has typed at least one digit
  // We commit to PIN mode once we see a digit, admin mode otherwise
  const looksLikePin = code.length === 0 ? null : /^\d+$/.test(code);

  // ── Session restore / QR auto-auth ───────────────────────────────────────
  useEffect(() => {
    bootstrap().catch(() => setPhase("form")); // safety net — always show form on error
  }, []);

  async function bootstrap() {
    // 1. QR token in URL
    const token = params.get("token");
    if (token) {
      setLoadingMsg("Authenticating via QR code…");
      try {
        const data = await authByQR(token);
        const ready = await buildJudgeState(data, token);
        onJudgeLogin(ready);
        navigate("/judge", { replace: true });
        return;
      } catch {
        // Bad/expired QR — fall through to form
      }
    }

    // 2. Saved judge session (IndexedDB — instant, no network)
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
            projects: sortByTable(projects),
            scores, // already a keyed map from loadScores()
          });
          navigate("/judge", { replace: true });
          return;
        }
      }
    } catch { /* IndexedDB blocked (private mode etc) — show form */ }

    // 3. Saved admin token
    const adminToken = localStorage.getItem("admin_token");
    if (adminToken) {
      onAdminLogin({ token: adminToken });
      navigate("/admin", { replace: true });
      return;
    }

    // 4. Nothing found — show form
    setPhase("form");
    setTimeout(() => inputRef.current?.focus(), 50);
  }

  // ── Form submit ───────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setPhase("submitting");

    try {
      if (looksLikePin) {
        if (code.length !== 6) {
          setError("Enter your full 6-digit PIN.");
          setPhase("form");
          return;
        }
        setLoadingMsg("Verifying PIN…");
        const data = await authByPIN(code, parseInt(eventId, 10));
        const ready = await buildJudgeState(data, data.token);
        onJudgeLogin(ready);
        navigate("/judge", { replace: true });
      } else {
        setLoadingMsg("Signing in as organizer…");
        const data = await adminLogin(code);
        localStorage.setItem("admin_token", data.token);
        onAdminLogin(data);
        navigate("/admin", { replace: true });
      }
    } catch (err) {
      const msg = err?.message || "";
      if (looksLikePin) {
        setError("PIN not recognised. Double-check your event ID, or ask the organizer.");
      } else {
        setError("Incorrect password.");
      }
      setPhase("form");
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  // Persist to IndexedDB and return a dashboard-ready state object.
  // Critically: converts server scores array → keyed map before returning.
  async function buildJudgeState(data, token) {
    if (token) localStorage.setItem("judge_token", token);
    await saveProfile({ judge: data.judge, event: data.event, token, savedAt: Date.now() });
    if (data.projects?.length) await saveProjects(data.projects);
    if (data.scores?.length) {
      for (const s of data.scores) {
        await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
      }
    }
    // Always read back from IndexedDB — gives us the correct keyed-map format
    const [projects, scores] = await Promise.all([
      data.projects?.length ? Promise.resolve(data.projects) : loadProjects(),
      loadScores(),
    ]);
    return {
      judge: data.judge,
      event: data.event,
      projects: sortByTable(projects),
      scores, // keyed map: "judge_1_project_3" → score object
    };
  }

  function sortByTable(list) {
    return [...list].sort((a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0));
  }

  // ── Loading / booting screen ──────────────────────────────────────────────
  if (phase === "booting" || phase === "submitting") {
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
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-900/50">
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">Hackathon Judge</h1>
          <p className="text-blue-300 text-sm mt-1">
            {looksLikePin === null && "Enter your 6-digit PIN or admin password"}
            {looksLikePin === true && "Enter your 6-digit judge PIN"}
            {looksLikePin === false && "Enter your organizer password"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-2xl p-8 space-y-4">
          {/* Event ID — only for PIN flow */}
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
              <p className="text-xs text-gray-400 mt-1">Ask the organizer if you don't know your event ID.</p>
            </div>
          )}

          {/* Single code / password input — type stays "text" to avoid focus reset on mobile */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {looksLikePin ? "PIN" : "Access code"}
            </label>
            <input
              ref={inputRef}
              type="text"
              inputMode={looksLikePin === false ? "text" : "numeric"}
              autoComplete="off"
              value={code}
              onChange={(e) => {
                const v = e.target.value;
                // Once in PIN mode, digits only
                if (looksLikePin) {
                  setCode(v.replace(/\D/g, "").slice(0, 6));
                } else {
                  setCode(v);
                }
              }}
              placeholder="PIN or password"
              className={`w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none ${
                looksLikePin ? "text-2xl text-center tracking-[0.5em] font-mono" : "text-base"
              }`}
              required
            />
          </div>

          {error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-100 px-3 py-2 rounded-lg">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold text-base hover:bg-blue-700 active:scale-[0.98] transition-all"
          >
            Continue →
          </button>
        </form>

        <p className="text-center text-blue-400/50 text-xs mt-6">
          Scores saved offline · syncs automatically
        </p>
      </div>
    </div>
  );
}
