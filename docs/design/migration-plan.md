# Design Migration Plan — Booking System → Notion design system

**Status:** Draft (2026-05-23). Not yet executed.

**Inputs:**
- Source target: [source-notion.design.md](./source-notion.design.md)
- Current baseline: [design.md](./design.md)

**Why this is a heavier-than-it-looks lift.** Notion's design system is built for a *marketing-rich, illustration-heavy, brand-confident product surface*. The booking system today is a *dense, neutral, utilitarian admin panel*. Adopting Notion's tokens (purple primary, deep navy hero, pastel feature tints, 40-44px touch targets, 80px hero typography, Notion-Sans / Inter) is straightforward at the CSS-variable + Tailwind config layer — that's a few files. Adopting Notion's *patterns* (centered hero with workspace mockup, pastel feature card grids, 4-tier pricing comparison, multi-column footer, etc.) is more invasive because the booking system has *no marketing surfaces today* and most of those patterns have no place to land in an admin app.

The plan below treats this as **two work streams** that can be done independently or together:

1. **Theme swap** (low-risk, high-visibility) — adopt Notion's color tokens, typography scale, radii, spacing, and the bits of component geometry that make sense in admin chrome. Visible "we re-skinned" change. ~3-5 files touched, ~1-2 days of work.
2. **Pattern adoption** (high-effort, opt-in) — build the marketing-style components Notion has (hero, pastel feature cards, pricing table, illustration system) for the surfaces that need them — likely a future public landing page / pricing page / docs site that doesn't exist yet. Don't speculatively build these for the admin app — they'd land on screens that don't need them.

Most of this doc focuses on Work Stream 1 because that's the practical near-term migration. Stream 2 is scoped at the end as "patterns ready when you build a marketing site."

---

## Token-by-token diff

Notation: `[KEEP]` = baseline already matches or is close enough; `[REPLACE]` = swap the value; `[NEW]` = baseline doesn't have it, add it; `[N/A]` = the target token doesn't apply to admin UI; `[ADAPT]` = take the spirit but recast for admin use.

### Colors — Brand & Primary

| Notion target | Current baseline | Action |
|---|---|---|
| `colors.primary` (signature purple) | `--primary: oklch(0.205 0 0)` (near-black) | **`[REPLACE]`** — single biggest visible change. Purple primary becomes the default button color across the admin panel. |
| `colors.primary-pressed` | not present | **`[NEW]`** — add for pressed states |
| `colors.primary-deep` | not present | **`[NEW]`** |
| `colors.brand-navy` (hero band) | not present | **`[N/A for admin]`** — no hero in admin app. Add when marketing surfaces ship. |
| `colors.brand-navy-deep` / `-mid` | not present | **`[N/A for admin]`** |
| `colors.link-blue` | not present (links currently use primary) | **`[NEW]`** — inline links should be blue, distinct from purple CTAs. This fixes a current ambiguity. |

### Colors — Brand spectrum (pink/orange/teal/green/yellow/brown/purple)

| Notion target | Current baseline | Action |
|---|---|---|
| All brand-* spectrum colors | not present | **`[NEW for admin]`** — but only the subset the admin uses for status indicators. Realistically: brand-green for "active/healthy", brand-orange for "warning/attention", brand-pink as accent. The full spectrum is for marketing illustrations and doesn't earn its keep in an admin panel. |

### Colors — Card tints (pastel feature backgrounds)

| Notion target | Current baseline | Action |
|---|---|---|
| `card-tint-peach/rose/mint/lavender/sky/yellow/yellow-bold/cream/gray` | not present | **`[N/A for admin]`** in Phase 1 of theme swap. Cards in the admin app are all white-on-white-with-hairline. Pastel tints don't have a home until marketing surfaces ship. **`[NEW for marketing]`** in Stream 2. |

### Colors — Surface

| Notion target | Current baseline | Action |
|---|---|---|
| `colors.canvas` (page bg + cards) | `--background` + `--card` both `oklch(1 0 0)` | **`[KEEP]`** — rename token to `canvas` for parity if desired, but the value is correct |
| `colors.surface` (subtle section bg) | `--secondary` / `--muted` / `--accent` all `oklch(0.97 0 0)` | **`[KEEP]`** the value, **`[ADAPT]`** the naming — consolidate three near-identical tokens into one `surface` token |
| `colors.surface-soft` | not present | **`[NEW]`** — useful for nested section division on dashboard |
| `colors.hairline` (1px borders) | `--border: oklch(0.922 0 0)` | **`[KEEP]`** the value, **`[ADAPT]`** the name |
| `colors.hairline-soft` / `-strong` | not present | **`[NEW]`** — Notion separates 3 hairline weights; today we have one. Adding gives more flexibility for nested sections. |

### Colors — Text

| Notion target | Current baseline | Action |
|---|---|---|
| `colors.ink-deep` (pure black) | not present | **`[NEW]`** — for occasional emphasis |
| `colors.ink` (primary text) | `--foreground: oklch(0.145 0 0)` | **`[KEEP]`** — rename to `ink` for parity |
| `colors.charcoal` (body emphasis) | not present | **`[NEW]`** — useful for "primary body text on tinted backgrounds" in Stream 2 |
| `colors.slate` (secondary text) | `--muted-foreground: oklch(0.556 0 0)` | **`[KEEP]`** — rename to `slate` |
| `colors.steel` (tertiary text) | not present | **`[NEW]`** — currently we'd reach for `text-muted-foreground` for both secondary and tertiary, conflating two roles |
| `colors.stone` / `colors.muted` | not present | **`[NEW]`** — quieter labels and disabled |
| `colors.on-dark` / `-muted` | not present | **`[N/A for admin]`** until dark-on-light contrast surfaces exist (hero bands) |

### Colors — Semantic

| Notion target | Current baseline | Action |
|---|---|---|
| `colors.semantic-success` | not present (we have no success token) | **`[NEW]`** — useful for "campaign active", "booking confirmed" badges in admin |
| `colors.semantic-warning` | not present | **`[NEW]`** — useful for "campaign awaiting approval", "pending reconfirmation" |
| `colors.semantic-error` | `--destructive: oklch(0.58 0.22 27)` | **`[KEEP]`** the value, **`[ADAPT]`** the name to `semantic-error` |

### Typography

| Notion target | Current baseline | Action |
|---|---|---|
| Notion-Sans (Inter-based) | Geist Variable | **`[REPLACE]`** — swap font family to Inter Variable. Geist and Inter are visually close; this is a name/glyph swap, not a structural one. Add `@fontsource-variable/inter` and update `--font-sans`. |
| `typography.hero-display` (80/600/1.05/-2px) | not present | **`[N/A for admin]`** — admin has no hero |
| `typography.display-lg` (56) | not present | **`[N/A for admin]`** |
| `typography.heading-1..5` | inconsistent ad-hoc Tailwind classes per page | **`[NEW + ADAPT]`** — define explicit scale tokens, but the *applied* sizes in admin can stay more modest. Recommend admin uses `heading-2` (36) for page titles, `heading-3` (28) for section, `heading-4` (22) for card titles. Reserve `heading-1` (48) and above for marketing. |
| `typography.subtitle` (18/400) | not present | **`[NEW]`** |
| `typography.body-md` (16/400/1.55) | implicitly `text-sm` (14) in most places | **`[ADAPT]`** — admin density argues to keep `body-sm` (14) as default body, with `body-md` (16) reserved for emphasis. Don't blindly inflate every text size to 16; would break information density. |
| `typography.body-md-medium` / `body-sm-medium` | not present | **`[NEW]`** — add 500-weight variants of each body size for emphasis runs |
| `typography.body-sm` (14/400/1.5) | implicitly `text-sm` | **`[KEEP]`** — admin default body |
| `typography.caption-bold` (13/600/1.4) | implicitly `text-xs` (12) without explicit weight | **`[NEW]`** — wire up the token; useful for status pill labels |
| `typography.button-md` (14/500/1.3) | `text-sm font-medium` in button.tsx | **`[KEEP]`** — token-name change only |

### Layout / Spacing

| Notion target | Current baseline | Action |
|---|---|---|
| `spacing.xxs` (4px) → `spacing.hero` (120px) | Tailwind defaults only | **`[NEW]`** — define spacing tokens to match. For admin, the `section` (64) and `section-lg` (96) values are oversized — admin cards live closer together. Keep the tokens but use `xl` (32) / `xxl` (48) as default section rhythm in admin. Marketing pages use the larger values when they ship. |
| 1280px max-width container | no global max-width | **`[ADAPT]`** — adopt as `--container-max: 1280px` and apply on a per-page basis. Dashboard / Analytics already render at full-width-of-main, which is fine; lists like Bookings benefit from a max-width to stop the table from becoming a wide-screen ribbon. |
| 32px gutters | `p-6` (24px) on `<main>` | **`[REPLACE]`** — bump main padding to `p-8` (32px) for parity. Modest density tradeoff. |

### Elevation & Depth

| Notion target | Current baseline | Action |
|---|---|---|
| Level 0 — flat with hairline border | Cards use `ring-1 ring-foreground/10` | **`[KEEP]`** the visual treatment, **`[ADAPT]`** — swap `ring-1` to `border border-hairline` for token parity. Visually identical. |
| Level 1 — subtle shadow (hover-elevated tiles) | ad-hoc | **`[NEW]`** — define token but apply sparingly in admin |
| Level 2 — card shadow | not present in admin (admin cards are flat with ring/border) | **`[NEW for marketing]`**, **`[N/A for admin]`** — admin flat-card aesthetic is fine |
| Level 3 — deep mockup shadow | not present | **`[N/A for admin]`** |
| Level 4 — modal shadow | shadcn modal defaults | **`[ADAPT]`** — replace with Notion's spec for consistency |

### Shapes (border radius)

| Notion target | Current baseline | Action |
|---|---|---|
| `rounded.xs` (4px) | not explicit | **`[NEW]`** |
| `rounded.sm` (6px) | `--radius-sm: calc(0.625 * 0.6)` ≈ 6px | **`[KEEP]`** |
| `rounded.md` (8px) — buttons, inputs | `--radius-md: calc(0.625 * 0.8)` ≈ 8px, but buttons use `rounded-lg` (10px) | **`[REPLACE]`** — change Button's default radius from `rounded-lg` to `rounded-md` (8px). Brings admin buttons to Notion's signature sober-rectangular geometry. |
| `rounded.lg` (12px) — cards | Card uses `rounded-xl` (14px) | **`[REPLACE]`** — drop Card's default to `rounded-lg` (12px). Minor tightening. |
| `rounded.xl` (16px), `xxl` (20), `xxxl` (24) | calc-derived larger sizes exist but unused | **`[KEEP + RENAME]`** |
| `rounded.full` (9999) — badges, pill tabs | Badge uses `rounded-4xl` (≈26px, effectively pill at h-5) | **`[REPLACE]`** — switch Badge to `rounded-full` for semantic clarity |

### Components

| Notion target | Current baseline | Action |
|---|---|---|
| `button-primary` (purple, 10/18 padding, rounded-md, 14/500 type) | `Button default` (near-black, h-8 / 32px tall, rounded-lg, text-sm font-medium) | **`[REPLACE]`** — purple bg + adjust to ≈40px tall (`h-10`) + `rounded-md`. Affects every admin button — heaviest single change in this plan. |
| `button-dark` (black on light) | not present | **`[NEW]`** — useful for "Save changes" type CTAs where purple is too brand-loud |
| `button-secondary` (outlined rectangular) | `Button outline` | **`[KEEP]`** with same radius/type updates |
| `button-on-dark` / `button-secondary-on-dark` | not present | **`[N/A for admin]`** |
| `button-ghost` | `Button ghost` | **`[KEEP]`** |
| `button-link` (link-blue inline) | `Button link` uses `text-primary` | **`[REPLACE]`** — switch to `text-link-blue`, not primary-purple. Distinguishes inline links from CTAs. |
| `card-base` / `card-feature` / `pricing-card` | `Card` (white + ring + rounded-xl) | **`[KEEP]`** as `card-base`. **`[NEW]`** variants `card-feature`, `pricing-card` if/when marketing surfaces ship. |
| `card-feature-yellow-bold` + pastel variants | not present | **`[N/A for admin]`** **`[NEW for marketing]`** |
| `text-input` (44px tall, rounded-md, focus-purple border) | `Input` (32px tall, rounded-lg, ring focus) | **`[REPLACE]`** — bump to `h-11` (44px), `rounded-md`, and switch focus border to `border-primary` (purple) on focus instead of the current ring treatment. Touch-target improvement + brand reinforcement. |
| `search-pill` | not present | **`[NEW]`** — useful for global search if/when it ships |
| `pill-tab` / `segmented-tab` | `Tabs` (shadcn) | **`[ADAPT]`** — wrap shadcn Tabs with our two variant classes to match Notion's pill / segmented styles |
| `badge-purple` / `pink` / `orange` | `Badge` variants are all grayscale + destructive | **`[REPLACE + NEW]`** — replace default badge with `badge-purple` styling; add chromatic variants for status (active/warning/error using semantic tokens) |
| `badge-tag-purple` / `orange` / `green` | not present | **`[NEW]`** — useful for the existing per-volunteer "preferred service" chips that today render with no distinguishing color |
| `badge-popular` | not present | **`[N/A for admin]`**, **`[NEW for marketing]`** |
| `comparison-table` | shadcn `Table` | **`[ADAPT]`** — current Table component can absorb the comparison-table styling. Pricing-comparison specific styling waits for marketing. |
| `workspace-mockup-card` | not present | **`[N/A for admin]`** |
| `testimonial-card` / `logo-wall-item` | not present | **`[N/A for admin]`**, **`[NEW for marketing]`** |
| `faq-accordion-item` | not present (we don't use accordions today) | **`[NEW for marketing]`** |
| `cta-banner-light` / `stat-row` | not present | **`[NEW for marketing]`** |
| `promo-banner` | not present | **`[NEW]`** — useful for "maintenance window 2026-06-15" admin announcements. Optional. |
| `hero-band-dark` | not present | **`[N/A for admin]`** **`[NEW for marketing]`** |
| `footer-region` / `footer-link` | not present | **`[N/A for admin]`** (admin has no footer), **`[NEW for marketing]`** |
| Top Navigation (marketing) | admin has `Sidebar` + `Header` | **`[N/A for admin]`** — different IA entirely. Marketing top-nav coexists with admin layout if both ship. |

---

## Stream 1: Theme swap (recommended near-term work)

**Goal:** Booking system admin UI looks Notion-flavored — purple primary, Inter typography, 8px-rounded buttons, 12px-rounded cards, 40-44px touch targets, semantic status colors. Visible change, low risk, no new feature surfaces.

**Files touched** (approximate):
- `frontend/src/index.css` — replace `:root` and `.dark` variable blocks with Notion-mapped values; add new tokens (link-blue, ink, slate, semantic-success, semantic-warning, hairline-soft/-strong, card-tint-* placeholders, brand-* if subset needed). Update `@theme inline` to expose the new tokens to Tailwind. Replace Geist import with Inter.
- `frontend/package.json` — swap `@fontsource-variable/geist` for `@fontsource-variable/inter`.
- `frontend/src/components/ui/button.tsx` — change default size to `h-10` (40px), default radius to `rounded-md` (8px), default variant uses `bg-primary` (now purple).
- `frontend/src/components/ui/card.tsx` — change default radius to `rounded-lg` (12px), swap `ring-1 ring-foreground/10` to `border border-hairline` for token parity.
- `frontend/src/components/ui/input.tsx` — bump to `h-11` (44px), `rounded-md`, swap focus to `focus:border-primary focus:ring-0` with thicker border-on-focus.
- `frontend/src/components/ui/badge.tsx` — drop default to chromatic (purple via primary), add `success`/`warning`/`tag-*` variants.
- `frontend/src/components/ui/tabs.tsx` — add `pill` and `segmented` variants alongside default.
- `frontend/src/components/layout/app-layout.tsx` — bump main padding `p-6` → `p-8`.
- Per-page touch-ups where typography size choices are notably off (Dashboard, Analytics, Settings) — bring page titles to a consistent `text-3xl font-semibold` (or our new `heading-2` token).

**Per-page audit (worth doing, light scope):**
- Dashboard — replace any explicit color usage (`text-green-600`, etc.) with semantic tokens
- Analytics — chart colors should pull from `--chart-*` already; verify
- Conversations — message bubble colors may need tweaking once primary is purple
- Test Tool / Multi-Volunteer Test — buttons/badges color shift will be visible
- Campaign detail page — uses status badges heavily; semantic colors land here

**Phases (Stream 1):**
1. **Token swap** (1-2 hours) — `index.css` only. Visible immediately: every button becomes purple, every text-foreground becomes Notion ink, every border becomes Notion hairline. Visual smoke test in dev.
2. **Component geometry** (1-2 hours) — Button/Input/Badge/Card radius + height updates.
3. **Per-page typography pass** (2-3 hours) — sweep page titles to consistent scale; introduce `text-heading-*` utility names via Tailwind plugin so it's explicit going forward.
4. **Semantic color adoption** (1-2 hours) — replace ad-hoc `text-green-600` / `text-yellow-600` etc. with the new semantic tokens.
5. **Verify in dev** — manually click through every page, screenshot before/after a few key pages.

Total: **half a day to a full day** of focused work.

---

## Stream 2: Pattern adoption (deferred; build when marketing surfaces ship)

These are the components from Notion's design that have no place in an admin app. Build them when the booking system grows a marketing surface (public landing page, pricing page, public docs).

| Pattern | When to build | Notes |
|---|---|---|
| `hero-band-dark` | When a `/marketing` route ships | Single biggest visual identity moment in Notion's design |
| `pastel feature cards` (peach/rose/mint/lavender/sky/yellow + yellow-bold) | When a public product page ships | Echo brand color spectrum |
| `pricing-card` + `pricing-card-featured` + `comparison-table` | When public pricing page ships | Already partially present via shadcn `Table` |
| `workspace-mockup-card` | When marketing showcases the admin UI | Take a real admin screenshot, frame in deep drop shadow |
| `testimonial-card` / `logo-wall-item` | When social proof is part of the marketing pitch | Standard pattern, low novelty |
| `faq-accordion-item` | When public docs / help ship | Light lift |
| `cta-banner-light` / `stat-row` / `promo-banner` | When marketing IA exists | Trivial individually |
| `footer-region` + `footer-link` | When marketing IA exists | Required for any public page |
| Top Navigation (marketing) | When marketing IA exists | Sits alongside admin Sidebar — different layout entirely |
| Multi-tier responsive collapse strategy (`80px → 56 → 48 → 36` hero) | When hero ships | Don't pre-bake the responsive tokens until a hero exists to test them |

**Decision:** explicitly DEFER Stream 2 until there's a real marketing surface to land on. Building it speculatively in the admin app would mean shipping components nothing uses, which rots faster than the tokens themselves.

---

## Risks & gotchas

| Risk | Mitigation |
|---|---|
| **Purple as primary changes the feel of the entire admin app.** Every button, focus ring, link is currently grayscale. Going purple is loud — some admins will react. | Ship Stream 1 behind a feature flag for a week if any tenant is conservative. Otherwise, ship and adjust. The brand intent is purple — adopt it. |
| **Button height 32 → 40 increases vertical density loss.** Pages with many buttons (Bookings list, Campaign rows) will look airier; could mean more scrolling on dense tables. | Quantify before vs. after on the two densest pages (Bookings, Conversations). If the loss is >10% rows visible, consider keeping `size="sm"` as the default in dense table contexts via a per-page override. |
| **Inter vs. Geist** is a near-zero visual change at most sizes. Some letter shapes differ (the lowercase `a`, the dot on `i`); some admins won't even notice. | Just do it. Mention in the migration changelog. |
| **`ring` → `border` on Card** is a subtle render difference. `ring` doesn't take layout space; `border` does (1px). Could break ultra-precise pixel-aligned layouts (we don't have any but a per-page sweep is worth it). | Verify in dev. If anything breaks, the fix is `border` + adjust padding by `-1px` on the affected component. |
| **OKLCH → hex/rgb conversion accuracy.** Notion's design.md provides token names, not values. We'll need to **pick OKLCH values that approximate the Notion brand colors**. Notion's actual purple is something like `#7C3AED` ish; the navy is around `#191919` ish. Verify against screenshots once Stream 1 lands. | Step 0 of execution: extract approximate OKLCH values from screenshots of the live Notion site (or the design.md if it has hex values that I missed). Don't ship Stream 1 with placeholder purples. |
| **Notion-Sans is proprietary.** We can't ship "Notion-Sans" as a font name. Inter Variable is the documented fallback per their spec and is what we should use. | Already noted — substitute Inter at the font layer. |
| **Semantic-success / -warning don't exist today.** Adding them means scanning the codebase for places that should adopt them. | Scope the sweep to ~5 places (campaign status, booking status, suspension status, dashboard alerts, error banners). Anything else stays grayscale until it surfaces. |

---

## Decision points before execution

These are choices that materially shape Stream 1 — confirm before I touch code:

1. **Touch target bump (32 → 40/44 px)** — go all-in (every button + input in the app) or keep dense in table contexts via overrides? Recommend: all-in, then add size overrides if specific pages feel cramped.
2. **Inter vs. Geist** — confirm OK to swap. Visual delta is small but it IS a swap.
3. **Color values** — do you want me to extract approximate OKLCH equivalents for Notion's actual purple/navy/etc. from the Notion website, or do you have hex values already? The design.md you provided uses token references (`{colors.primary}`) without committed values.
4. **Stream 2 scope** — confirm deferral. If you want any Stream 2 piece (e.g., promo-banner for admin maintenance windows), name it and I'll lift it forward.
5. **Per-tenant theming** — current plan ships one theme for everyone. If different tenants might want different brand colors, the right move is to scope `--primary` to a CSS class on `<html>` set per-tenant from a server-rendered hint. Separate effort, not blocking.

---

## Phased execution checklist (when ready to ship)

- [ ] Resolve decision points above
- [ ] Extract / commit specific OKLCH values for the new tokens (don't ship with placeholders)
- [ ] PR 1 — Token swap (`index.css` only). Visible immediately.
- [ ] PR 2 — Component geometry (Button / Card / Input / Badge / Tabs)
- [ ] PR 3 — Per-page typography pass
- [ ] PR 4 — Semantic color sweep
- [ ] Manual QA pass — click through every authenticated route, screenshot a few key pages
- [ ] Update `design.md` (baseline) to reflect post-migration state — or replace it wholesale with the Notion-aligned doc
- [ ] Defer Stream 2 to "when marketing surfaces ship"

---

## Out of scope for this plan

- Dark mode polish (admin app doesn't use it; if it ships, follow Notion's `on-dark` and `brand-navy` conventions)
- Animation/transition tokens (Notion's spec leaves them out; recommend 150–200ms ease across the board when adopted)
- Per-tenant theming (separate effort; see decision point #5)
- Building the marketing site (Stream 2; build when needed)
- Migrating from `@base-ui/react` to a different primitive library — Notion's spec doesn't dictate primitives, just visual tokens. Base UI stays.
