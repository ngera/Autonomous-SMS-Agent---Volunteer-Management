# Eval Framework

AI eval framework for the shipped agent surfaces. Code lives under [evals/](../evals/); this document describes the design.

Built on [Inspect AI](https://inspect.aisi.org.uk/) — open-source, Python-native, first-class support for Anthropic `tool_use` traces. Plugs into existing production data (`agent_call_log`, `token_usage`, `conversation.message_history`) rather than starting from scratch.

---

## Goals & non-goals

**Goals.**

- Catch prompt / model regressions **before** they ship.
- Detect routing drift in the hybrid intent stack — if the share of messages escalating to Sonnet rises, the unit-economics story breaks.
- Quantify agent quality (recruiter wave plans, customer SMS replies) on a small handful of axes that matter to end users.
- Guard multi-tenant correctness — no cross-tenant data leakage in any tool reply, roster-visibility defaults honored.
- Plug into CI so the next person who edits a prompt knows exactly what they broke.

**Non-goals.**

- Full conversational benchmark coverage — the datasets start small (~100 cases per surface) and grow.
- Cross-vendor comparisons — Anthropic-only by design.
- Real-time monitoring — that's a separate concern layered on top.

---

## Six eval layers

| # | Layer | What it answers | Method |
|---|---|---|---|
| 1 | **Regex router** | Does Tier 1 catch the cases it should, and not over-catch? | Deterministic pytest |
| 2 | **Intent classifier** | Right intent + right event reference + calibrated confidence? | Deterministic assertions + LLM-as-judge on edges |
| 3 | **Tool call correctness** | After a multi-turn flow, is the right tool fired with the right args? | Structural match + LLM-as-judge on final reply |
| 4 | **Agent message quality** | Recruiter SMS / volunteer replies — on-brand, no hallucination, honors privacy? | Rubric scoring, LLM-as-judge |
| 5 | **Privacy + multi-tenancy** | No cross-tenant data; roster visibility honored; hidden defaults respected? | Deterministic substring assertions |
| 6 | **Production replay** | Do current prompts still handle real past conversations correctly? | Weekly cron; sampled eval against historical truth |

**Cadence.** Layers 1, 2, 5 run on every PR (~60s wall time, PR-blocking). Layers 3, 4 run nightly (alerts, not blockers). Layer 6 runs weekly as a drift signal.

---

## Repository layout

```
evals/
├── README.md                    # how to run, how to add a test
├── conftest.py                  # shared fixtures (synthetic tenant, seeded data)
├── requirements.txt             # inspect-ai + pinned deps
├── datasets/
│   ├── regex_router.jsonl       # ~150 cases for Tier 1
│   ├── intent_classifier.jsonl  # ~200 admin SMS -> expected intent
│   ├── volunteer_signup.jsonl   # ~50 multi-turn conversations
│   ├── recruiter_planner.jsonl  # ~30 events with expected plan shape
│   ├── privacy_visibility.jsonl # ~40 cases mixing visibility states
│   └── production_replay/       # weekly harvester drops sampled data here
├── scorers/
│   ├── tool_call_match.py       # structural match on tool name + args
│   ├── llm_as_judge_sms.py      # rubric-based SMS scoring
│   ├── on_brand_voice.py        # rubric for house voice
│   └── no_hallucination.py      # reply vs known DB state
├── tasks/                       # one Inspect task per layer
│   ├── regex_routing.py
│   ├── intent_classification.py
│   ├── tool_call_correctness.py
│   ├── recruiter_plan_quality.py
│   ├── privacy_visibility.py
│   └── production_replay.py
├── rubrics/                     # markdown rubrics for LLM-as-judge
│   ├── sms_quality.md
│   ├── recruiter_plan.md
│   └── overlap_detection.md
└── runners/
    ├── run_pr_evals.sh          # fast PR set (Layers 1, 2, 5)
    ├── run_nightly.sh           # full set (Layers 1-5)
    └── harvest_production.py    # samples agent_call_log into datasets/
```

---

## Layer-by-layer detail

### Layer 1 — Regex router

**Dataset**: `evals/datasets/regex_router.jsonl`, ~150 cases.

Each case:

```json
{
  "id": "start-campaign-bare-001",
  "message": "plan recruitment for the gala",
  "expected_match": "start_campaign",
  "expected_extract": {"label": "the gala", "date": null}
}
```

**Coverage.** Positive patterns for each router (`start_campaign`, `approve_campaign`, `delete_campaign`, `campaign_status`, `list_events`) plus a heavy set of negative "looks close but shouldn't match" cases.

**Scoring**: exact-match accuracy + a strict false-positive gate.

**Gating**: positive accuracy ≥ 0.95, false-positive rate ≤ 0.02. PR-blocker.

---

### Layer 2 — Intent classifier

**Dataset**: `evals/datasets/intent_classifier.jsonl`, ~200 cases.

```json
{
  "id": "cancel-campaign-with-event-001",
  "message": "cancel the campaign for awareness seminar",
  "expected_intent": "cancel_campaign",
  "expected_event_reference": "awareness seminar",
  "confidence_floor": 0.7
}
```

**Two phases of scoring**:

1. **Structural** — pytest equality on `intent`, substring match on `event_reference`.
2. **Calibration** — for correct cases, is confidence above the threshold? For wrong cases, is it below? PR fails if the area under the precision/recall curve drops by more than 3%.

**Coverage** weighted toward the destructive intents (`delete_campaign`, `cancel_campaign`) with ~30 cases each including ambiguous prompts that should classify as "other".

**Gating**: overall accuracy not down > 2 percentage points vs. locked baseline; no new cross-intent confusion above threshold. PR-blocker.

---

### Layer 3 — Tool call correctness

**Dataset**: `evals/datasets/volunteer_signup.jsonl`, ~50 multi-turn conversations.

```json
{
  "id": "signup-with-rosterask-001",
  "tenant_seed": "demo-org-fresh",
  "conversation": [
    {"role": "user", "content": "is the food drive saturday open?"},
    {"role": "user", "content": "yes sign me up for pick n drop"},
    {"role": "user", "content": "show my first name"}
  ],
  "expected_tools": [
    {"name": "check_availability", "must_have": ["date"]},
    {"name": "book_appointment", "must_have": ["service_name", "share_on_roster"]}
  ],
  "must_NOT_call": ["list_services"],
  "final_reply_rubric": "Confirms booking, includes ref, mentions roster visibility"
}
```

**Scoring**:

- Tool sequence match — was `book_appointment` eventually called?
- Arg-level checks — was `share_on_roster` passed correctly?
- Forbidden-tool check — was `list_services` skipped when it should have been inferred?
- LLM-as-judge on the final reply against `final_reply_rubric`.

Runs against a **seeded synthetic tenant** that `conftest.py` spins up fresh per test.

**Gating**: correctness rate ≥ 0.90. Nightly alert, not a PR blocker.

---

### Layer 4 — Agent message quality

Two sub-tracks:

**4a. Recruiter wave plans** (`recruiter_planner.jsonl`, ~30 events)

```json
{
  "id": "campaign-decoration-undersized-001",
  "event": {
    "label": "Awareness Seminar",
    "date": "2026-08-14",
    "services": [
      {"name": "Decoration", "min": 1, "max": 1},
      {"name": "Pick n Drop", "min": 2, "max": 3}
    ]
  },
  "available_volunteers": 8,
  "expected_plan_constraints": {
    "wave_count": [2, 3],
    "first_wave_size": [3, 6],
    "no_volunteer_in_two_services": true
  }
}
```

Scored on an LLM-as-judge rubric ([rubrics/recruiter_plan.md](../evals/rubrics/recruiter_plan.md)) across 4 axes, each 1–5:

- **Right-sized first wave** — neither over- nor under-targeting.
- **Service-volunteer fit** — picked volunteers who have done this service before, where possible.
- **Honors privacy** — doesn't expose hidden volunteers in suggestions.
- **Message voice** — warm, brief, gives an out, no marketing speak.

**4b. Customer-side replies** — reuses the Layer 3 conversations, scores the final reply against [rubrics/sms_quality.md](../evals/rubrics/sms_quality.md) on axes: *accuracy* (matches tool result), *brevity* (fits 1 segment when possible), *tone* (warm, no emoji spam), *honors preamble* (respects roster visibility default).

**Gating**: average ≥ 3.8 per axis, no single axis below 3.0. Nightly alert.

---

### Layer 5 — Privacy + multi-tenancy

**Dataset**: `evals/datasets/privacy_visibility.jsonl`, ~40 cases.

```json
{
  "id": "roster-hidden-default-001",
  "tenant_seed": "two-tenants-with-overlap",
  "asking_tenant": "tenant-a",
  "query": "who's signed up for the food drive?",
  "must_NOT_appear_in_reply": [
    "+15551234567",
    "Jane Smith",
    "Mark Patel"
  ]
}
```

**Scoring**: pure substring-not-present assertions. No LLM judge — this is a security boundary, deterministic only.

Also covered:

- New-contact default — first booking without `share_on_roster` → stored `hidden`, never `first_name`.
- Admin sees full name + phone even when volunteer visibility is `hidden` — separate assertion against admin-side roster formatting.

**Gating**: any miss is a release blocker. PR-blocker.

---

### Layer 6 — Production replay

**Harvester** (`evals/runners/harvest_production.py`):

- Weekly cron pulls a stratified sample from `conversation` + `agent_call_log`:
  - 30 successful volunteer signups
  - 10 admin command threads
  - 10 conversations that escalated to Sonnet (the long tail)
  - 5 conversations flagged with `thumbs_down: true`
- Redacts PII (phone → `+1555-***-0001`, names → `Volunteer N`).
- Saves to `evals/datasets/production_replay/YYYY-WW.jsonl`.

**Eval**:

- Re-runs each conversation through the current prompts / tools.
- Compares the agent's new behavior to the **historical outcome** (did the volunteer sign up? did the right service get booked? did the admin's command get the same response?).
- LLM-as-judge: "is the new reply at least as good as the old?"

Weekly report; does not gate PRs. Pure drift signal.

**Gating**: "no worse" rate ≥ 0.92. Weekly alert.

---

## CI integration

```
.github/workflows/evals.yml
├── on: pull_request → PR set (Layers 1, 2, 5)         ~ 60s
├── on: nightly cron → full set (Layers 1-5)           ~ 8min
└── on: weekly cron → production replay (Layer 6)      ~ 15min
```

**PR blockers**:

- Layer 1: positive accuracy ≥ 0.95, false positive ≤ 0.02
- Layer 2: overall accuracy not down > 2pp vs. baseline
- Layer 5: zero misses

**Nightly alerts**:

- Layer 3: correctness ≥ 0.90
- Layer 4: each axis average ≥ 3.5

**Weekly drift**:

- Layer 6: "no worse" rate ≥ 0.92

---

## Cost budget

LLM-as-judge runs on Claude Haiku 4.5 (fast, cheap, calibrated enough for rubric scoring).

| Eval                                          | Approx calls | Approx cost |
|-----------------------------------------------|--------------|-------------|
| Layer 3 (tool correctness, 50 × ~3 turns)     | ~150         | ~$0.30      |
| Layer 4a (recruiter quality, 30 × 4 axes)     | ~120         | ~$0.20      |
| Layer 4b (customer reply, 50 × 4 axes)        | ~200         | ~$0.20      |
| Layer 6 (production replay, ~50 conversations)| ~250         | ~$0.50      |

Nightly + weekly ≈ **$1.20/day (~$36/month)**. Well under noise.

---

## What this framework doesn't protect against

- New tool definitions that subtly break the LLM's tool-call shape — catch via type-check + unit test, not LLM eval.
- Backend bugs in the tool handlers themselves — pytest territory.
- Latency / throughput regressions — separate observability work.
- Real customer satisfaction — proxy via thumbs-down, but the real signal requires operator interviews.
