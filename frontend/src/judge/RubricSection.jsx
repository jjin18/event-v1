import React, { useState } from "react";

const CRITERIA = [
  {
    name: "Innovation & Originality",
    weight: "25%",
    description: "How novel and creative is the idea? Does it solve a problem in a new way?",
    low: "Obvious idea, similar products exist, no new angle",
    mid: "Some novelty, builds on existing ideas with a twist",
    high: "Breakthrough concept, genuinely new approach to a real problem",
  },
  {
    name: "Technical Complexity",
    weight: "25%",
    description: "How technically sophisticated is the implementation?",
    low: "Simple CRUD app, no technical depth",
    mid: "Moderate complexity, solid integration of APIs/services",
    high: "Deep technical work: custom ML, novel architecture, impressive scale",
  },
  {
    name: "Real-world Impact",
    weight: "25%",
    description: "Does this solve a real problem? How many people does it affect?",
    low: "Niche problem, unclear market",
    mid: "Clear problem, reasonable target audience",
    high: "Mass-market problem, immediate real-world applicability",
  },
  {
    name: "Presentation & Demo",
    weight: "25%",
    description: "How well did they communicate and demonstrate their project?",
    low: "Confusing explanation, demo broken or not shown",
    mid: "Clear explanation, demo mostly works",
    high: "Compelling pitch, flawless demo, handles questions confidently",
  },
];

export default function RubricSection() {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-t border-gray-100">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="font-semibold text-gray-800 text-sm uppercase tracking-wide">Rubric Reference</span>
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
            <p className="font-semibold mb-1">Conflict of Interest Policy</p>
            <p>If you know team members personally, have financial interest, or worked with them, recuse yourself. Tell the organizer immediately.</p>
          </div>

          {CRITERIA.map((c) => (
            <div key={c.name} className="border border-gray-200 rounded-lg p-3">
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-gray-800 text-xs">{c.name}</span>
                <span className="text-blue-600 text-xs font-medium">{c.weight}</span>
              </div>
              <p className="text-gray-600 text-xs mb-2">{c.description}</p>
              <div className="grid grid-cols-3 gap-1 text-xs">
                <div className="bg-red-50 p-1.5 rounded text-red-700">
                  <div className="font-medium">Score 1–3</div>
                  <div className="text-red-600">{c.low}</div>
                </div>
                <div className="bg-yellow-50 p-1.5 rounded text-yellow-700">
                  <div className="font-medium">Score 4–7</div>
                  <div className="text-yellow-600">{c.mid}</div>
                </div>
                <div className="bg-green-50 p-1.5 rounded text-green-700">
                  <div className="font-medium">Score 8–10</div>
                  <div className="text-green-600">{c.high}</div>
                </div>
              </div>
            </div>
          ))}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-xs text-blue-800">
            <p className="font-semibold mb-1">Tips</p>
            <ul className="space-y-1 list-disc list-inside">
              <li>Score independently before discussing with other judges</li>
              <li>Use the full range — don't cluster around 5-7</li>
              <li>A working demo is worth significant points</li>
              <li>Note your reasoning for edge scores in the notes field</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
