import React, { useState } from "react";
import { createEvent } from "../lib/api.js";

export default function EventSidebar({ events, activeEventId, onSelect, onEventCreated, onLogout }) {
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setLoading(true);
    try {
      const ev = await createEvent({ name: newName.trim() });
      onEventCreated(ev);
      setNewName("");
      setCreating(false);
    } catch {
      alert("Failed to create event");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-56 bg-gray-900 text-white flex flex-col shrink-0 h-full">
      <div className="px-4 py-5 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">H</div>
          <span className="font-semibold text-sm">Hackathon Admin</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-3">
        {/* New event button */}
        {creating ? (
          <form onSubmit={handleCreate} className="px-3 mb-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Event name"
              className="w-full bg-gray-800 text-white text-sm px-3 py-2 rounded-lg border border-gray-600 focus:border-blue-500 outline-none mb-1"
              autoFocus
            />
            <div className="flex gap-1">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 bg-blue-600 text-xs py-1.5 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
              >
                Create
              </button>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="flex-1 bg-gray-700 text-xs py-1.5 rounded-lg hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <button
            onClick={() => setCreating(true)}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-300 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <span className="text-lg leading-none">+</span>
            <span>New event</span>
          </button>
        )}

        <div className="mt-1 border-t border-gray-700 pt-2">
          {events.map((ev) => (
            <button
              key={ev.id}
              onClick={() => onSelect(ev.id)}
              className={`w-full flex items-center gap-2 px-4 py-2.5 text-left text-sm transition-colors ${
                ev.id === activeEventId
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <span className="text-base">{ev.id === activeEventId ? "⚡" : "🎓"}</span>
              <span className="truncate">{ev.name}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-gray-700 p-3">
        <button
          onClick={onLogout}
          className="w-full text-xs text-gray-400 hover:text-white py-2 transition-colors"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
