import React, { useEffect, useState } from "react";
import { updateEvent } from "../../lib/api.js";

const FIELDS = [
  { key: "name", label: "Event name", type: "text" },
  { key: "date", label: "Date", type: "text", placeholder: "March 15-16, 2026" },
  { key: "venue", label: "Venue", type: "text" },
  { key: "city", label: "City", type: "text" },
  { key: "org_name", label: "Organization", type: "text" },
  { key: "org_address", label: "Address", type: "text" },
  { key: "org_website", label: "Website", type: "text" },
  { key: "organizer_name", label: "Organizer name", type: "text" },
  { key: "organizer_title", label: "Organizer title", type: "text" },
  { key: "hours_expected", label: "Expected hours", type: "number" },
];

export default function SetupTab({ event, onUpdated }) {
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setForm({ ...event });
    setSaved(false);
  }, [event.id]);

  function handleChange(key, val) {
    setForm((prev) => ({ ...prev, [key]: val }));
    setSaved(false);
  }

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    try {
      const updated = await updateEvent(event.id, form);
      onUpdated(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert("Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // Live letter preview
  const preview = {
    org: form.org_name || "[Organization]",
    address: form.org_address || "[Address]",
    website: form.org_website || "[Website]",
    name: form.name || "[Event Name]",
    date: form.date || "[Date]",
    venue: form.venue || "[Venue]",
    city: form.city || "[City]",
    organizer: form.organizer_name || "[Organizer Name]",
    title: form.organizer_title || "[Title]",
    hours: form.hours_expected || 4,
  };

  return (
    <div className="flex gap-6 max-w-6xl">
      {/* Form */}
      <form onSubmit={handleSave} className="flex-1 min-w-0">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Event Setup</h2>
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          {FIELDS.map(({ key, label, type, placeholder }) => (
            <div key={key} className="flex items-center gap-4">
              <label className="w-36 shrink-0 text-sm text-gray-600 text-right">{label}:</label>
              <input
                type={type}
                value={form[key] ?? ""}
                onChange={(e) => handleChange(key, type === "number" ? parseFloat(e.target.value) : e.target.value)}
                placeholder={placeholder || ""}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          ))}

          <div className="flex items-center gap-4">
            <label className="w-36 shrink-0 text-sm text-gray-600 text-right">Logo:</label>
            <input
              type="file"
              accept="image/*"
              className="flex-1 text-sm text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
              onChange={async (e) => {
                const f = e.target.files[0];
                if (!f) return;
                const fd = new FormData();
                fd.append("file", f);
                const token = localStorage.getItem("admin_token");
                const res = await fetch(`/api/admin/events/${event.id}/logo`, {
                  method: "POST",
                  headers: { Authorization: `Bearer ${token}` },
                  body: fd,
                });
                if (res.ok) {
                  const d = await res.json();
                  handleChange("logo_path", d.logo_path);
                }
              }}
            />
          </div>

          <div className="pt-2 flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
            >
              {saving ? "Saving..." : "Save changes"}
            </button>
            {saved && <span className="text-green-600 text-sm font-medium">✓ Saved</span>}
          </div>
        </div>
      </form>

      {/* Live letter preview */}
      <div className="w-80 shrink-0">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Letter Preview</h2>
        <div className="bg-white border border-gray-200 rounded-xl p-5 text-xs leading-relaxed space-y-2 shadow-sm sticky top-0">
          <div className="text-right text-gray-600">
            <div className="font-bold">{preview.org}</div>
            <div>{preview.address}</div>
            <div className="text-blue-600">{preview.website}</div>
          </div>
          <hr className="border-gray-300 my-2" />
          <p className="font-bold text-center text-gray-800">OFFICIAL JUDGE ACKNOWLEDGMENT</p>
          <p>Dear [Judge Name],</p>
          <p>
            On behalf of <strong>{preview.org}</strong>, we are honored to confirm your participation as an official judge at <strong>{preview.name}</strong>, held on {preview.date} at {preview.venue}, {preview.city}.
          </p>
          <p>
            [Judge Name] brings expertise in [Expertise] to our panel. Over the course of this event, you evaluated [N] projects, contributing approximately <strong>{preview.hours}</strong> hours of expert technical review.
          </p>
          <p className="text-gray-500 border-t border-gray-200 pt-2">
            Issued by: {preview.organizer}, {preview.title}<br />
            {preview.org} · {preview.name} · {preview.date}
          </p>
        </div>
      </div>
    </div>
  );
}
