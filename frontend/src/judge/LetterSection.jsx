import React from "react";
import { generateLetterPDF } from "./LetterPDF.js";

export default function LetterSection({ judge, event, scoredProjects }) {
  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-gray-800 text-sm uppercase tracking-wide">My Letter</h2>
        <button
          onClick={() => generateLetterPDF(judge, event, scoredProjects)}
          className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-full transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download PDF
        </button>
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-xs text-gray-700 leading-relaxed space-y-2">
        <div className="text-right text-gray-500">
          <div className="font-semibold">{event?.org_name}</div>
          <div>{event?.org_address}</div>
          <div>{event?.org_website}</div>
        </div>
        <hr className="border-gray-300" />
        <p className="font-bold text-center text-gray-800 text-xs">OFFICIAL JUDGE ACKNOWLEDGMENT</p>
        <p>Dear <strong>{judge?.name}</strong>,</p>
        <p>
          On behalf of <strong>{event?.org_name}</strong>, we are honored to confirm your participation as an official judge at <strong>{event?.name}</strong>, held on {event?.date} at {event?.venue}, {event?.city}.
        </p>
        <p>
          {judge?.name} brings expertise in <strong>{judge?.expertise}</strong> to our panel. Over the course of this event, you evaluated <strong>{scoredProjects.length}</strong> projects, contributing approximately <strong>{event?.hours_expected || 4}</strong> hours of expert technical review.
        </p>
        <p>
          Your assessments directly determine which teams receive awards and recognition.
        </p>
        {scoredProjects.length > 0 && (
          <div>
            <p className="font-medium">Projects evaluated:</p>
            <ul className="mt-1 space-y-0.5">
              {scoredProjects.map((p) => (
                <li key={p.id} className="text-gray-600">
                  • {p.title} — {p.team_name}
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="pt-2 border-t border-gray-200">
          <p className="text-gray-500">Issued by: {event?.organizer_name}, {event?.organizer_title}</p>
          <p className="text-gray-500">{event?.org_name} · {event?.name} · {event?.date}</p>
        </div>
      </div>
    </div>
  );
}
