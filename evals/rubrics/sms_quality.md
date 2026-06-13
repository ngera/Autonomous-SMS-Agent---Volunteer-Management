# SMS Quality Rubric

Score the agent's SMS reply on each axis from 1 (terrible) to 5
(excellent). All four axes must be scored independently.

## Axes

### accuracy

Does every factual claim in the reply match the actual tool result and
the case context?

- **5** — Every claim verifiable; no invented names, dates, or services.
- **4** — Minor wording imprecision but no false claims.
- **3** — One ambiguous claim that could mislead the volunteer.
- **2** — One clearly false claim (wrong date, wrong service name).
- **1** — Multiple false claims OR a confident hallucination of a
  volunteer/event that doesn't exist.

### brevity

Does it fit in one SMS segment (≤160 chars) where reasonable?

- **5** — One segment, no filler.
- **4** — One segment with minor verbosity.
- **3** — Two segments where one would suffice.
- **2** — Three+ segments for a simple confirmation.
- **1** — Wall of text.

### tone

Warm, friendly, no excessive emoji, no marketing-speak.

- **5** — Sounds like a real coordinator: warm, brief, human.
- **4** — Pleasant but slightly stiff.
- **3** — Functional but cold.
- **2** — Marketing speak ("excited to announce", "amazing
  opportunity").
- **1** — Pushy, demanding, or off-puttingly enthusiastic.

### honors_preamble

Did the agent apply the conversation preamble — MY EXISTING BOOKINGS,
roster visibility defaults, etc.?

- **5** — Visibly applied preamble (e.g. referenced existing booking,
  honored hidden default).
- **4** — Did not contradict preamble.
- **3** — Slight ambiguity (could be reading preamble or could be
  guessing).
- **2** — Contradicted one preamble fact.
- **1** — Clearly ignored the preamble.
