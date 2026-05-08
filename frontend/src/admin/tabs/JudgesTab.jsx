import React, { useEffect, useRef, useState } from "react";
import {
  createJudge,
  deleteJudge,
  downloadWithAuth,
  fetchJudges,
  regenerateQR,
} from "../../lib/api.js";

export default function JudgesTab({ eventId, event }) {
  const [judges, setJudges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newForm, setNewForm] = useState({ name: "", email: "", expertise: "", pin: "" });
  const fileRef = useRef();

  useEffect(() => { load(); }, [eventId]);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchJudges(eventId);
      setJudges(data.judges || []);
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd(e) {
    e.preventDefault();
    try {
      const j = await createJudge({ ...newForm, event_id: eventId });
      setJudges((prev) => [...prev, j]);
      setNewForm({ name: "", email: "", expertise: "", pin: "" });
      setAdding(false);
    } catch { alert("Failed to add judge"); }
  }

  async function handleDelete(id) {
    if (!confirm("Deactivate this judge?")) return;
    await deleteJudge(id);
    setJudges((prev) => prev.filter((j) => j.id !== id));
  }

  async function handleRegenQR(id) {
    await regenerateQR(id);
    alert("QR regenerated — download the new QR card.");
  }

  async function handleCSVImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const token = localStorage.getItem("admin_token");
    const res = await fetch(`/api/admin/judges/import?event_id=${eventId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (res.ok) {
      const d = await res.json();
      alert(`Imported ${d.inserted} judges`);
      load();
    }
  }

  function downloadQR(judgeId) {
    const token = localStorage.getItem("admin_token");
    fetch(`/api/admin/judges/${judgeId}/qr`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const judge = judges.find((j) => j.id === judgeId);
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `qr_${(judge?.name || "judge").replace(/\s+/g, "_")}.png`;
        a.click();
      });
  }

  function downloadAllQR() {
    const token = localStorage.getItem("admin_token");
    fetch(`/api/admin/qr/zip?event_id=${eventId}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "judge_qr_codes.zip";
        a.click();
      });
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Judges ({judges.length})</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            className="text-sm text-gray-600 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Import CSV
          </button>
          <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCSVImport} />
          <button
            onClick={downloadAllQR}
            className="text-sm text-gray-600 px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            Download all QR codes (ZIP)
          </button>
          <button
            onClick={() => setAdding(true)}
            className="text-sm text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg font-medium"
          >
            + Add judge
          </button>
        </div>
      </div>

      {/* Add form */}
      {adding && (
        <form onSubmit={handleAdd} className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4">
          <div className="grid grid-cols-2 gap-3 mb-3">
            {[
              ["name", "Name *"],
              ["email", "Email"],
              ["expertise", "Expertise"],
              ["pin", "PIN (leave blank to auto-generate)"],
            ].map(([k, label]) => (
              <div key={k}>
                <label className="block text-xs text-gray-600 mb-0.5">{label}</label>
                <input
                  type="text"
                  value={newForm[k]}
                  onChange={(e) => setNewForm((p) => ({ ...p, [k]: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  required={k === "name"}
                />
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <button type="submit" className="px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Add</button>
            <button type="button" onClick={() => setAdding(false)} className="px-4 py-1.5 text-sm rounded-lg border border-gray-200 hover:bg-gray-50">Cancel</button>
          </div>
        </form>
      )}

      {/* CSV format hint */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-2 mb-4 text-xs text-gray-500">
        CSV format: <code className="font-mono bg-gray-100 px-1 rounded">name, email, expertise, pin</code>
      </div>

      {/* Judge table */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Name", "Expertise", "PIN", "QR Card", "Status", "Actions"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left font-medium text-gray-600">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {judges.map((j) => (
                <tr key={j.id} className="hover:bg-gray-50 group">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{j.name}</div>
                    {j.email && <div className="text-xs text-gray-400">{j.email}</div>}
                  </td>
                  <td className="px-4 py-3 text-gray-600">{j.expertise || "—"}</td>
                  <td className="px-4 py-3 font-mono font-bold text-gray-800 tracking-widest">{j.pin}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => downloadQR(j.id)}
                      className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      PNG
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${
                      j.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}>
                      {j.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleRegenQR(j.id)}
                      className="text-xs text-gray-400 hover:text-blue-600 mr-3 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      Regen QR
                    </button>
                    <button
                      onClick={() => handleDelete(j.id)}
                      className="text-xs text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {judges.length === 0 && (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-gray-400">
                    No judges yet. Add individually or import a CSV.
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
