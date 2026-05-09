# Product Requirements Document
## Hackathon Platform with Contingent Sponsor Measurement
### v1.0 — for Founders Inc / MakerMods Hackathon and subsequent deployments

---

## 1. Document context

**Author:** Jia Jin
**Status:** Draft for engineering kickoff
**Target ship date:** First deployable version 60 days from kickoff
**First customer:** Founders Inc / MakerMods hackathon (operating partner deal, $300 base + sponsor revenue)
**First sponsor:** AI Taco (contingent contract, terms TBD in section 9)
**Reviewers needed:** Engineering lead (TBD), Founders Inc operations contact, MakerMods operations contact

---

## 2. Why we're building this

Hackathon organizers have no infrastructure for running events that produce measurable outcomes for their stakeholders. Founders Inc runs hackathons to demonstrate accelerator credibility to LPs and applicants. MakerMods runs them to grow their community. Sponsors at these events pay $5,000–$50,000 per slot and have no way to verify ROI before, during, or after the event. Attendees show up without information about who else will be in the room. Outcomes evaporate when the event ends.

The product is the operational and measurement layer underneath events. We sell to organizers (who pay for the operational capability) and to sponsors (who pay for the measurement and contingent pricing). We capture verified attendee data and outcome data as a byproduct, which compounds into a defensible substrate over time.

This v1 is the version we ship for the Founders Inc / MakerMods hackathon plus the next 4–6 events that follow it on the same template. The product must work end-to-end for one event, then be repeatable across events with minimal customization.

---

## 3. What's in scope and what's not

### In scope for v1
- Attendee registration with multi-source identity verification
- Pre-event composition reveal to confirmed attendees
- Sponsor contingent contract structure and execution
- Booth scanner and interaction logging at the event
- Real-time match verification for sponsors during the event
- Post-event packet for sponsors within 48 hours
- 30/60/90-day outcome tracking loop
- Organizer dashboard showing event-level metrics
- Manual fallback flows for every automated piece (the event happens regardless of system performance)

### Explicitly out of scope for v1
- Recruiting product (queryable graph for hiring)
- ROI calculator for prospective sponsors deciding whether to sponsor
- Cross-event attribution (will be Tier 2 data accumulating over time, not a v1 feature)
- Threshold-RSVP composition mechanics (deferred to v2 — too much UX risk for first event)
- Voucher/reputation-staked invitations (deferred — requires graph density)
- Native mobile app (mobile web only)
- Integrations with ATS or CRM systems (manual outcome capture only)
- Self-serve sponsor onboarding (every v1 sponsor contract is hand-priced)
- Self-serve organizer onboarding (every v1 organizer is hand-onboarded)
- AI-driven matching of attendees to sponsors during the event (rule-based ICP matching only)

### Explicitly deferred but planned for v2
- Threshold-RSVP composition reveal
- Voucher mechanism for invitations
- Cross-event behavioral signals
- Conversational graph search

---

## 4. Users and their goals

### 4.1 Organizer (Founders Inc / MakerMods staff)
**Who they are:** Operations leads at accelerators or community brands that run hackathons as part of their broader strategy.
**What they want:** A hackathon that runs smoothly, makes their brand look credible to attendees and sponsors, and produces post-event evidence of impact they can share with their stakeholders (LPs, board, community).
**What they don't want:** Operational fires, sponsor complaints, attendee confusion, or anything that reflects badly on their brand.
**How they measure success:** Sponsor renewal for next event, attendee satisfaction, post-event report quality.
**What they pay:** $300–$3,000 per event for v1, scaling up over time as the platform proves value.

### 4.2 Sponsor (AI Taco and similar)
**Who they are:** DevRel leads, recruiting leads, or growth marketers at tech companies (Series A through public) sponsoring hackathons to recruit engineering talent.
**What they want:** Verifiable contact with their ICP at the event, a defensible report afterward they can show their CFO, and outcomes that justify renewal.
**What they don't want:** To pay flat fees and hope. To collect 200 random business cards and waste their team's time chasing them.
**How they measure success:** Hires made, pipeline created, cost per qualified candidate.
**What they pay:** $5,000–$25,000 per event in v1, structured as base + per-verified-ICP-match capped at a maximum.

### 4.3 Attendee (hackathon participant)
**Who they are:** Students, early-career engineers, junior researchers, occasional founders. Mostly age 18–28. Technically capable, time-constrained, network-hungry.
**What they want:** A good hackathon experience, exposure to companies they might want to work at, intros to people more senior than them, a meaningful project on their resume.
**What they don't want:** Spam from sponsors after the event, their data sold without consent, applications that take 30 minutes, events that turn out to be career fairs in disguise.
**How they measure success:** Connections made, opportunities surfaced, fun had.
**What they pay:** Nothing in v1.

### 4.4 Sponsor booth staff
**Who they are:** Engineers, recruiters, or DevRel folks at the sponsor company who actually staff the booth at the event. Often different people from the buyer.
**What they want:** A simple way to record who they met, verify the conversation matters, and follow up afterward without losing context.
**What they don't want:** A tool that takes more than 10 seconds per scan. A tool that requires logging in repeatedly. A tool that fails when wifi is bad.
**How they measure success:** Quality of follow-up conversations, perceived productivity at the booth.

### 4.5 Internal: our team running the platform
**Who we are:** A small team (2–4 people in v1) operating the platform alongside the organizer. We must be able to monitor every event in real time, intervene when verification breaks, resolve disputes, and produce reports.
**What we need:** Visibility into every flow, alerts when things break, manual override capability for every automated step.

---

## 5. End-to-end user flows

### 5.1 Organizer onboarding (manual, hand-held)

**Pre-deal phase (handled by founder/sales, not in product):**
- Conversation with organizer establishing event details, expected attendance, sponsor list, dates, location, ICP definitions for the room
- Contract signed defining: operating fee, data rights (we retain attendee data and behavioral signals; organizer retains brand and event content), revenue share on sponsor contracts (we keep 20–30%, organizer gets 70–80%)

**In-product phase:**
1. Internal team creates event record in the platform admin: name, date, expected attendance, organizer brand assets, RSVP cap, location, schedule
2. Organizer gets login credentials and access to organizer dashboard
3. Organizer configures event-specific details: tracks, judging criteria, schedule, session list, sponsor list with assigned booth slots
4. Organizer reviews and approves the public RSVP page before it goes live

### 5.2 Sponsor contract creation (manual, hand-held)

**Pre-deal phase:**
- Conversation with sponsor establishing: their ICP, their goal (hires, pipeline, brand, mix), their budget
- Internal team prices the contingent contract: base fee, per-match fee, cap, ICP definition, verification criteria
- Contract signed (DocuSign or equivalent) with terms

**In-product phase:**
1. Internal team creates sponsor record in admin: company, contract terms, ICP definition (structured), payment method
2. Sponsor gets login credentials and access to sponsor dashboard
3. Sponsor reviews the ICP definition (which the platform will use to verify matches) and confirms or revises
4. Sponsor designates booth staff who will use the scanner at the event
5. Base fee charged immediately; per-match fees accrue at the event

### 5.3 Attendee registration

**Public RSVP page:**
1. Attendee lands on RSVP page (white-labeled with organizer brand: Founders Inc, MakerMods)
2. Page shows: event name, date, location, organizer description, anonymized current composition stats ("currently confirmed: 23 CS students, 8 ML researchers, 3 founders")
3. Single CTA: "Apply to attend"

**Application flow:**
1. Attendee clicks apply, prompted to authenticate via LinkedIn OAuth (preferred), GitHub OAuth (alternative for engineers), or manual entry (fallback)
2. After OAuth, system pulls profile data: name, headline, education, work history, public projects, contributions
3. System computes confidence score based on data richness and consistency across sources
4. Attendee sees: "Here's what we found about you. Confirm or correct." with prefilled fields they can edit
5. Attendee adds 2–3 fields not in OAuth: current focus, what they're hoping to get from the event (free text), optional resume upload
6. System runs ICP matching against the event's expected sponsors and computes preliminary match scores
7. Attendee sees: "Submit application. You'll hear back within 48 hours."

**Application review:**
1. Internal team and organizer see new applications in admin dashboard with: confidence score, sponsor ICP-match potential, any red flags (low confidence, conflicting data)
2. Default decision: accept if confidence > threshold and no red flags. Manual review if borderline.
3. Accepted attendees get email: "You're in. Here's what to expect." with details and a unique check-in code (QR).
4. Rejected attendees get email: "Thanks for applying. We weren't able to fit you this time." (No detailed reasons given by default — this is intentional to prevent gaming.)

### 5.4 Pre-event composition reveal

Three days before the event, all confirmed attendees receive an email:
"Here's who else is coming. Anonymized but specific."

The email and corresponding web page show:
- Aggregated composition by role and seniority (e.g., "47 CS undergrads from top-30 schools, 12 ML researchers, 8 startup engineers, 3 founders")
- Notable affiliations represented (e.g., "Anthropic, Stripe, Founders Inc batch '25")
- Sponsor list with their stated ICPs (e.g., "AI Taco is hiring ML engineers, expressed interest in CS juniors and seniors")

Purpose: gives attendees signal about whether the room is worth their time. Lets sponsors gauge expected ICP density. Builds anticipation.

This is a v1 feature even though threshold-RSVP is not — composition reveal as information is doable; threshold-RSVP as commitment mechanism is too much UX risk for first deployment.

### 5.5 At the event: attendee check-in

1. Attendee arrives at venue, presents QR code from acceptance email at registration desk
2. Staff scans QR via mobile web tool, system marks attendee as checked in, prints badge with name and verification icon
3. Badges visually distinguish "verified" attendees (those who completed OAuth) from manually-added walk-ins (rare, lower-trust)
4. System updates real-time dashboard with check-in counts

### 5.6 At the event: sponsor booth interactions

**Setup before doors open:**
1. Sponsor booth staff log into the booth scanner mobile web tool with credentials provided in advance
2. Each booth staff member sees: event name, sponsor company, real-time match counter, list of attendees they've already scanned
3. Tutorial flow walks them through their first scan (60 seconds)

**During the event:**
1. Attendee approaches booth, conversation happens
2. Booth staff opens scanner, scans attendee's badge QR code
3. Within 2 seconds, booth staff sees:
    - Attendee name, school/company, role
    - Match status: "ICP match" / "Partial match" / "Not a match" / "Needs review"
    - One-tap rating: "Strong fit, follow up" / "Some interest" / "Not a match"
    - Optional: 30-second voice memo capture (transcribed in background) or 60-character text note
4. Booth staff taps a rating, optional memo, returns to conversation
5. Match count updates on sponsor dashboard in real time

**Edge case handling:**
- Wifi out: scanner queues scans locally, syncs when connection returns
- Attendee not in system (walked in without registering): manual entry flow with elevated review requirement
- Disagreement on ICP match: scanner shows "needs review" — flagged for end-of-event manual review by sponsor lead

### 5.7 At the event: real-time dashboards

**Sponsor dashboard (live):**
- Total scans today, total verified ICP-matches, total accrued contract value
- Match counter with visual bar showing distance to cap
- List of recent scans with attendee details
- Booth staff leaderboard (anonymized) showing who's logging the most
- Alert if no scans in last 30 minutes ("Booth quiet — anything we can help with?")

**Organizer dashboard (live):**
- Total check-ins, expected vs. actual attendance
- Sponsor activity heat map (which booths are busy)
- Any flagged issues or disputes
- Attendee feedback if any has come in

**Internal dashboard (live):**
- All events running today
- System health indicators (scanner success rate, OAuth success rate, etc.)
- Alerts for any sponsor or organizer issues
- Manual override panel

### 5.8 Post-event: contract execution

**Within 24 hours of event close:**
1. System closes match counts, allowing 24-hour window for sponsor to flag disputed scans
2. Manual review of any "needs review" scans by internal team + sponsor lead
3. Final verified match count locked
4. Invoice generated: base fee already paid + (verified matches × per-match fee), capped at agreed cap
5. Sponsor's saved payment method auto-charged
6. Organizer revenue share calculated and queued for payout

**Within 48 hours of event close:**
1. Post-event packet generated for sponsor: PDF + interactive web view
2. Packet contains: every verified ICP match with full profile, interaction notes, voice memo transcripts, suggested follow-up tier, suggested follow-up template
3. Sponsor receives email with packet, prompt to log outcomes at +30/+60/+90 days
4. Organizer receives separate report: event metrics, sponsor satisfaction, attendee feedback, suggested improvements

### 5.9 Post-event: outcome tracking loop

**At event-date + 14 days:**
- Email to sponsor: "Quick check-in: have you started following up with the matches from [event]?"
- One-click access to outcome tracker showing all matches with status field

**At event-date + 30 days:**
- Email to sponsor: "How's the pipeline from [event]?"
- Outcome tracker prompts: contacted? interviewing? next step?

**At event-date + 60 days:**
- Email to sponsor: "Any offers or hires from [event]?"
- Tracker prompts: offered? declined? hired?

**At event-date + 90 days:**
- Email to sponsor: "Final outcomes from [event]"
- Tracker prompts for confirmed hires, with optional details: role, salary range
- Triggers internal report: predicted vs actual outcomes, sponsor satisfaction, renewal likelihood

**Throughout the loop:**
- Attendee side gets parallel prompts: "Have you been contacted by sponsors from [event]?" — used for triangulation
- Discrepancies between sponsor-reported outcomes and attendee-reported contacts surface as questions for internal review

---

## 6. Functional requirements (detailed)

### 6.1 Attendee identity verification

**Required:**
- Support LinkedIn OAuth and GitHub OAuth as primary verification sources
- Support email-domain verification (.edu emails for students, company-domain emails for working professionals)
- Compute a confidence score 0–1 based on:
    - Number of OAuth sources connected (1 source: 0.5, 2 sources: 0.75, 3 sources: 0.9)
    - Consistency of data across sources (matching name, matching education, matching employer)
    - Account age and activity level on each source
    - Domain trust score for email verification
- Store verified profile data with provenance: which fact came from which source, when verified, when last refreshed
- Refresh verified data no more than every 30 days per attendee to manage API costs

**Should:**
- Detect and flag obvious gaming (brand-new GitHub accounts with no contributions, LinkedIn profiles with mismatched names)
- Allow attendees to add additional verification sources (Twitter/X, personal website, ORCID for researchers) for higher confidence
- Cache verification data to reduce API calls

**Must not:**
- Accept self-reported claims as verified data
- Display verification details (which sources, what data) to other users without the attendee's consent
- Sell or share raw verification data with sponsors

### 6.2 ICP matching engine

**Required:**
- Allow sponsors to define structured ICP criteria including:
    - Role categories (engineer, designer, founder, researcher, etc.)
    - Seniority bands (intern, junior, mid, senior; or class year for students)
    - Skill markers (specific languages, frameworks, public projects, paper publications)
    - Institution criteria (specific schools, school tiers, employer stages)
    - Behavioral criteria (won prior hackathon, contributed to specific repos, published research)
- Match each attendee against each sponsor's ICP, producing: match (full), partial match, no match
- Generate a human-readable explanation of why each attendee was/wasn't a match, for sponsor inspection
- Update matches in real time when attendee data is updated or sponsor ICP changes

**Should:**
- Use frontier LLMs (Claude or GPT-4-tier) for nuanced matching where rules don't suffice
- Cache match decisions per (attendee, sponsor) pair, invalidating when underlying data changes
- Surface low-confidence matches as "needs review" rather than auto-deciding

**Must not:**
- Match based on demographic data (race, gender, age beyond seniority context, religion, etc.) — explicitly prohibit these as ICP criteria
- Hallucinate matches: every claimed match must cite specific data from attendee profile

### 6.3 Booth scanner

**Required:**
- Mobile web app (no native app required for v1)
- Authenticate sponsor staff with simple login (no SSO required for v1)
- QR code scanner using device camera, fallback to manual code entry
- Display attendee profile within 2 seconds of scan
- Display match status with single-tap rating: "Strong fit" / "Some interest" / "Not a match"
- Optional voice memo capture (15-second cap, transcribed via Whisper API)
- Optional 60-character text note
- Queue scans locally if offline, sync when connectivity returns
- Show scanner activity feed for the staff member: their last 10 scans with status

**Should:**
- Show scanner-level statistics (total scans, ICP matches today)
- Allow staff to flag a scan for review post-event ("not sure if this counts as a match")
- Surface attendee profile photo (from LinkedIn) for face-name matching

**Must not:**
- Lose scan data due to connectivity issues (always queue locally first)
- Require more than 5 seconds of staff attention per scan in the standard flow

### 6.4 Real-time dashboards

**Required:**
- Sponsor dashboard updating within 5 seconds of any new scan
- Organizer dashboard updating within 30 seconds of major events (check-in, scan)
- Internal dashboard with system health, error rates, dispute flags

**Should:**
- Mobile-responsive (organizer and sponsor leads will check on phones)
- Email/SMS alerts for critical events (sponsor approaching cap, organizer-reported issue)
- Snapshot views for offline review

### 6.5 Contract execution

**Required:**
- Generate invoice automatically based on verified match counts
- Charge sponsor's saved payment method (Stripe integration)
- Calculate and queue organizer revenue share
- Provide audit trail per contract: every scan, every status change, every payment action with timestamp and actor

**Should:**
- Support split payments to multiple parties (organizer + platform)
- Generate downloadable PDF invoices with line-item breakdown
- Allow disputes within 7 days of invoice with documented evidence

**Must not:**
- Execute contract before manual review of flagged scans is complete
- Charge sponsor without sending a final invoice for confirmation

### 6.6 Post-event packet

**Required:**
- Generate within 48 hours of event close
- Contain for each verified match: full profile, scan timestamp, interaction rating, voice memo transcript or text note, suggested follow-up template
- Available as both PDF (for sharing) and interactive web view (for follow-up actions)
- Include sponsor's contract execution summary (matches, fees, ROI prediction vs actuals if applicable)

**Should:**
- Allow sponsor to add their own notes per attendee directly in the web view
- Generate suggested follow-up emails using AI, customized per attendee (drafted, not sent — sponsor reviews and sends)
- Surface attendees who flagged interest in the sponsor (parallel data from attendee-side prompts)

### 6.7 Outcome tracking

**Required:**
- Automated email cadence at +14, +30, +60, +90 days
- One-click access to outcome tracker showing all event matches
- Capture outcome status per attendee: no follow-up, contacted, interviewing, offered, hired, declined
- Capture optional details: role, salary range, decline reasons
- Triangulate with attendee-side prompts where possible

**Should:**
- Pre-populate outcome status based on signals (e.g., LinkedIn shows attendee changed jobs to sponsor company)
- Surface patterns to sponsor: "You convert 40% of strong-fit ratings to interviews; 8% of some-interest ratings."
- Generate annual ROI summary across all events sponsored

---

## 7. Technical architecture

### 7.1 Stack

**Backend:** Python (FastAPI) or TypeScript (Node), team's preference. Single monolith for v1, no microservices.

**Frontend:** React + Tailwind. Three primary surfaces:
- Public RSVP and composition reveal (no auth required for browsing)
- Authenticated dashboards (organizer, sponsor, sponsor booth staff, internal admin)
- Outcome tracker (authenticated)

**Database:** Postgres (primary), with pgvector for embedding similarity if needed in v1 (deferred unless required).

**File storage:** S3 or equivalent for resumes, voice memos, generated PDFs.

**Authentication:** Auth0, Clerk, or Supabase Auth. Do not roll custom auth.

**OAuth integrations:** LinkedIn (limited API — most-restricted), GitHub (open), email domain verification (custom).

**LLM calls:** OpenAI GPT-4-tier or Anthropic Claude for ICP matching, packet generation, follow-up template drafting.

**Speech-to-text:** OpenAI Whisper API for voice memo transcription.

**Payments:** Stripe (Standard Connect for split payments to organizers).

**Email:** Resend, Postmark, or SendGrid.

**Monitoring:** Sentry for errors, basic uptime monitoring.

### 7.2 Data model (high-level)

**Events:** id, organizer_id, name, date, location, expected_attendance, status, brand_assets, schedule, sponsor_list, ICP_categories.

**Organizers:** id, name, brand_assets, contract_terms, payment_details, status.

**Sponsors:** id, company_name, contract_id (per event), ICP_definition (structured), booth_staff_list, payment_method, status.

**Attendees:** id, identity_verifications (array of source, data, confidence, timestamp), profile_data (canonical), event_attendances (array), match_results_per_event (array).

**ApplicationDecisions:** event_id, attendee_id, decision, decision_reason, decided_by (system or person), timestamp.

**Scans:** id, event_id, sponsor_id, booth_staff_id, attendee_id, timestamp, rating, memo_text, memo_audio_url, match_status (auto-computed), match_status_reviewed (post-event).

**Contracts:** id, sponsor_id, event_id, base_fee, per_match_fee, cap, ICP_definition_snapshot, verified_match_count, final_invoice_amount, payment_status, audit_log.

**Outcomes:** id, event_id, sponsor_id, attendee_id, status, status_history (array), captured_via (sponsor_report or attendee_report or signal_inference), captured_at.

### 7.3 Performance targets

- RSVP page load: <2 seconds
- Application submit: <5 seconds for OAuth-driven, <10 seconds with manual entry
- Booth scanner scan-to-display: <2 seconds median, <4 seconds p95
- Real-time dashboard update: <5 seconds for sponsor, <30 seconds for organizer
- Post-event packet generation: <2 hours after event close (target 30 minutes)

### 7.4 Reliability requirements

- 99% uptime during event days (hard requirement — failure during a live event is a customer-relationship-ending event)
- Booth scanner must function offline with graceful sync
- All scans must be durably stored before scanner UI confirms scan to user
- Daily backups of full database
- Rollback capability for any deploy

### 7.5 Security and privacy requirements

- All attendee PII encrypted at rest and in transit
- Attendee data scoped per event — sponsors only see attendees from events they sponsored
- Sponsors do not see other sponsors' data
- Attendees can request data deletion at any time, processed within 7 days
- No selling or sharing of attendee data with third parties without explicit consent
- SOC 2 readiness as a Year 2 priority (not v1 blocker)

### 7.6 Data rights (critical contract terms)

For every organizer contract, the platform must retain:
- Right to retain attendee identity and behavioral data after the event ends
- Right to use that data to improve matching algorithms across events
- Right to surface aggregate patterns from the data to other organizers and sponsors
- Right to use attendee data to predict ROI for future sponsors of similar events

For every attendee, consent must be obtained for:
- Verification across multiple sources at registration
- Sharing identity profile with sponsors who match their declared interests
- Behavioral logging at the event for ROI measurement
- Cross-event pattern learning (with the option to delete or anonymize)

These are non-negotiable contract terms. Without them, the substrate cannot compound and the company cannot become defensible.

---

## 8. Edge cases and failure modes

### 8.1 Identity verification failures
- **OAuth fails or returns insufficient data:** fallback to manual entry with elevated review threshold.
- **Attendee provides conflicting data across sources:** flag for review, ask attendee to clarify.
- **Account appears recently created or low-activity:** flag for review, may require additional verification.

### 8.2 Booth scanner failures
- **Wifi unavailable:** queue scans locally, sync when restored. Visual indicator to staff.
- **Scanner returns wrong attendee:** allow correction within 30 seconds, log correction for audit.
- **Attendee not in system (walk-in):** manual entry flow with mandatory post-event verification before counting toward contract.

### 8.3 Match dispute scenarios
- **Sponsor disputes a verified match:** evidence trail (verification + interaction log) reviewed by internal mediator. Resolution within 7 days.
- **Sponsor wants to add a match not auto-detected:** request goes through review, must be substantiated by interaction evidence.
- **Multiple sponsors claim the same attendee as a match:** all valid matches counted (one attendee can be a match for multiple sponsors with different ICPs).

### 8.4 Event cancellation or under-delivery
- **Organizer cancels event before commitment cap:** all sponsors refunded base fee minus actual platform costs.
- **Event under-attended (<50% of predicted):** sponsors receive proportional refund of base fee, in addition to standard contingent terms.
- **Sponsor doesn't show up to event with paid base fee:** base fee retained, no per-match accrual possible.

### 8.5 Outcome tracking gaps
- **Sponsor doesn't respond to outcome prompts:** continue cadence; assume "no follow-up" as default after 90 days. Note in their record.
- **Attendee reports contact that sponsor didn't log:** flag for sponsor review; ask both sides for clarification.
- **Hire happens but neither side reports:** detected via LinkedIn job-change signal; ask both sides to confirm.

### 8.6 System failures during event
- **Platform goes down during live event:** event continues with manual fallback (paper sign-in, paper scan logs). Internal team on-site to handle. Data reconstructed post-event from manual records.
- **Specific feature breaks:** organizer and sponsors notified immediately with workaround. Repair within 1 hour or fall back to manual.

---

## 9. Specific contract terms for first deployment

### 9.1 Founders Inc / MakerMods operating contract
- Operating fee: $300 per event (v1 pricing, will increase as platform proves value)
- Data rights: platform retains all attendee identity, verification, and behavioral data; brand assets and event content remain with organizer
- Revenue share on sponsor contracts: 75% to organizer, 25% to platform (platform takes 25% as the entity providing measurement infrastructure)
- Term: per event, with mutual option to extend
- Exclusivity: not exclusive — organizer can use other tools, but for events run on this platform, all sponsor contracts must use platform's contingent structure

### 9.2 AI Taco contingent sponsor contract (template)
- Base fee: $5,000 (paid upfront on contract signing)
- Per-verified-ICP-match fee: $1,500
- Cap: $20,000 (i.e., max 10 matches counted)
- ICP definition (to be finalized with AI Taco): CS or related students at top-30 schools, junior or senior, with at least one shipped AI/ML public project in the last 12 months
- Verification criteria: GitHub OAuth + .edu email verification + ML/AI projects evidenced by public commits or papers
- Match dispute window: 7 days post-event
- Outcome tracking: sponsor commits to providing 30/60/90-day outcome reports for verified matches
- Renewal terms: option to renew at next platform-operated event, with pricing potentially adjusted based on actuals

### 9.3 Attendee terms of participation
- Free participation
- Required: identity verification via at least one OAuth source
- Optional: additional verification sources for higher confidence (and access to higher-stakes events in the future)
- Data sharing: profile shared with sponsors whose ICP matches; not shared with sponsors whose ICP doesn't match
- Behavioral logging at event: explicit consent required, presented as part of check-in
- Post-event: opt-in for sponsor contact (with default opt-in for ICP-matched sponsors only)
- Right to deletion: at any time, processed within 7 days

---

## 10. Success metrics

### 10.1 Operational metrics for first deployment (Founders Inc / MakerMods event)
- ≥80% of registered attendees complete identity verification with confidence > 0.7
- ≥90% of sponsor booth staff successfully use the scanner during the event
- <5% scanner failure rate (failed scans, missed attendees, errors)
- 100% of sponsor contracts executed within 48 hours of event close
- ≥70% of sponsors satisfied with the post-event packet (survey)
- 0 critical system failures during the live event

### 10.2 Business metrics for first 90 days
- 1 paying organizer contract executed end-to-end (Founders Inc / MakerMods)
- 1 paying sponsor contingent contract executed end-to-end (AI Taco)
- ≥3 additional organizer conversations advanced from outreach
- ≥3 additional sponsor conversations advanced from outreach
- Total revenue >$10,000 (combination of operating fees and sponsor contracts)

### 10.3 Substrate metrics for first 6 months
- ≥500 verified attendee profiles in the graph
- ≥5 events run on the platform
- ≥10 sponsor contracts executed
- ≥20 attributed outcomes (hires, interviews, offers) tracked end-to-end
- Identity verification confidence median > 0.8

---

## 11. Risks and mitigations

### 11.1 Single points of failure
- **Founder is the salesperson, the technical lead, the operator, and the customer success function.** Mitigation: hire one engineering lead within 60 days; identify a customer success freelancer for event-day operations.
- **MLH partnership is informal.** Mitigation: convert to written commitment within 30 days; do not depend on it for first deployment; treat as Year 2 acceleration, not Year 1 dependency.
- **AI Taco contract not yet signed.** Mitigation: sign within 14 days; if AI Taco backs out, identify backup sponsor before event date.

### 11.2 Product risks
- **Identity verification false positives let in bad-fit attendees.** Mitigation: conservative thresholds for v1, manual review of borderline cases, ongoing calibration as data accumulates.
- **Scanner fails during event.** Mitigation: paper backup, internal team on-site for all v1 events, explicit fallback runbook.
- **Sponsors dispute verified matches at scale.** Mitigation: clear ICP definitions agreed pre-event, evidence trail per scan, escalation path with internal mediator.

### 11.3 Market risks
- **Attendees reject identity verification as too invasive.** Mitigation: clear value proposition (better events, better matches, no spam), opt-in for sensitive uses, easy data deletion.
- **Sponsors reject contingent contracts as unfamiliar.** Mitigation: hand-walk the first 5 sponsors through the structure, anchor pricing such that contingent is upside vs flat-fee, offer flat-fee fallback if needed for early sales.
- **Organizers don't see operational value at $300 price point.** Mitigation: focus on outcome (sponsor renewal, attendee quality) as value driver; raise prices as evidence accumulates.

### 11.4 Existential risks
- **Underlying assumption fails: hackathons don't actually produce hires for sponsors.** Mitigation: track 30/60/90-day outcomes from first event aggressively. If conversion rate is near zero, pivot to a different event category before scaling further. **This is the single biggest risk to the entire thesis.**

---

## 12. Open questions

1. Should the first event support contingent contracts, or run with flat-fee sponsors and prove operational quality first? (Recommendation: contingent for AI Taco specifically, flat-fee for any other sponsors at the first event to reduce risk.)
2. What's the minimum viable composition reveal — emailed report, web page, or in-app real-time view? (Recommendation: emailed report at T-3 days for v1, in-app for v2.)
3. How do we handle attendees who are between roles or job-changing during the event? (Recommendation: capture both prior and intended roles, surface to sponsors with context.)
4. Do we allow sponsors to upload their own ICP rubric, or do we hand-craft it together for v1? (Recommendation: hand-craft for v1, self-serve for v2.)
5. What's the disclosure to attendees about which sponsors will see their profile? (Recommendation: list all sponsors at registration, make match logic transparent, opt-out on a per-sponsor basis.)
6. How do we price subsequent events? (Recommendation: track first event's outcomes, price next events based on demonstrated value — likely $1,500–$5,000 organizer fee, $10,000–$25,000 sponsor contracts.)
7. What's the legal structure for cross-event data use? (Open — needs counsel review before second event.)

---

## 13. Build sequence

**Weeks 1–2:**
- Set up infrastructure (database, auth, hosting, payments)
- Define data model
- Build admin tools for internal team to manage events, organizers, sponsors

**Weeks 3–4:**
- Public RSVP page with OAuth verification
- Application review interface for internal team and organizer
- Identity confidence scoring

**Weeks 5–6:**
- ICP matching engine
- Sponsor dashboard (pre-event view: expected matches based on confirmed attendees)
- Sponsor contract record-keeping and base-fee billing

**Weeks 7–8:**
- Booth scanner mobile web app
- Real-time match counting and dashboard updates
- Composition reveal email at T-3 days

**Weeks 9–10:**
- Post-event packet generation
- Contract execution flow (final invoicing, payment, organizer payout)
- Dispute resolution interface

**Weeks 11–12:**
- Outcome tracking loop (email cadence + tracker UI)
- Internal monitoring and alerting
- End-to-end testing with friendly dry-run event

**Week 13: Founders Inc / MakerMods event runs.**

**Weeks 14–17: Outcome capture, learnings, iteration.**

This timeline is aggressive and depends on the team being able to execute focused. If the team is solo, double the timeline.

---

## 14. Definition of done

V1 ships when:
- A complete attendee can register, get verified, get accepted, attend an event, and have their behavior logged
- A sponsor can sign a contingent contract, see real-time match counts during the event, and have the contract automatically execute post-event
- An organizer can run an event end-to-end on the platform without breaking
- An internal team member can monitor and intervene on any event in real time
- Post-event packets are produced within 48 hours
- Outcome tracking emails are sent on schedule

The Founders Inc / MakerMods event running successfully end-to-end with at least one contingent sponsor contract is the v1 success criterion.
