import React, { useState, useEffect } from "react";
import TopBar from "../layout/TopBar.jsx";
import LeftPanel from "./LeftPanel.jsx";
import ScoringArea from "./ScoringArea.jsx";
import { onSyncStatusChange, startSyncPoller, flushQueue } from "../lib/sync.js";
import { scoreKey, saveProjects, saveScore, loadScores } from "../lib/db.js";
import { fetchJudgeProjects, fetchJudgeScores } from "../lib/api.js";

export default function Dashboard({ judge, event, projects: initialProjects, scores: initialScores }) {
  const [projects, setProjects] = useState(initialProjects || []);
  const [scores, setScores] = useState(initialScores || {});
  const [syncStatus, setSyncStatus] = useState("synced");
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Pick first unscored project as default active
  const firstUnscored = projects.find((p) => !scores[scoreKey(judge?.id, p.id)]);
  const [activeProjectId, setActiveProjectId] = useState(
    firstUnscored?.id ?? projects[0]?.id ?? null
  );

  useEffect(() => {
    startSyncPoller();
    const unsub = onSyncStatusChange(setSyncStatus);

    // Background: flush any queued offline scores, then pull fresh server state
    flushQueue().then(() => refreshFromServer());

    return unsub;
  }, []);

  async function refreshFromServer() {
    try {
      const [projRes, scoresRes] = await Promise.all([
        fetchJudgeProjects(),
        fetchJudgeScores(),
      ]);

      if (projRes?.projects?.length) {
        const sorted = projRes.projects.sort(
          (a, b) => (parseInt(a.table_number) || 0) - (parseInt(b.table_number) || 0)
        );
        await saveProjects(sorted);
        setProjects(sorted);
      }

      if (scoresRes?.scores?.length) {
        for (const s of scoresRes.scores) {
          await saveScore(s.judge_id, s.project_id, { ...s, syncStatus: "synced" });
        }
        const fresh = await loadScores();
        setScores(fresh);
      }
    } catch {
      // Offline or server error — local state is the source of truth
    }
  }

  function handleScoreSaved(judgeId, projectId, data) {
    const k = scoreKey(judgeId, projectId);
    setScores((prev) => ({ ...prev, [k]: { ...data, key: k } }));
  }

  function handleSelectProject(id) {
    setActiveProjectId(id);
    setDrawerOpen(false); // close mobile drawer when project selected
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <TopBar
        event={event}
        syncStatus={syncStatus}
        onMenuClick={() => setDrawerOpen(true)}
      />

      {/* Two-column layout: tablet fixed, mobile drawer */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left panel — fixed 280px on md+, hidden on mobile */}
        <aside className="hidden md:flex flex-col w-72 border-r border-gray-200 bg-white overflow-y-auto shrink-0">
          <LeftPanel
            judge={judge}
            event={event}
            projects={projects}
            scores={scores}
            activeProjectId={activeProjectId}
            onSelectProject={handleSelectProject}
          />
        </aside>

        {/* Right panel — scoring */}
        <main className="flex-1 overflow-hidden flex flex-col">
          <ScoringArea
            projects={projects}
            scores={scores}
            judgeId={judge?.id}
            activeProjectId={activeProjectId}
            onSetActive={setActiveProjectId}
            onScoreSaved={handleScoreSaved}
          />
        </main>
      </div>

      {/* Mobile bottom drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40"
            onClick={() => setDrawerOpen(false)}
          />
          {/* Drawer */}
          <div className="absolute bottom-0 left-0 right-0 bg-white rounded-t-2xl shadow-2xl max-h-[80vh] flex flex-col">
            {/* Handle */}
            <div className="flex justify-center pt-3 pb-1">
              <div className="w-10 h-1 bg-gray-300 rounded-full" />
            </div>
            <div className="overflow-y-auto flex-1">
              <LeftPanel
                judge={judge}
                event={event}
                projects={projects}
                scores={scores}
                activeProjectId={activeProjectId}
                onSelectProject={handleSelectProject}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
