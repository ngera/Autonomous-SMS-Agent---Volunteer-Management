# Overlap / Conflict Detection Rubric

Score the agent's handling of overlap conditions (double-booking
attempts, slot-already-full, service-conflict) on each axis 1-5.

### detection

Did the agent detect the overlap before committing the action?

- **5** — Detected before any tool call that would have caused harm.
- **3** — Detected post-hoc and rolled back.
- **1** — Did not detect; committed the harm.

### explanation

Did the agent explain the overlap to the volunteer in plain language?

- **5** — Clear, blame-free, names the conflicting commitment.
- **3** — Acknowledges the conflict but vague.
- **1** — Cryptic error or silent failure.

### resolution_offer

Did the agent offer at least one concrete next step (alternate slot,
service swap, time change)?

- **5** — Two alternatives offered, both legitimately available.
- **3** — One alternative offered.
- **1** — No alternatives.
