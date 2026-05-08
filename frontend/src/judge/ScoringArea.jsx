import React, { useEffect, useRef, useState } from "react";
import { saveScore, scoreKey } from "../lib/db.js";
import { queueScore } from "../lib/sync.js";

const CRITERIA = [
  { key: "innovation", label: "Innovation & Originality", weight: 0.25 },
  { key: "technical", label: "Technical Complexity", weight: 0.25 },
  { key: "impact", label: "Real-world Impact", weight: 0.25 },
  { key: "presentation", label: "Presentation & Demo", weight: 0.25 },
];

function ScoreSlider({ label, value, onChange }) {
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState(String(value));

  useEffect(() => {
    if (!editing) setInputVal(String(value));
  }, [value, editing]);

  function commitInput() {
    const n = parseFloat(inputVal);
    if (!isNaN(n)) onChange(Math.min(10, Math.max(1, n)));
    setEditing(false);
  }

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {editing ? (
          <input
            type="number"
            min={1} max={10} step={0.5}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onBlur={commitInput}
            onKeyDown={(e) => e.key === "Enter" && commitInput()}
            className="w-16 text-center border border-blue-400 rounded-lg py-0.5 text-lg font-bold text-blue-700 outline-none"
            autoFocus
          />
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-lg font-bold text-blue-700 bg-blue-50 rounded-lg px-3 py-0.5 hover:bg-blue-100 transition-colors"
          >
            {value.toFixed(1)}
          </button>
        )}
      </div>

      <div className="relative">
        <input
          type="range"
          min={1} max={10} step={0.5}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-400 mt-0.5 px-1">
          <span>1 (weak)</span>
          <span>10 (breakthrough)</span>
        </div>
      </div>
    </div>
  );
}

export default function ScoringArea({ projects, scores, judgeId, activeProjectId, onSetActive, onScoreSaved }) {
  const idx = projects.findIndex((p) => p.id === activeProjectId);
  const project = projects[idx] ?? null;
  const [search, setSearch] = useState("");
  const [notes, setNotes] = useState("");
  const [vals, setVals] = useState({ innovation: 5, technical: 5, impact: 5, presentation: 5 });
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const key = project ? scoreKey(judgeId, project.id) : null;
  const existing = key ? scores[key] : null;

  useEffect(() => {
    if (existing) {
      setVals({
        innovation: existing.innovation ?? 5,
        technical: existing.technical ?? 5,
        impact: existing.impact ?? 5,
        presentation: existing.presentation ?? 5,
      });
      setNotes(existing.notes ?? "");
    } else {
      setVals({ innovation: 5, technical: 5, impact: 5, presentation: 5 });
      setNotes("");
    }
    setExpanded(false);
  }, [activeProjectId]);

  const totalRaw = Object.values(vals).reduce((a, b) => a + b, 0);
  const totalWeighted = totalRaw / 4;

  function handleSearch(e) {
    e.preventDefault();
    const q = search.toLowerCase().trim();
    const found = projects.find(
      (p) =>
        p.table_number === q ||
        p.title.toLowerCase().includes(q) ||
        `table ${p.table_number}` === q
    );
    if (found) {
      onSetActive(found.id);
      setSearch("");
    }
  }

  function navigate(dir) {
    if (!projects.length) return;
    const newIdx = Math.max(0, Math.min(projects.length - 1, idx + dir));
    onSetActive(projects[newIdx].id);
  }

  async function handleSaveNext() {
    if (!project) return;
    setSaving(true);

    const scoreData = {
      project_id: project.id,
      innovation: vals.innovation,
      technical: vals.technical,
      impact: vals.impact,
      presentation: vals.presentation,
      notes,
    };

    // Save to IndexedDB immediately
    await saveScore(judgeId, project.id, {
      ...scoreData,
      total_raw: totalRaw,
      total_weighted: totalWeighted,
      syncStatus: "pending",
    });

    // Queue server sync — never blocks
    queueScore(judgeId, scoreData).catch(() => {});

    onScoreSaved(judgeId, project.id, {
      ...scoreData,
      total_raw: totalRaw,
      total_weighted: totalWeighted,
      syncStatus: "pending",
    });

    setSaving(false);

    // Jump to next unscored project
    const nextIdx = projects.findIndex(
      (p, i) => i > idx && !scores[scoreKey(judgeId, p.id)]
    );
    if (nextIdx !== -1) {
      onSetActive(projects[nextIdx].id);
    } else {
      // Wrap around to first unscored
      const first = projects.find((p) => !scores[scoreKey(judgeId, p.id)]);
      if (first && first.id !== project.id) onSetActive(first.id);
    }
  }

  if (!project) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
        Select a project to start scoring
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sticky header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 z-10">
        <div className="flex items-center justify-between mb-2">
          <button
            onClick={() => navigate(-1)}
            disabled={idx === 0}
            className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            ◀ Prev
          </button>
          <div className="text-center">
            <div className="text-xs text-gray-500">{idx + 1} of {projects.length}</div>
            <div className="text-2xl font-black text-blue-700 leading-tight">
              TABLE {project.table_number || "??"}
            </div>
          </div>
          <button
            onClick={() => navigate(1)}
            disabled={idx === projects.length - 1}
            className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next ▶
          </button>
        </div>

        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search table # or name..."
            className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
          />
          <button type="submit" className="px-3 py-1.5 bg-gray-100 rounded-lg text-sm hover:bg-gray-200 transition-colors">🔍</button>
        </form>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Project card */}
        <div className="px-4 pt-4 pb-2">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            <div className="flex items-start justify-between mb-2">
              <div className="text-3xl font-black text-gray-900">TABLE {project.table_number || "??"}</div>
              {project.devpost_url && (
                <a
                  href={project.devpost_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                >
                  Devpost ↗
                </a>
              )}
            </div>
            <hr className="border-gray-200 mb-3" />
            <h2 className="text-xl font-bold text-gray-900 mb-1">{project.title}</h2>
            <div className="flex items-center gap-2 text-sm text-gray-600 mb-3 flex-wrap">
              <span>Team: <strong>{project.team_name || "—"}</strong></span>
              {project.track && (
                <>
                  <span className="text-gray-300">·</span>
                  <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full text-xs font-medium">
                    {project.track}
                  </span>
                </>
              )}
            </div>
            {project.description && (
              <div>
                <p className={`text-sm text-gray-600 leading-relaxed ${!expanded ? "line-clamp-3" : ""}`}>
                  {project.description}
                </p>
                {project.description.length > 150 && (
                  <button
                    onClick={() => setExpanded(!expanded)}
                    className="text-xs text-blue-600 mt-1 hover:underline"
                  >
                    {expanded ? "Show less" : "Show more"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Scoring rubric */}
        <div className="px-4 py-2">
          <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm">
            {CRITERIA.map(({ key, label }) => (
              <ScoreSlider
                key={key}
                label={label}
                value={vals[key]}
                onChange={(v) => setVals((prev) => ({ ...prev, [key]: v }))}
              />
            ))}

            <div className="mt-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add notes for this project..."
                rows={2}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>
        </div>

        {/* Spacer for sticky bar */}
        <div className="h-20" />
      </div>

      {/* Sticky bottom bar */}
      <div className="sticky bottom-0 bg-white border-t border-gray-200 px-4 py-3 shadow-lg">
        <div className="flex items-center justify-between mb-2 text-sm">
          <span className="text-gray-600">
            Raw: <strong className="text-gray-900">{totalRaw.toFixed(1)}/40</strong>
          </span>
          <span className="text-gray-600">
            Weighted: <strong className="text-blue-700">{totalWeighted.toFixed(2)}/10</strong>
          </span>
        </div>
        <button
          onClick={handleSaveNext}
          disabled={saving}
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-semibold text-base hover:bg-blue-700 active:scale-[0.98] transition-all disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save & Next"}
        </button>
      </div>
    </div>
  );
}
