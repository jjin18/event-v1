import React, { useEffect, useState } from "react";
import { adminLogin, fetchEvents } from "../lib/api.js";
import EventSidebar from "./EventSidebar.jsx";
import SetupTab from "./tabs/SetupTab.jsx";
import ProjectsTab from "./tabs/ProjectsTab.jsx";
import JudgesTab from "./tabs/JudgesTab.jsx";
import LeaderboardTab from "./tabs/LeaderboardTab.jsx";

export default function AdminApp() {
  const [authed, setAuthed] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState([]);
  const [activeEventId, setActiveEventId] = useState(null);
  const [activeTab, setActiveTab] = useState("setup");

  useEffect(() => {
    const t = localStorage.getItem("admin_token");
    if (t) {
      setAuthed(true);
      loadEvents();
    }
  }, []);

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await adminLogin(password);
      localStorage.setItem("admin_token", data.token);
      setAuthed(true);
      await loadEvents();
    } catch {
      setError("Invalid password");
    } finally {
      setLoading(false);
    }
  }

  async function loadEvents() {
    try {
      const data = await fetchEvents();
      setEvents(data.events || []);
      if (data.events?.length && !activeEventId) {
        setActiveEventId(data.events[0].id);
      }
    } catch {
      localStorage.removeItem("admin_token");
      setAuthed(false);
    }
  }

  function handleEventCreated(ev) {
    setEvents((prev) => [ev, ...prev]);
    setActiveEventId(ev.id);
    setActiveTab("setup");
  }

  function handleEventUpdated(ev) {
    setEvents((prev) => prev.map((e) => (e.id === ev.id ? ev : e)));
  }

  if (!authed) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm p-8">
          <div className="text-center mb-8">
            <div className="w-14 h-14 bg-gray-900 rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Admin</h1>
            <p className="text-gray-500 text-sm mt-1">Organizer workspace</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Admin password"
              className="w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-gray-900 outline-none"
              required
            />
            {error && <p className="text-red-600 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gray-900 text-white py-3 rounded-xl font-semibold hover:bg-gray-700 transition-colors disabled:opacity-60"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const activeEvent = events.find((e) => e.id === activeEventId) || null;

  const TABS = [
    { id: "setup", label: "Setup" },
    { id: "projects", label: "Projects" },
    { id: "judges", label: "Judges" },
    { id: "leaderboard", label: "Leaderboard" },
  ];

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <EventSidebar
        events={events}
        activeEventId={activeEventId}
        onSelect={setActiveEventId}
        onEventCreated={handleEventCreated}
        onLogout={() => {
          localStorage.removeItem("admin_token");
          setAuthed(false);
        }}
      />

      {/* Main workspace */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tab bar */}
        <div className="bg-white border-b border-gray-200 px-6">
          <div className="flex items-center gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
            {activeEvent && (
              <div className="ml-auto py-2">
                <span className="text-xs text-gray-400">Event ID: </span>
                <span className="text-xs font-mono font-bold text-gray-700">{activeEvent.id}</span>
              </div>
            )}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-6">
          {!activeEvent ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              Create or select an event from the sidebar
            </div>
          ) : activeTab === "setup" ? (
            <SetupTab event={activeEvent} onUpdated={handleEventUpdated} />
          ) : activeTab === "projects" ? (
            <ProjectsTab eventId={activeEvent.id} />
          ) : activeTab === "judges" ? (
            <JudgesTab eventId={activeEvent.id} event={activeEvent} />
          ) : (
            <LeaderboardTab eventId={activeEvent.id} />
          )}
        </div>
      </div>
    </div>
  );
}
