# Event Lifecycle — Functional Workflow

*What happens, in what order, who triggers it, and what each side sees.*

Version 1.0 · June 2026 · Companion to `memory/event_lifecycle_plan.md` (design rationale) and `requirements/01_functional_spec.md` (system-wide spec).

---

## Table of Contents

1. [Scope](#1-scope)
2. [Actors](#2-actors)
3. [Lifecycle states](#3-lifecycle-states)
4. [Workflow A — Check-in](#4-workflow-a--check-in)
5. [Workflow B — Mid-event service change (SWITCH / ALSO)](#5-workflow-b--mid-event-service-change-switch--also)
6. [Workflow C — Roster auto-pings](#6-workflow-c--roster-auto-pings)
7. [Workflow D — Check-out](#7-workflow-d--check-out)
8. [Workflow E — Post-event review](#8-workflow-e--post-event-review)
9. [Workflow F — Recognition](#9-workflow-f--recognition)
10. [SMS surface](#10-sms-surface)
11. [Admin UI surface](#11-admin-ui-surface)
12. [Cross-cutting rules](#12-cross-cutting-rules)
13. [Edge case matrix](#13-edge-case-matrix)

---

## 1. Scope

Covers the lifecycle of a **single booked event** from 30 minutes before its scheduled start through up to 7 days after it ends. Out of scope: solicitation/recruitment (handled by the recruiter agent), reminders (handled by the reminder pipeline), donation campaigns.

Each workflow describes the behaviour as observed by volunteers (SMS) and admins (SMS + web UI), independent of implementation. Phase numbers in headings refer to the five-phase rollout in `event_lifecycle_plan.md`; all five phases are now live.

---

## 2. Actors

| Actor | Channel | Capabilities |
|---|---|---|
| **Volunteer** | SMS only | Check in (`HERE`), check out (`DONE`), report a mid-event service change (`SWITCH <service>`, `ALSO <service>`), respond to admin asks |
| **Admin** (OWNER / MANAGER) | Web UI + SMS | Override any volunteer action, approve/reject mid-event changes, grade the event, grant manual recognitions, override the auto-close |
| **Owner** | Web UI + SMS | Everything an admin can do, plus unlock a finalized review during the 24h post-event window |
| **Super admin** | Web UI | Everything an owner can do; unlock review forever (compliance) |
| **System** | Background jobs | Schedules ping windows, triggers auto-close at T+end+1h, runs the post-event review evaluator, evaluates recognition criteria, decays the quality score |
| **Engagement agent** | LLM | Routes inbound volunteer SMS into intents (`HERE` / `DONE` / `HERE-AGAIN` / `BACK` / `SWITCH` / `ALSO`) |

---

## 3. Lifecycle states

The booking row carries the canonical status, but day-of behaviour layers three signals on top of it: `checked_in_at`, `checked_out_at`, and the existence of a `booking_review` row.

```
       [confirmed]
            │
            │  T-30  (check-in window opens)
            ▼
       [arrivable]   ← admin can mark checked-in; volunteer can text HERE
            │
            ▼
       [checked_in]  ← checked_in_at is set; admin sees green "live"
            │
            ▼
       [live]        ← T_start ... T_end; service log accepts SWITCH/ALSO
            │
            ▼
       [checked_out] ← checked_out_at is set (by volunteer DONE, admin, or auto-close at T+end+1h)
            │
            ▼
       [review_pending] ← booking_review row exists; awaiting admin grade
            │
            ▼
       [reviewed]    ← admin approved; quality score recomputed; recognition evaluator runs
            │
            ▼
       [recognized?] ← optional: 1..N volunteer_recognition rows granted
```

Two states are terminal-but-mutable:
- **reviewed** is editable by OWNER/SUPER_ADMIN during a 24-hour window; SUPER_ADMIN can unlock forever.
- **checked_out** can still be re-opened by an admin override that adds a new service log segment ("HERE-AGAIN").

---

## 4. Workflow A — Check-in

### A.1 Trigger window

Check-in becomes available at **T-30 minutes** relative to the booking's scheduled start. Early check-in before T-30 is rejected with a polite "too early" reply; the cut-off is configurable per tenant via the `early_checkin_window_minutes` setting.

### A.2 Variant 1 — Volunteer texts `HERE`

1. Volunteer sends `HERE` (or a natural-language equivalent the engagement agent classifies as `HERE`).
2. System looks up the sender by phone within the tenant.
3. If exactly one booking is in the [T-30, T_end] window for this contact → mark `checked_in_at = now`, `checked_in_source = volunteer_sms`. Reply: confirmation with event name + location.
4. If multiple matching bookings → reply asking which event (lists them with short codes).
5. If no matching booking but the contact exists → see Variant 4 below.
6. If sender phone is unknown to the tenant → see Variant 5 below.

### A.3 Variant 2 — Admin marks check-in

1. Admin opens the **Live events panel** on the dashboard or the **run sheet** for a specific event.
2. Admin clicks "Mark checked in" on a roster row.
3. System sets `checked_in_at = now`, `checked_in_source = admin_override`. No SMS is sent to the volunteer.

### A.4 Variant 3 — `HERE-AGAIN` (re-entry after check-out)

1. Volunteer who has already checked out for this event texts `HERE` (or `BACK`).
2. The engagement agent reclassifies the intent as `HERE-AGAIN` because `checked_out_at` is set.
3. System clears `checked_out_at`, opens a new service log segment, and resumes the event for that volunteer.
4. Hours derivation will later treat this as a multi-segment booking (see §12.3).

### A.5 Variant 4 — Known contact, no booking (walk-up by signed-up volunteer)

1. Volunteer is on the roster of *some* tenant event but not the live one. Engagement agent's `_find_live_slot_with_capacity` ranks live events by:
   - (a) any service they're already booked for today,
   - (b) preferred service capacity remaining,
   - (c) any open slot anywhere,
   - (d) none → polite "no slot available, please contact admin" reply.
2. When a single best slot is found, admin is notified to confirm the walk-up; volunteer receives a holding ack.

### A.6 Variant 5 — Unknown phone (walk-up candidate)

Decision: **Invitation-only.** The system does *not* auto-onboard.

1. Sender phone is not in `contacts`. A row is inserted into `volunteer_candidate` with `phone`, `inbound_message`, and `created_at`.
2. Sender receives a silent acknowledgement that does not promise event placement.
3. Admin sees the row in the **Walk-up candidates** dashboard panel and can promote (creates Contact + invitation flow) or dismiss.
4. Auto-prune: dismissed candidates older than 1 year are deleted on a nightly job.

### A.7 Status badge

After check-in, the run-sheet roster row shows:
- Green dot · "Checked in 4 min ago" if `checked_in_at` is recent.
- Yellow dot · "5 min late" if past T_start with no check-in.
- Grey dot · "Not yet arrived" if before T_start.

---

## 5. Workflow B — Mid-event service change (SWITCH / ALSO)

### B.1 Intent classification

The engagement agent recognises two distinct mid-event intents from a checked-in volunteer:

- **SWITCH `<service>`** — end the current service segment and start a new one (e.g. "switching to kitchen prep").
- **ALSO `<service>`** — keep the current service segment running *and* add a parallel one (multi-service booking, e.g. "also doing greeter").

### B.2 Sequence

1. Volunteer SMS arrives; classified as SWITCH or ALSO. The agent parses the target service name.
2. If parsing is ambiguous (no service or two candidates), the agent replies asking for clarification ("Which service: kitchen, greeter, or runner?"). It does *not* guess.
3. A `booking_service_log` row is inserted with `status = pending`, `requested_by = volunteer`.
4. The admin run-sheet shows a yellow "Pending change" pill on the volunteer's row with two buttons: **Approve** / **Reject**.
5. Admin clicks Approve → status flips to `approved`, the previous segment ends (for SWITCH) or stays open (for ALSO), and the volunteer receives a confirmation SMS.
6. Admin clicks Reject → status flips to `rejected`; volunteer receives "Admin asked you to stay on `<current>` for now."

### B.3 Supersede

If a second SWITCH/ALSO arrives before the first is decisioned:
1. The first pending row's status flips to `superseded` (optimistic-concurrency `version` check).
2. The second row becomes the new pending row.
3. If two admins race the Approve button on the same row, the loser sees `409 stale, please retry` and the UI re-fetches.

### B.4 Hours derivation

Each segment's contribution to total hours is computed from `started_at`, `ended_at`, and the service's duration. Multi-segment reconstruction (Decision §12.3) is the only way to compute hours for events where the volunteer changed services or re-entered.

---

## 6. Workflow C — Roster auto-pings

### C.1 Window

Auto-pings to admin are scheduled at fixed offsets relative to T_start:

| Offset | Trigger | Suppress if… |
|---|---|---|
| T-30 | Roster summary ping | — |
| T-15 | Late-warning ping | All booked volunteers already checked in |
| T0 | "Event started" ping | All booked volunteers already checked in |
| T+15 | Mid-event status ping | — |
| T+30 | Late-arrivals ping | All booked volunteers already checked in or checked out |
| T+45 | Check-out reminder ping | All booked volunteers already checked out |
| T+60 | Final ping | All booked volunteers already checked out |

### C.2 Recipient

The tenant's "ping admin" (configured per event in the run sheet, or defaulting to the booking's primary admin). Multiple admins per tenant can subscribe.

### C.3 Opt-out

Admin can text `STOP STATUS` at any time during the event to silence all subsequent pings for that event only. Future events restart pings normally. Logged in `roster_status_ping_log.suppression_reason = admin_optout`.

### C.4 Dispatch failures

Twilio errors are caught and recorded with `suppression_reason = dispatch_failed`. The admin can see failed pings in the observability dashboard ("Dispatch failure rate" metric).

---

## 7. Workflow D — Check-out

### D.1 Variant 1 — Volunteer texts `DONE`

1. Engagement agent classifies inbound SMS as `DONE`.
2. System sets `checked_out_at = now`, `checked_out_source = volunteer_sms`. The currently-open service log segment is closed with `ended_at = now`.
3. Volunteer receives a thank-you SMS: "Thanks for serving! See you next time."

### D.2 Variant 2 — Admin marks check-out

1. Admin clicks "Mark checked out" on the run sheet.
2. Same effect; `checked_out_source = admin_override`. No SMS.

### D.3 Variant 3 — Auto-close at T+end+1h

1. Background job runs at `scheduled_end_at + 1 hour`.
2. Any booking with `checked_in_at IS NOT NULL` and `checked_out_at IS NULL` is auto-closed.
3. `checked_out_at = scheduled_end_at` (not now — the assumption is the volunteer left at the official end).
4. `checked_out_source = auto_close`.
5. No SMS is sent.

### D.4 Variant 4 — No-show (no check-in by T+end+1h)

1. Same auto-close job: if `checked_in_at IS NULL` past the auto-close moment, the booking gets a `booking_review` row with `status = no_show` directly.
2. No hours credit.
3. The volunteer's `historical_quality_score` is updated using the no-show signal (decay-weighted).

---

## 8. Workflow E — Post-event review

### E.1 Creation

A `booking_review` row is created automatically when:
- Check-out happens (any variant), OR
- The auto-close marks a no-show.

Status flow:
```
pending → approved (admin grades + saves)
pending → skipped (admin chose not to grade)
pending → no_show (auto, never graded by admin)
```

### E.2 The grade

A 1–5 integer:
- **1** "Consider striking" — flags the contact for follow-up; tightens future targeting.
- **2** Below standard.
- **3** Met expectations (default).
- **4** Above standard.
- **5** Exceptional.

Plus an optional free-text note (visible to admins only, never sent to the volunteer).

### E.3 Approval

Admin opens the **Reviews** page (filtered to "Pending"), grades, and clicks Approve. Effects:
1. `status = approved`, `approved_at = now`, `approved_by_admin_id = current_admin`.
2. `recompute_quality_score_for_contact()` runs — see §12.2 for the formula.
3. `evaluate_and_grant_for_contact()` runs the recognition engine — see Workflow F.

### E.4 Bulk approval

Reviews page supports multi-select + "Approve all selected" using a single default grade (typically 3). The list is filtered server-side to `status = pending` to prevent accidentally re-approving finalized rows.

### E.5 Unlock window

OWNER and SUPER_ADMIN can unlock an approved review within 24 hours after approval. Unlock effects:
1. Status flips to `unlocked` (a holding state) so the row is editable but doesn't double-trigger recognition.
2. Quality score is recomputed on re-approval.
3. If a recognition was granted on the original approval, it is **not** automatically revoked — admin must manually revoke (Workflow F.5).

After the 24h window, only SUPER_ADMIN can unlock (compliance lever).

---

## 9. Workflow F — Recognition

### F.1 Three kinds

| Kind | Granted by | Examples |
|---|---|---|
| **Milestone** | Auto, on every review approval | "10 hours volunteered", "First event completed", "50 events served" |
| **Badge** | Auto (criteria) OR manual | "Top performer Q2", "5-star streak" |
| **Award** | Manual only | "Volunteer of the year", admin-bestowed honours |

### F.2 Definition

OWNERs define recognitions on the **Recognition** admin page. Each definition has:
- `kind` (immutable)
- `key` (stable id, immutable)
- `label` (display name)
- `uniqueness_scope` (immutable): `lifetime` | `per_event` | `per_period`
- `period_unit` (only when scope = `per_period`): `month` | `quarter` | `year`
- `auto_criteria` (JSON; required for milestones, optional for badges, ignored for awards):
  - `metric` ∈ `hours` | `events_completed` | `service_count` | `avg_grade_over_last_n`
  - `threshold` (number)
  - `service_id` (when metric = `service_count`)
  - `n` (when metric = `avg_grade_over_last_n`)

### F.3 Auto-evaluation

After review approval (Workflow E.3) the recognition engine:
1. Loads all active definitions for the tenant.
2. For each definition with `auto_criteria`, computes the metric value (e.g. total approved hours).
3. If `metric_value >= threshold`, attempts to grant via `INSERT … ON CONFLICT DO NOTHING` against the scope-specific partial unique index. This guarantees a single volunteer cannot earn the same definition twice within its scope.
4. For scope = `per_event`, the grant carries `earned_via_slot_id`. For scope = `per_period`, it carries `period_key` derived from `derive_period_key(period_unit, earned_at)`.

### F.4 Congratulations SMS (opt-in)

A tenant setting `recognition_congrats_enabled` (default `false`) controls whether the engine sends a congratulatory SMS on grant. When on:
- Volunteer receives "🎉 You earned the `<label>` recognition!"
- One SMS per grant; never resent if revoked + re-granted.

### F.5 Manual grant / revoke

From the Contact detail page → Recognition tab, MANAGERs can:
- **Grant** a badge or award (not milestones — those are auto-only). Selects a definition + optional notes.
- **View** historical grants with kind, scope, and earned date.

Revoke is not yet a first-class UI action; manual grant errors are corrected by a SUPER_ADMIN-only database operation. (Backlog item.)

---

## 10. SMS surface

### 10.1 Volunteer → System

| Keyword | Pre-event | During event | Post-event |
|---|---|---|---|
| `HERE` | Check in (within T-30 window) | Re-entry as `HERE-AGAIN` if already checked out | Out of window |
| `DONE` | Ignored | Check out | Ignored |
| `BACK` | Ignored | Re-entry alias for HERE-AGAIN | Ignored |
| `SWITCH <service>` | Ignored | Mid-event service change | Ignored |
| `ALSO <service>` | Ignored | Add parallel service | Ignored |
| Free text | Routed to engagement agent | Routed to engagement agent | Goes to follow-up / no-op |

### 10.2 System → Volunteer

- Check-in confirmation: "✓ Checked in to `<event>` at `<location>`."
- Check-in conflict: "You're booked for several events today — which one?"
- Walk-up ack (unknown phone): silent, no promise.
- SWITCH/ALSO approved: "Admin approved your switch to `<service>`."
- SWITCH/ALSO rejected: "Admin asked you to stay on `<current>` for now."
- Check-out thank-you: "Thanks for serving!"
- Recognition (opt-in only): "🎉 You earned the `<label>` recognition!"

### 10.3 System → Admin

Roster pings (Workflow C) are admin-facing SMS:
- T-30: "Tonight's `<event>`: `<n>` confirmed, `<m>` reminded."
- T+15: "Mid-event status — `<x>` of `<n>` checked in."
- T+45: "End of `<event>` approaching — `<y>` checked out."

Plus event-specific alerts:
- Walk-up candidate: "New unknown number texted HERE — review on dashboard."
- Mid-event SWITCH/ALSO: "`<volunteer>` requested `<switch/also>` `<service>` — approve in run sheet."

### 10.4 Admin → System

Admins can text:
- `STATUS` — receive a snapshot of any in-progress event.
- `STOP STATUS` — opt out of further auto-pings for the current event only.
- `APPROVE <id>` / `REJECT <id>` — decision a pending SWITCH/ALSO request from SMS.
- `CHECKIN <volunteer>` / `CHECKOUT <volunteer>` — override actions from SMS.

By default, admin SMS is interpreted as asking *about an event or volunteer*, not about themselves; admins must explicitly say "me" to opt into the volunteer flow.

---

## 11. Admin UI surface

| Page | Audience | Purpose |
|---|---|---|
| **Dashboard → Live events panel** | All admins | Shows currently-running events with roster, check-in counts, and walk-up candidate count. |
| **Walk-up candidates** | MANAGER+ | Triage list for unknown-phone walk-ups; promote or dismiss. |
| **Run sheet** (`/run-sheet/:slotId`) | MANAGER+ | Per-event roster with check-in/check-out controls, pending SWITCH/ALSO approvals, service log. |
| **Reviews** | MANAGER+ | Filterable list of pending reviews with bulk-approve + per-row grade entry. Unlock action visible to OWNER+. |
| **Event review** (`/event-review/:slotId`) | MANAGER+ | Single-event grading view with per-volunteer notes. |
| **Recognition** (`/recognition`) | OWNER | CRUD for award definitions; toggle is_active; deactivate. |
| **Contact detail → Recognition tab** | MANAGER+ for grant, all admins for view | Historical grants for one volunteer; manual grant dialog. |
| **Observability** | MANAGER+ | Five tabs of phase metrics (check-in, auto-pings, service log, reviews, recognition). |

---

## 12. Cross-cutting rules

### 12.1 Timezone assumption

All wall-clock comparisons (T-30, auto-close, period_key derivation) assume the tenant is in **US Eastern**. Multi-timezone support is in the backlog and explicitly deferred.

### 12.2 Quality score formula

`historical_quality_score` is a decay-weighted average of approved review grades:

```
score = Σ (grade_i × 0.9^i) / Σ (0.9^i)
```

where `i = 0` is the most recent review and increments backwards. A grade of 1 contributes a strong downward pull because the decay is mild; a no-show is treated as grade 0.

### 12.3 Multi-segment hours

A booking with N service log segments has total hours = Σ (segment_end - segment_start) for each closed segment, with one floor: the *first* segment cannot contribute less than 15 minutes of credit even if the volunteer texted DONE immediately ("early-credit floor"). Later segments use raw duration.

### 12.4 Optimistic concurrency

Service log rows carry a `version` integer. Any UPDATE checks `version = old_version`; rowcount=0 → `OptimisticLockError` → HTTP 409 with `"stale, please retry"`. The run-sheet UI re-fetches on 409.

### 12.5 Idempotency

All SMS-triggered state transitions use a deduplication key derived from `(message_sid, intent)` so a Twilio retry cannot double-credit a check-in.

### 12.6 Per-tenant prompts

Every LLM prompt used in the engagement agent (intent classification, ambiguity resolution, walk-up confirmation) lives in the **AI Prompts** admin UI, not in code. OWNERs can edit live; changes apply on the next message.

### 12.7 Recurring events

Each occurrence of a recurring event is its own booking. There is no "series" in the lifecycle — every check-in, review, and recognition is per-occurrence.

---

## 13. Edge case matrix

| # | Scenario | Behaviour |
|---|---|---|
| 1 | Volunteer texts `HERE` at T-45 | Reply "Too early — check-in opens 30 min before." Configurable. |
| 2 | Volunteer texts `HERE` at T+90 (after auto-close) | Reply "That event has already ended." No state change. |
| 3 | Volunteer texts `DONE` without checking in first | Reply "We don't see you as checked in — please text HERE first." |
| 4 | Volunteer texts `HERE` while booked for two simultaneous events | Reply with both options, ask which. |
| 5 | Two admins approve a SWITCH at the same moment | Optimistic-lock check; second admin sees 409 + UI re-fetch. |
| 6 | Volunteer texts `HERE-AGAIN` after being marked no-show by auto-close | Engagement agent reopens the booking, clears no-show review, creates new service log segment. |
| 7 | Admin texts `STATUS` for an event they don't admin | Reply with brief snapshot anyway; access is tenant-scoped, not event-scoped. |
| 8 | Recognition criteria threshold lowered after a volunteer already qualified | Next review approval re-evaluates; volunteers who now qualify but didn't before will receive new grants. Existing grants stay. |
| 9 | OWNER unlocks a review 23h59m after approval | Allowed (window check is strict-less-than 24h). The flip to "unlocked" status pauses recognition until re-approval. |
| 10 | SUPER_ADMIN deactivates a definition that already has grants | Existing grants stay visible on contact pages; no new evaluation for that definition. |
| 11 | Walk-up candidate row exists but the same phone now SMS-opts-in via normal flow | The opt-in flow creates the Contact; admin should manually dismiss the candidate row (or let auto-prune handle it after 1 year). |
| 12 | Tenant enables `recognition_congrats_enabled` after definitions already exist | Past grants do not retro-notify; future grants do. |
| 13 | A `SWITCH` request to a service the volunteer isn't qualified for | Admin still sees the pending row; they can reject or approve. The system does not pre-filter qualifications at request time. |
| 14 | Engagement agent classifies inbound SMS with low confidence | Falls through to free-text routing — usually replied to by the orchestrator's general fallback prompt. |

---

*End of document.*
