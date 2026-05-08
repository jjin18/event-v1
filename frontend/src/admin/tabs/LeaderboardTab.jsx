import React, { useEffect, useState } from "react";
import { fetchLeaderboard } from "../../lib/api.js";

export default function LeaderboardTab({ eventId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, [eventId]);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchLeaderboard(eventId);
      setRows(data.leaderboard || []);
    } finally {
      setLoading(false);
    }
  }

  function download(path, filename) {
    const token = localStorage.getItem("admin_token");
    fetch(`${path}?event_id=${eventId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
      });
  }

  const scored = rows.filter((r) => r.judge_count > 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Leaderboard</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => load()}
            className="text-sm text-gray-600 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            ↻ Refresh
          </button>
          <button
            onClick={() => download("/api/admin/export/scores", "scores.csv")}
            className="text-sm text-gray-600 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Export scores CSV
          </button>
          <button
            onClick={() => download("/api/admin/export/leaderboard", "leaderboard.csv")}
            className="text-sm text-gray-600 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Export leaderboard CSV
          </button>
          <button
            onClick={() => download("/api/admin/export/luma", "luma_winners.csv")}
            className="text-sm text-white bg-purple-600 hover:bg-purple-700 px-3 py-1.5 rounded-lg font-medium"
          >
            Luma top-10 CSV
          </button>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="text-2xl font-black text-gray-900">{rows.length}</div>
          <div className="text-sm text-gray-500">Total projects</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="text-2xl font-black text-blue-600">{scored.length}</div>
          <div className="text-sm text-gray-500">Scored projects</div>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <div className="text-2xl font-black text-green-600">
            {scored.length > 0 ? (scored.reduce((a, r) => a + (r.judge_count || 0), 0) / scored.length).toFixed(1) : "—"}
          </div>
          <div className="text-sm text-gray-500">Avg judges / project</div>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600 w-12">Rank</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Table</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Project</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Team</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Track</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Avg Score</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Judges</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((r, i) => (
                <tr key={r.id} className={i < 3 ? "bg-yellow-50" : "hover:bg-gray-50"}>
                  <td className="px-4 py-3">
                    <span className="font-bold text-gray-700">
                      {i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `#${i + 1}`}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-600">{r.table_number || "—"}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">{r.title}</td>
                  <td className="px-4 py-3 text-gray-600">{r.team_name || "—"}</td>
                  <td className="px-4 py-3">
                    {r.track && (
                      <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs">{r.track}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {r.avg_score != null ? (
                      <div>
                        <span className="font-bold text-gray-900">{parseFloat(r.avg_score).toFixed(2)}</span>
                        <span className="text-gray-400 text-xs">/10</span>
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">{r.judge_count || 0}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-gray-400">
                    No scores yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
