import React from "react";

export default function ProgressSection({ projects, scores, activeProjectId, onSelectProject }) {
  const total = projects.length;
  const scored = Object.keys(scores).length;
  const pct = total ? Math.round((scored / total) * 100) : 0;

  return (
    <div className="border-t border-gray-100">
      <div className="px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <span className="font-semibold text-gray-800 text-sm uppercase tracking-wide">My Progress</span>
          <span className="text-xs text-gray-500 font-medium">{scored}/{total}</span>
        </div>

        <div className="w-full bg-gray-200 rounded-full h-2 mb-1">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="text-xs text-gray-500 mb-3">{pct}% complete</div>

        <div className="space-y-1 max-h-64 overflow-y-auto">
          {projects.map((p) => {
            const key = `judge_${scores._judgeId}_project_${p.id}`;
            const isScored = !!scores[`judge_${scores._judgeId}_project_${p.id}`];
            const isActive = p.id === activeProjectId;

            return (
              <button
                key={p.id}
                onClick={() => onSelectProject(p.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
                  isActive ? "bg-blue-50 border border-blue-200" : "hover:bg-gray-50"
                }`}
              >
                <span className="text-base leading-none">
                  {isScored ? "🟢" : isActive ? "🟡" : "⚪"}
                </span>
                <span className="text-gray-400 font-mono w-10 shrink-0">
                  {p.table_number ? `T${p.table_number.padStart(2, "0")}` : "—"}
                </span>
                <span className={`font-medium truncate ${isActive ? "text-blue-700" : "text-gray-700"}`}>
                  {p.title}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
