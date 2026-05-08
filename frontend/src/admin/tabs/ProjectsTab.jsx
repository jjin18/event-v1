import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  createProject,
  deleteProject,
  fetchProjects,
  updateProject,
} from "../../lib/api.js";

export default function ProjectsTab({ eventId }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importMode, setImportMode] = useState("csv"); // "csv" | "scrape"
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [scrapeLog, setScrapeLog] = useState([]);
  const [scraping, setScraping] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [sortCol, setSortCol] = useState("table_number");
  const [selected, setSelected] = useState(new Set());
  const [adding, setAdding] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", team_name: "", table_number: "", track: "", description: "", devpost_url: "" });
  const fileRef = useRef();

  useEffect(() => { load(); }, [eventId]);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchProjects(eventId);
      setProjects(data.projects || []);
    } finally {
      setLoading(false);
    }
  }

  const sorted = [...projects].sort((a, b) => {
    if (sortCol === "table_number") return (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0);
    return (a[sortCol] || "").localeCompare(b[sortCol] || "");
  });

  async function handleCSVUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    const token = localStorage.getItem("admin_token");
    const res = await fetch(`/api/admin/projects/import?event_id=${eventId}`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
    if (res.ok) {
      const d = await res.json();
      alert(`Imported ${d.inserted} projects`);
      load();
    }
  }

  async function handleScrape(e) {
    e.preventDefault();
    if (!scrapeUrl) return;
    setScraping(true);
    setScrapeLog([]);
    const token = localStorage.getItem("admin_token");
    const res = await fetch("/api/admin/projects/scrape", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ url: scrapeUrl, event_id: eventId }),
    });
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            const d = JSON.parse(line.slice(6));
            if (d.status) setScrapeLog((prev) => [...prev, d.status]);
            if (d.status === "done") load();
            if (d.error) setScrapeLog((prev) => [...prev, `Error: ${d.error}`]);
          } catch { }
        }
      }
    }
    setScraping(false);
  }

  function startEdit(p) {
    setEditingId(p.id);
    setEditForm({ ...p });
  }

  async function saveEdit(id) {
    try {
      const updated = await updateProject(id, { ...editForm, event_id: eventId });
      setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)));
      setEditingId(null);
    } catch { alert("Save failed"); }
  }

  async function handleDelete(id) {
    if (!confirm("Delete this project and all its scores?")) return;
    await deleteProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleBulkDelete() {
    if (!confirm(`Delete ${selected.size} projects?`)) return;
    for (const id of selected) await deleteProject(id);
    setProjects((prev) => prev.filter((p) => !selected.has(p.id)));
    setSelected(new Set());
  }

  async function handleAdd(e) {
    e.preventDefault();
    try {
      const p = await createProject({ ...newForm, event_id: eventId });
      setProjects((prev) => [...prev, p]);
      setNewForm({ title: "", team_name: "", table_number: "", track: "", description: "", devpost_url: "" });
      setAdding(false);
    } catch { alert("Failed to add project"); }
  }

  function exportCSV() {
    const header = "table_number,title,team_name,track,devpost_url";
    const rows = projects.map((p) =>
      [p.table_number, p.title, p.team_name, p.track, p.devpost_url]
        .map((v) => `"${(v || "").replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `projects_event_${eventId}.csv`;
    a.click();
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Projects ({projects.length})</h2>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button onClick={handleBulkDelete} className="text-sm text-red-600 hover:text-red-800 font-medium px-3 py-1.5 border border-red-200 rounded-lg">
              Delete {selected.size}
            </button>
          )}
          <button onClick={exportCSV} className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 border border-gray-200 rounded-lg">
            Export CSV
          </button>
          <button onClick={() => setAdding(true)} className="text-sm text-white bg-blue-600 hover:bg-blue-700 px-3 py-1.5 rounded-lg font-medium">
            + Add project
          </button>
        </div>
      </div>

      {/* Import controls */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4">
        <div className="flex gap-2 mb-3">
          <button
            onClick={() => setImportMode("csv")}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${importMode === "csv" ? "bg-blue-100 text-blue-700" : "text-gray-500 hover:bg-gray-100"}`}
          >
            CSV Upload
          </button>
          <button
            onClick={() => setImportMode("scrape")}
            className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-colors ${importMode === "scrape" ? "bg-blue-100 text-blue-700" : "text-gray-500 hover:bg-gray-100"}`}
          >
            Scrape Devpost
          </button>
        </div>

        {importMode === "csv" ? (
          <div
            className="border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 transition-colors"
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              const file = e.dataTransfer.files[0];
              if (file) handleCSVUpload({ target: { files: [file] } });
            }}
          >
            <svg className="w-8 h-8 text-gray-400 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <p className="text-sm text-gray-600">Drop Devpost CSV here, or <span className="text-blue-600 font-medium">browse</span></p>
            <p className="text-xs text-gray-400 mt-1">Columns: title, team_name, table_number, track, description, devpost_url</p>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={handleCSVUpload} />
          </div>
        ) : (
          <form onSubmit={handleScrape} className="flex gap-2">
            <input
              type="url"
              value={scrapeUrl}
              onChange={(e) => setScrapeUrl(e.target.value)}
              placeholder="https://your-hackathon.devpost.com"
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              required
            />
            <button
              type="submit"
              disabled={scraping}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-60"
            >
              {scraping ? "Fetching..." : "Fetch projects"}
            </button>
          </form>
        )}

        {scrapeLog.length > 0 && (
          <div className="mt-3 bg-gray-50 rounded-lg p-3 text-xs font-mono text-gray-600 max-h-32 overflow-y-auto">
            {scrapeLog.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        )}
      </div>

      {/* Add project form */}
      {adding && (
        <form onSubmit={handleAdd} className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4">
          <div className="grid grid-cols-2 gap-3 mb-3">
            {[
              ["title", "Project title *"],
              ["team_name", "Team name"],
              ["table_number", "Table #"],
              ["track", "Track"],
              ["devpost_url", "Devpost URL"],
              ["description", "Description"],
            ].map(([k, label]) => (
              <div key={k} className={k === "description" ? "col-span-2" : ""}>
                <label className="block text-xs text-gray-600 mb-0.5">{label}</label>
                <input
                  type="text"
                  value={newForm[k]}
                  onChange={(e) => setNewForm((p) => ({ ...p, [k]: e.target.value }))}
                  className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                  required={k === "title"}
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

      {/* Project table */}
      {loading ? (
        <div className="text-center py-8 text-gray-400">Loading...</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-3 py-3 text-left w-8">
                  <input
                    type="checkbox"
                    onChange={(e) => setSelected(e.target.checked ? new Set(projects.map((p) => p.id)) : new Set())}
                    checked={selected.size === projects.length && projects.length > 0}
                  />
                </th>
                {[["#", "id"], ["Table", "table_number"], ["Project", "title"], ["Team", "team_name"], ["Track", "track"]].map(([label, col]) => (
                  <th
                    key={col}
                    onClick={() => setSortCol(col)}
                    className="px-3 py-3 text-left font-medium text-gray-600 cursor-pointer hover:text-gray-900 select-none"
                  >
                    {label} {sortCol === col ? "↑" : ""}
                  </th>
                ))}
                <th className="px-3 py-3 text-right font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.map((p, i) => (
                <tr key={p.id} className="hover:bg-gray-50 group">
                  <td className="px-3 py-2.5">
                    <input
                      type="checkbox"
                      checked={selected.has(p.id)}
                      onChange={(e) => {
                        const next = new Set(selected);
                        e.target.checked ? next.add(p.id) : next.delete(p.id);
                        setSelected(next);
                      }}
                    />
                  </td>
                  <td className="px-3 py-2.5 text-gray-400 text-xs">{i + 1}</td>

                  {editingId === p.id ? (
                    <>
                      <td className="px-2 py-1.5">
                        <input value={editForm.table_number || ""} onChange={(e) => setEditForm((f) => ({ ...f, table_number: e.target.value }))}
                          className="w-16 border border-blue-300 rounded px-2 py-1 text-xs" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input value={editForm.title || ""} onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                          className="w-full border border-blue-300 rounded px-2 py-1 text-xs" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input value={editForm.team_name || ""} onChange={(e) => setEditForm((f) => ({ ...f, team_name: e.target.value }))}
                          className="w-full border border-blue-300 rounded px-2 py-1 text-xs" />
                      </td>
                      <td className="px-2 py-1.5">
                        <input value={editForm.track || ""} onChange={(e) => setEditForm((f) => ({ ...f, track: e.target.value }))}
                          className="w-full border border-blue-300 rounded px-2 py-1 text-xs" />
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button onClick={() => saveEdit(p.id)} className="text-xs text-blue-600 font-medium hover:underline mr-2">Save</button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-gray-400 hover:text-gray-600">Cancel</button>
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2.5 font-mono text-gray-700">{p.table_number || "—"}</td>
                      <td className="px-3 py-2.5 font-medium text-gray-900">
                        {p.title}
                        {p.devpost_url && (
                          <a href={p.devpost_url} target="_blank" rel="noreferrer"
                            className="ml-1 text-blue-400 hover:text-blue-600 text-xs opacity-0 group-hover:opacity-100 transition-opacity">↗</a>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-gray-600">{p.team_name || "—"}</td>
                      <td className="px-3 py-2.5">
                        {p.track && (
                          <span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full text-xs">{p.track}</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button onDoubleClick={() => startEdit(p)} onClick={() => startEdit(p)}
                          className="text-xs text-gray-400 hover:text-blue-600 mr-3 opacity-0 group-hover:opacity-100 transition-opacity">Edit</button>
                        <button onClick={() => handleDelete(p.id)}
                          className="text-xs text-gray-400 hover:text-red-600 opacity-0 group-hover:opacity-100 transition-opacity">Remove</button>
                      </td>
                    </>
                  )}
                </tr>
              ))}
              {sorted.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-gray-400">
                    No projects yet. Import a CSV or scrape Devpost above.
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
