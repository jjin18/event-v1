import React from "react";
import LetterSection from "./LetterSection.jsx";
import RubricSection from "./RubricSection.jsx";
import ProgressSection from "./ProgressSection.jsx";

export default function LeftPanel({ judge, event, projects, scores, activeProjectId, onSelectProject }) {
  const scoredProjects = projects.filter(
    (p) => scores[`judge_${judge?.id}_project_${p.id}`]
  );
  // Inject judgeId for progress section
  const scoresWithId = { ...scores, _judgeId: judge?.id };

  return (
    <div className="h-full overflow-y-auto bg-white">
      <LetterSection judge={judge} event={event} scoredProjects={scoredProjects} />
      <RubricSection />
      <ProgressSection
        projects={projects}
        scores={scoresWithId}
        activeProjectId={activeProjectId}
        onSelectProject={onSelectProject}
      />
    </div>
  );
}
