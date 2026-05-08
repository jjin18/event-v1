import React from "react";

export default function TopBar({ event, syncStatus, onMenuClick }) {
  const statusConfig = {
    synced: { icon: "🟢", label: "Synced", color: "text-green-600" },
    syncing: { icon: "🔵", label: "Syncing...", color: "text-blue-600" },
    pending: { icon: "🟡", label: "Pending", color: "text-yellow-600" },
    offline: { icon: "🔴", label: "Offline", color: "text-red-600" },
    error: { icon: "🔴", label: "Sync error", color: "text-red-600" },
  };
  const s = statusConfig[syncStatus] || statusConfig.synced;

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between sticky top-0 z-20 shadow-sm">
      <div className="flex items-center gap-3">
        {onMenuClick && (
          <button
            onClick={onMenuClick}
            className="md:hidden p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Open menu"
          >
            <svg className="w-5 h-5 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
        <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">
          H
        </div>
        <div>
          <div className="font-semibold text-gray-900 text-sm leading-tight">
            {event?.name || "Hackathon"}
          </div>
          <div className="text-xs text-gray-500">{event?.venue}, {event?.city}</div>
        </div>
      </div>

      <div className={`flex items-center gap-1.5 text-xs font-medium ${s.color}`}>
        <span>{s.icon}</span>
        <span className="hidden sm:inline">{s.label}</span>
      </div>
    </div>
  );
}
