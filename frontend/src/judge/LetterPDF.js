import { jsPDF } from "jspdf";

export function generateLetterPDF(judge, event, scoredProjects) {
  const doc = new jsPDF({ unit: "pt", format: "letter" });
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const margin = 54;
  const contentW = pageW - margin * 2;

  // Page border
  doc.setDrawColor(80, 80, 80);
  doc.setLineWidth(1);
  doc.rect(18, 18, pageW - 36, pageH - 36);

  // Watermark
  doc.setFont("helvetica", "normal");
  doc.setTextColor(200, 200, 200);
  doc.setFontSize(60);
  doc.text(event?.name || "HACKATHON", pageW / 2, pageH / 2, {
    align: "center",
    angle: 45,
  });
  doc.setTextColor(0, 0, 0);

  // Header — letterhead
  doc.setFontSize(11);
  doc.setFont("helvetica", "bold");
  doc.text(event?.org_name || "Organization", pageW - margin, 60, { align: "right" });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.text(event?.org_address || "", pageW - margin, 74, { align: "right" });
  doc.text(event?.org_website || "", pageW - margin, 86, { align: "right" });

  // Double rule
  doc.setLineWidth(2);
  doc.line(margin, 105, pageW - margin, 105);
  doc.setLineWidth(0.5);
  doc.line(margin, 109, pageW - margin, 109);

  // Title
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("OFFICIAL JUDGE ACKNOWLEDGMENT", pageW / 2, 132, { align: "center" });

  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  let y = 160;

  const body = [
    `Dear ${judge?.name || "Judge"},`,
    "",
    `On behalf of ${event?.org_name || "the organizing team"}, we are honored to confirm your participation as an official judge at ${event?.name || "this event"}, held on ${event?.date || ""} at ${event?.venue || ""}, ${event?.city || ""}.`,
    "",
    `${judge?.name || "You"} bring${judge?.name ? "s" : ""} expertise in ${judge?.expertise || "technology"} to our panel. Over the course of this event, you evaluated ${scoredProjects.length} project${scoredProjects.length !== 1 ? "s" : ""}, contributing approximately ${event?.hours_expected || 4} hours of expert technical review.`,
    "",
    "Your assessments directly determine which teams receive awards and recognition. This letter serves as formal documentation suitable for professional portfolios, visa applications (O-1, EB-1), and LinkedIn credentials.",
    "",
    "Projects evaluated:",
  ];

  for (const line of body) {
    if (y > pageH - 200) {
      doc.addPage();
      y = margin;
    }
    if (line === "") {
      y += 8;
      continue;
    }
    const wrapped = doc.splitTextToSize(line, contentW);
    doc.setFont("helvetica", line.startsWith("Dear") || line.startsWith("Projects") ? "normal" : "normal");
    doc.setFontSize(11);
    doc.text(wrapped, margin, y);
    y += wrapped.length * 18;
  }

  // Project list
  for (const p of scoredProjects) {
    if (y > pageH - 120) {
      doc.addPage();
      y = margin;
    }
    doc.text(`• ${p.title} — ${p.team_name || ""}`, margin + 10, y);
    y += 18;
  }

  y += 24;

  const issuedBy = `Issued by: ${event?.organizer_name || ""}, ${event?.organizer_title || ""}`;
  const footer = `${event?.org_name || ""} · ${event?.name || ""} · ${event?.date || ""}`;
  doc.text(issuedBy, margin, y);
  y += 18;
  doc.text(footer, margin, y);
  y += 40;

  doc.line(margin, y, margin + 200, y);
  y += 14;
  doc.setFont("helvetica", "bold");
  doc.text(event?.organizer_name || "", margin, y);
  y += 14;
  doc.setFont("helvetica", "normal");
  doc.text(event?.organizer_title || "", margin, y);
  y += 14;
  doc.text(event?.org_name || "", margin, y);

  const eventSlug = (event?.name || "event").replace(/\s+/g, "_");
  const judgeSlug = (judge?.name || "judge").replace(/\s+/g, "_");
  const dateSlug = new Date().toISOString().slice(0, 10);
  doc.save(`judge_acknowledgment_${judgeSlug}_${eventSlug}_${dateSlug}.pdf`);
}
