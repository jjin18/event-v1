import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { authByPIN, authByQR, adminLogin } from "./lib/api.js";
import {
  loadProfile, saveProfile,
  saveProjects, saveScore,
  loadScores, loadProjects,
} from "./lib/db.js";

export default function UnifiedLogin() {
  const [params] = useSearchParams();

  const [code, setCode]       = useState("");
  const [eventId, setEventId] = useState("1");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]     = useState("");
  const [statusMsg, setStatusMsg] = useState("");
  const inputRef = useRef(null);

  const isPin = /^\d+$/.test(code) && code.length > 0;

  useEffect(() => {
    silentRestore();
    inputRef.current?.focus();
  }, []);

  async function silentRestore() {
    // 1. QR token in URL
    const token = params.get("token");
    if (token) {
      setStatusMsg("Authenticating via QR code…");
      try {
        const data = await authByQR(token);
        await persistJudgeSession(data, token);
        window.location.replace("/judge");
        return;
      } catch {
        setStatusMsg("");
      }
    }

    // 2. Saved judge session
    try {
      const profile = await loadProfile();
      if (profile?.token && profile?.judge) {
        const age = Date.now() - (profile.savedAt || 0);
        if (age < 30 * 24 * 60 * 60 * 1000) {
          setStatusMsg("Restoring your session…");
          localStorage.setItem("judge_token", profile.token);
          window.location.replace("/judge");
          return;
        }
      }
    } catch { /* IndexedDB unavailable — show form */ }

    // 3. Saved admin session
    const adminToken = localStorage.getItem("admin_token");
    if (adminToken) {
      window.location.replace("/admin");
      return;
    }

    setStatusMsg("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      if (isPin) {
        if (code.length !== 6) {
          setError("PIN must be exactly 6 digits.");
          setSubmitting(false);
          return;
        }
        const data = await authByPIN(code, parseInt(eventId, 10));
        await persistJudgeSession(data, data.token);
        window.location.replace("/judge");
      } else {
        const data = await adminLogin(code);
        localStorage.setItem("admin_token", data.token);
        window.location.replace("/admin");
      }
    } catch {
      setError(isPin
        ? "PIN not recognised — check your Event ID or ask the organizer."
        : "Incorrect password."
      );
      setSubmitting(false);
    }
  }

  async function persistJudgeSession(data, token) {
    if (token) localStorage.setItem("judge_token", token);
    await saveProfile({ judge: data.judge, event: data.event, token, savedAt: Date.now() });
    if (data.projects?.length) await saveProjects(data.projects);
    if (data.scores?.length) {
      for (const s of data.scores) {
        await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-blue-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-blue-900/50">
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white">Hackathon Judge</h1>
          <p className="text-blue-300 text-sm mt-1">
            {isPin ? "Judge PIN login" : code.length > 0 ? "Organizer login" : "Enter your PIN or admin password"}
          </p>
        </div>

        {/* Non-blocking status (session restore in progress) */}
        {statusMsg && (
          <div className="flex items-center gap-2 justify-center mb-4">
            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-blue-300 text-sm">{statusMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-2xl p-8 space-y-4">

          {/* Event ID — only when typing a PIN */}
          {isPin && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event ID</label>
              <input
                type="number"
                value={eventId}
                onChange={(e) => setEventId(e.target.value)}
                min="1"
                placeholder="1"
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-center text-lg font-mono tracking-widest focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
              />
              <p className="text-xs text-gray-400 mt-1">Ask the organizer for the event ID.</p>
            </div>
          )}

          {/* Code field */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {isPin ? "PIN" : "Access code"}
            </label>
            <input
              ref={inputRef}
              type="text"
              inputMode={isPin ? "numeric" : "text"}
              autoComplete="off"
              value={code}
              onChange={(e) => {
                const v = e.target.value;
                setCode(isPin ? v.replace(/\D/g, "").slice(0, 6) : v);
              }}
              placeholder="PIN or password"
              className={`w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none ${
                isPin ? "text-2xl text-center tracking-[0.5em] font-mono" : "text-base"
              }`}
              disabled={submitting}
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
            disabled={submitting || !code}
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold text-base hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {submitting
              ? <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Signing in…</>
              : "Continue →"
            }
          </button>
        </form>

        <p className="text-center text-blue-400/50 text-xs mt-6">
          Scores saved offline · syncs automatically
        </p>
      </div>
    </div>
  );
}
