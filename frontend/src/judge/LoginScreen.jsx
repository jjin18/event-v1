import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { authByPIN, authByQR } from "../lib/api.js";
import { saveProfile, saveProjects, saveScore, scoreKey } from "../lib/db.js";

export default function LoginScreen({ onLogin }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [pin, setPin] = useState("");
  const [eventId, setEventId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("pin"); // "pin" | "qr"

  // QR token auto-auth
  useEffect(() => {
    const token = params.get("token");
    if (token) {
      setLoading(true);
      authByQR(token)
        .then((data) => handleSuccess(data, token))
        .catch(() => setError("Invalid or expired QR code. Please use your PIN."))
        .finally(() => setLoading(false));
    }
  }, []);

  async function handleSuccess(data, token) {
    const t = token || data.token;
    if (t) localStorage.setItem("judge_token", t);

    await saveProfile({
      judge: data.judge,
      event: data.event,
      token: t,
      savedAt: Date.now(),
    });

    if (data.projects?.length) {
      await saveProjects(data.projects);
    }

    if (data.scores?.length) {
      for (const s of data.scores) {
        await saveScore(s.judge_id, s.project_id, {
          ...s,
          syncStatus: "synced",
        });
      }
    }

    onLogin(data);
    navigate("/judge");
  }

  async function handlePINSubmit(e) {
    e.preventDefault();
    if (pin.length !== 6) {
      setError("PIN must be 6 digits");
      return;
    }
    if (!eventId) {
      setError("Enter your event ID");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await authByPIN(pin, parseInt(eventId));
      await handleSuccess(data, data.token);
    } catch (err) {
      setError(err.message || "Invalid PIN");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-8">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <svg className="w-9 h-9 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Hackathon Judge</h1>
          <p className="text-gray-500 text-sm mt-1">Enter your credentials to start judging</p>
        </div>

        {loading && (
          <div className="text-center py-4">
            <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-gray-500 mt-2 text-sm">Authenticating...</p>
          </div>
        )}

        {!loading && (
          <form onSubmit={handlePINSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event ID</label>
              <input
                type="number"
                value={eventId}
                onChange={(e) => setEventId(e.target.value)}
                placeholder="1"
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg text-center tracking-widest focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">6-Digit PIN</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={pin}
                onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                className="w-full border border-gray-300 rounded-lg px-4 py-3 text-2xl text-center tracking-[0.5em] font-mono focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                required
              />
            </div>
            {error && (
              <p className="text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">{error}</p>
            )}
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold text-lg hover:bg-blue-700 active:scale-95 transition-all"
            >
              Start Judging
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
