import { CoordinatorCharacter } from "./coordinator-character";
import "./coordinator-character.css";

const traits = [
  "Middle-aged nonprofit coordinator with calm authority and warmth.",
  "Handles event plans, volunteer recruiting, roster scheduling, and fundraising runs.",
  "Visual props: clipboard, calendar, volunteer checklist, donor pledge notes, name badge.",
  "Animation-ready SVG layers for head, body, clipboard, calendar, notes, and badge.",
];

export function CoordinatorCharacterPage() {
  return (
    <main className="min-h-screen bg-[#f8f5ed] text-[#21343b]">
      <section className="mx-auto grid min-h-screen w-full max-w-6xl items-center gap-10 px-6 py-10 md:grid-cols-[1fr_1.05fr]">
        <div className="space-y-7">
          <div className="space-y-3">
            <p className="text-sm font-semibold uppercase tracking-[0.12em] text-[#407c87]">
              Animated character concept
            </p>
            <h1 className="text-4xl font-bold leading-tight md:text-5xl">
              Mara Ellis, nonprofit event coordinator
            </h1>
            <p className="max-w-xl text-lg leading-8 text-[#577078]">
              A grounded, capable coordinator designed for explainer videos about volunteer
              recruitment, event scheduling, and fundraising operations.
            </p>
          </div>

          <dl className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-[#d9e2df] bg-white p-4">
              <dt className="text-sm font-semibold text-[#407c87]">Personality</dt>
              <dd className="mt-1 text-sm leading-6 text-[#435b63]">
                Reassuring, organized, practical, and quietly upbeat under pressure.
              </dd>
            </div>
            <div className="rounded-lg border border-[#d9e2df] bg-white p-4">
              <dt className="text-sm font-semibold text-[#407c87]">Signature motion</dt>
              <dd className="mt-1 text-sm leading-6 text-[#435b63]">
                Gentle nod, checklist lift, floating notes, and steady scheduling rhythm.
              </dd>
            </div>
          </dl>

          <ul className="grid gap-3 text-sm leading-6 text-[#435b63]">
            {traits.map((trait) => (
              <li className="flex gap-3" key={trait}>
                <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[#db7a4b]" />
                <span>{trait}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex justify-center">
          <CoordinatorCharacter pose="planning" />
        </div>
      </section>
    </main>
  );
}

