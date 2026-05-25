import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowUp,
  Ban,
  Calendar,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Heart,
  MessageSquare,
  Plug,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-zinc-900">
      <TopNav />
      <Hero />
      <LogoStrip />
      <AgentsSection />
      <AdminDashboardSection />
      <DashboardSection />
      <IntegrationsSection />
      <TrustSection />
      <PricingSection />
      <FAQSection />
      <BottomCTA />
      <Footer />
    </div>
  );
}

function Wordmark({
  variant = "blue",
  className,
}: {
  variant?: "blue" | "white";
  className?: string;
}) {
  const src =
    variant === "white" ? "/brand/wordmark-white.svg" : "/brand/wordmark-blue.svg";
  return (
    <img
      src={src}
      alt="mustr"
      className={cn("h-10 w-auto", className)}
    />
  );
}

function TopNav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-200/80 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link to="/" className="text-zinc-900">
          <Wordmark />
        </Link>
        <div className="hidden items-center gap-7 text-sm text-zinc-600 md:flex">
          <a href="#agents" className="hover:text-zinc-900">
            Product
          </a>
          <a href="#pricing" className="hover:text-zinc-900">
            Pricing
          </a>
          <a href="#faq" className="hover:text-zinc-900">
            FAQ
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-medium text-zinc-700 hover:text-zinc-900"
          >
            Login
          </Link>
          <a
            href="#cta"
            className="rounded-full bg-[#0F172A] px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Book demo
          </a>
        </div>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <section className="bg-gradient-to-b from-[#F5F8FC] via-white to-white px-6 py-20">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <Wordmark className="h-32 w-auto" />
          <h1 className="mt-8 text-7xl font-extrabold leading-[1.02] tracking-tight">
            Your nonprofit&apos;s growth team.{" "}
            <em className="text-[#1c2d4a]">By text.</em>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-zinc-600">
            <span className="font-semibold text-zinc-900">mustr</span> recruits
            volunteers, fills shifts, sends reminders, and runs donation
            campaigns &mdash; all over plain SMS. No app for your volunteers. No
            spreadsheet for you.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#cta"
              className="rounded-full bg-[#007AFF] px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#0066d6]"
            >
              Book a 15-min demo
            </a>
            <a
              href="#hero-thread"
              className="rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50"
            >
              Watch a real conversation &rarr;
            </a>
          </div>
        </div>
        <div id="hero-thread" className="flex justify-center lg:justify-end">
          <HeroThread />
        </div>
      </div>
    </section>
  );
}

const HERO_MESSAGES: Array<{ kind: "in" | "out"; text: string }> = [
  {
    kind: "in",
    text: "Hi Maya 👋 We're 3 short for Sunday's 8am food drive — can you swing by?",
  },
  { kind: "out", text: "Sunday is a stretch. Got anything Saturday?" },
  {
    kind: "in",
    text: "Yes — Sat 9am pickup at the warehouse. ICS attached. Reply Y to lock it in.",
  },
  { kind: "out", text: "Y" },
  { kind: "in", text: "Locked in. See you Saturday 9am 🙌" },
];

function HeroThread() {
  return (
    <div className="w-full max-w-sm overflow-hidden rounded-3xl border border-[#9CADC2] bg-[#D2DBE8] shadow-2xl">
      <div className="flex items-center justify-between gap-2 border-b border-[#9CADC2] bg-[#BCC9DA]/95 px-3 py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#9CADC2] text-base">
            🤖
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight text-black">
              mustr
            </p>
            <p className="truncate text-[11px] leading-tight text-black">
              Recruiter agent
            </p>
          </div>
        </div>
        <span className="text-[11px] text-black/70">today</span>
      </div>

      <div className="space-y-1.5 bg-[#D2DBE8] px-3 py-4">
        {HERO_MESSAGES.map((m, i) => {
          const isOut = m.kind === "out";
          return (
            <div
              key={i}
              className={cn(
                "flex w-full",
                isOut ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[78%] whitespace-pre-wrap border border-[#9CADC2] bg-[#FBF6EE] px-3 py-1.5 text-sm leading-snug text-[#1c1c1e]",
                  isOut
                    ? "rounded-[18px] rounded-br-[4px]"
                    : "rounded-[18px] rounded-bl-[4px]"
                )}
              >
                {m.text}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 border-t border-[#9CADC2] bg-[#BCC9DA]/95 px-2 py-2 backdrop-blur">
        <div className="h-8 flex-1 rounded-full border border-[#9CADC2] bg-[#FBF6EE] px-3 py-1.5 text-sm text-[#7e8a9c]">
          iMessage
        </div>
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#9CADC2] text-white">
          <ArrowUp className="h-4 w-4" strokeWidth={3} />
        </div>
      </div>
    </div>
  );
}

const LOGO_ORGS = [
  "Sample Food Bank",
  "City Animal Rescue",
  "Coastline Faith",
  "Rapid Relief Network",
  "Open Hands Coalition",
  "Westside Shelter",
];

function LogoStrip() {
  return (
    <section className="border-y border-zinc-200 bg-zinc-50/60 px-6 py-10">
      <div className="mx-auto max-w-6xl">
        <p className="text-center text-xs uppercase tracking-wider text-zinc-500">
          Trusted by food banks, animal shelters, faith communities, and
          disaster-relief teams across the U.S.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
          {LOGO_ORGS.map((org) => (
            <span
              key={org}
              className="text-sm font-semibold uppercase tracking-wide text-zinc-400"
            >
              {org}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

const AGENTS = [
  {
    icon: Cpu,
    name: "Recruiter",
    tag: "Fills empty events while you sleep.",
    body: "Plans outreach in waves, targets the right volunteers, escalates only when it can't close the gap.",
  },
  {
    icon: Calendar,
    name: "Scheduler",
    tag: "Books, swaps, and cascades reschedules.",
    body: "Multi-shift events, ICS calendar sync, no double-bookings ever.",
  },
  {
    icon: MessageSquare,
    name: "Engagement",
    tag: "Reminds, follows up, retains.",
    body: "Reminders, no-show chase, attendance tracking, retention loops.",
  },
  {
    icon: Heart,
    name: "Marketing",
    tag: "Runs donation campaigns end-to-end.",
    body: "Touch sequences, attribution, IRS-ready receipts. Stripe Connect built in.",
  },
];

function AgentsSection() {
  return (
    <section id="agents" className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">Meet the agents</h2>
          <p className="mt-3 text-lg text-zinc-600">
            Four specialists, one Orchestrator. Each one purpose-built &mdash;
            not a chatbot bolt-on.
          </p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            return (
              <div
                key={a.name}
                className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E1E9F4] text-[#1c2d4a]">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{a.name}</h3>
                <p className="mt-1 text-sm italic text-[#1c2d4a]">{a.tag}</p>
                <p className="mt-3 text-sm leading-relaxed text-zinc-600">
                  {a.body}
                </p>
              </div>
            );
          })}
        </div>
        <p className="mt-10 text-center text-sm text-zinc-500">
          All coordinated by an{" "}
          <span className="font-semibold text-zinc-900">Orchestrator</span>.
          Admin takeover is one tap away.
        </p>
      </div>
    </section>
  );
}

const ADMIN_KPIS = [
  { label: "Volunteers", value: "1,247", trend: "+38 this mo" },
  { label: "This week", value: "7", trend: "5 recurring · 2 one-time" },
  { label: "Open slots", value: "23", trend: "Across 4 events" },
  { label: "Monthly bookings", value: "184", trend: "+12% vs last mo" },
];

const ADMIN_WEEK = [
  { name: "Sat 9am · Food Drive (Warehouse)", booked: 8, max: 12 },
  { name: "Sun 8am · Animal shelter pickup", booked: 12, max: 12 },
  { name: "Mon 10am · Front desk", booked: 4, max: 8 },
  { name: "Tue 6pm · Phone bank", booked: 15, max: 20 },
  { name: "Wed 7am · Kitchen prep", booked: 6, max: 6 },
];

const ADMIN_ALERTS = [
  {
    icon: AlertTriangle,
    title: "Food drive understaffed",
    body: "Sat 9am — 8/12 booked",
    tone: "amber" as const,
  },
  {
    icon: ClipboardList,
    title: "3 strikes pending review",
    body: "No-shows last 7 days",
    tone: "neutral" as const,
  },
  {
    icon: Ban,
    title: "1 volunteer suspended",
    body: "Awaiting action",
    tone: "neutral" as const,
  },
];

const ADMIN_CAMPAIGNS = [
  { name: "Fall Donor Drive", value: "$12.4k raised", color: "text-emerald-600" },
  { name: "Sat Recruit Wave", value: "47 invites sent", color: "text-[#007AFF]" },
];

function AdminDashboardSection() {
  return (
    <section className="bg-[#F8FAFC] px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">
            Run your week from one screen
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            Every event, every volunteer, every alert &mdash; at a glance.
          </p>
        </div>
        <div className="mt-12">
          <FakeAdminDashboard />
        </div>
      </div>
    </section>
  );
}

function FakeAdminDashboard() {
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl">
      <div className="flex items-center gap-2 border-b border-zinc-200 bg-zinc-50 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400" />
        <span className="h-3 w-3 rounded-full bg-yellow-400" />
        <span className="h-3 w-3 rounded-full bg-green-400" />
        <span className="ml-3 text-xs text-zinc-500">mustr — Dashboard</span>
      </div>

      <div className="space-y-6 p-6">
        <div>
          <p className="text-sm text-zinc-500">Good morning, Sarah 👋</p>
          <p className="text-lg font-semibold text-zinc-900">
            7 events this week.{" "}
            <span className="text-amber-600">2 still need volunteers.</span>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {ADMIN_KPIS.map((k) => (
            <div
              key={k.label}
              className="rounded-xl border border-zinc-200 bg-white p-3"
            >
              <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                {k.label}
              </p>
              <p className="mt-1 text-xl font-bold text-zinc-900">{k.value}</p>
              <p className="text-[10px] text-zinc-500">{k.trend}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-xl border border-zinc-200 bg-white p-4 lg:col-span-2">
            <p className="text-sm font-semibold text-zinc-900">This week</p>
            <div className="mt-3 space-y-3">
              {ADMIN_WEEK.map((ev) => {
                const pct = Math.round((ev.booked / ev.max) * 100);
                const full = ev.booked >= ev.max;
                return (
                  <div key={ev.name} className="flex items-center gap-3 text-xs">
                    <div className="flex-1">
                      <div className="flex items-baseline justify-between">
                        <p className="font-medium text-zinc-800">{ev.name}</p>
                        <p className="text-zinc-500">
                          {ev.booked}/{ev.max}
                        </p>
                      </div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-100">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            full ? "bg-emerald-500" : "bg-[#007AFF]"
                          )}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                    {!full && (
                      <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-700">
                        needs vols
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-4">
            <p className="text-sm font-semibold text-zinc-900">
              Needs attention
            </p>
            <div className="mt-3 space-y-2">
              {ADMIN_ALERTS.map((a) => {
                const Icon = a.icon;
                const isAmber = a.tone === "amber";
                return (
                  <div
                    key={a.title}
                    className={cn(
                      "flex items-start gap-2 rounded-lg border p-2 text-xs",
                      isAmber
                        ? "border-amber-200 bg-amber-50"
                        : "border-zinc-200 bg-zinc-50"
                    )}
                  >
                    <Icon
                      className={cn(
                        "mt-0.5 h-3.5 w-3.5 flex-shrink-0",
                        isAmber ? "text-amber-600" : "text-zinc-500"
                      )}
                    />
                    <div>
                      <p
                        className={cn(
                          "font-medium",
                          isAmber ? "text-amber-900" : "text-zinc-900"
                        )}
                      >
                        {a.title}
                      </p>
                      <p
                        className={cn(
                          "text-[10px]",
                          isAmber ? "text-amber-700" : "text-zinc-500"
                        )}
                      >
                        {a.body}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>

            <p className="mt-4 text-[10px] uppercase tracking-wider text-zinc-500">
              Active campaigns
            </p>
            <div className="mt-2 space-y-1.5 text-xs">
              {ADMIN_CAMPAIGNS.map((c) => (
                <div key={c.name} className="flex items-center justify-between">
                  <p className="text-zinc-700">{c.name}</p>
                  <span className={cn("font-medium", c.color)}>{c.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DashboardSection() {
  return (
    <section className="bg-[#0F172A] px-6 py-24 text-white">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <h2 className="text-4xl font-bold tracking-tight">
            Inside every conversation
          </h2>
          <p className="mt-3 text-lg text-zinc-300">
            Every thread. Every AI decision. One screen.
          </p>
          <ul className="mt-8 space-y-4 text-zinc-300">
            {[
              "One screen for every conversation — see every volunteer thread and every AI decision in real time.",
              "One-click takeover when a thread needs a human.",
              "Replayable trace tab — know exactly why the agent said what it said.",
            ].map((line) => (
              <li key={line} className="flex gap-3">
                <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-[#7BA9F0]" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
        <FakeDashboard />
      </div>
    </section>
  );
}

function FakeDashboard() {
  const inbox = [
    "Maya Lopez",
    "Daniel Reyes",
    "Ava Chen",
    "Marcus Patel",
    "Lily Brooks",
  ];
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl">
      <div className="flex items-center gap-2 border-b border-zinc-700 bg-zinc-800/80 px-4 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400" />
        <span className="h-3 w-3 rounded-full bg-yellow-400" />
        <span className="h-3 w-3 rounded-full bg-green-400" />
        <span className="ml-3 text-xs text-zinc-400">mustr — Conversations</span>
      </div>
      <div className="grid grid-cols-3 divide-x divide-zinc-700">
        <div className="space-y-1 p-3 text-xs">
          <p className="px-1 pb-1 text-[10px] uppercase tracking-wider text-zinc-500">
            Inbox
          </p>
          {inbox.map((n, i) => (
            <div
              key={n}
              className={cn(
                "rounded-md px-2 py-2",
                i === 0 ? "bg-zinc-700/60" : "hover:bg-zinc-800"
              )}
            >
              <p className="font-medium text-zinc-200">{n}</p>
              <p className="truncate text-[10px] text-zinc-500">
                {i === 0
                  ? "Sun is a stretch. Got anything Sat?"
                  : "Can't make it this week — sorry!"}
              </p>
            </div>
          ))}
        </div>
        <div className="space-y-2 p-3 text-xs">
          <p className="px-1 pb-1 text-[10px] uppercase tracking-wider text-zinc-500">
            Conversation
          </p>
          <div className="space-y-1.5 text-[11px]">
            <div className="rounded-lg bg-zinc-700/50 px-2 py-1.5 text-zinc-200">
              3 short for Sun 8am food drive — swing by?
            </div>
            <div className="ml-6 rounded-lg bg-[#1f2c50] px-2 py-1.5 text-zinc-100">
              Sun is a stretch. Got anything Sat?
            </div>
            <div className="rounded-lg bg-zinc-700/50 px-2 py-1.5 text-zinc-200">
              Yes — Sat 9am. Reply Y to lock it in.
            </div>
            <div className="ml-6 rounded-lg bg-[#1f2c50] px-2 py-1.5 text-zinc-100">
              Y
            </div>
            <div className="rounded-lg bg-zinc-700/50 px-2 py-1.5 text-zinc-200">
              Locked in. See you Saturday 🙌
            </div>
          </div>
        </div>
        <div className="space-y-2 p-3 text-xs">
          <p className="px-1 pb-1 text-[10px] uppercase tracking-wider text-zinc-500">
            Trace
          </p>
          <div className="space-y-1 font-mono text-[10px] text-zinc-400">
            <p>
              <span className="text-[#7BA9F0]">▸ recruiter</span> matched 12
              candidates
            </p>
            <p>
              <span className="text-[#7BA9F0]">▸ engagement</span> sent SMS · 0.4s
            </p>
            <p>
              <span className="text-[#7BA9F0]">▸ scheduler</span> proposed Sat 9am
            </p>
            <p>
              <span className="text-[#7BA9F0]">▸ scheduler</span> booked slot
              #4821
            </p>
            <p>
              <span className="text-[#7BA9F0]">▸ engagement</span> sent
              confirmation
            </p>
            <p>
              <span className="text-[#7BA9F0]">▸ orchestrator</span> closed turn
              · 1.2s
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

const INTEGRATIONS = [
  "Twilio",
  "Anthropic Claude",
  "Stripe",
  "Google Calendar",
  "Salesforce",
  "HubSpot",
  "BambooHR",
  "Airtable",
  "Bloomerang",
  "Zapier",
];

function IntegrationsSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-6xl text-center">
        <h2 className="text-4xl font-bold tracking-tight">Connect everything</h2>
        <p className="mt-3 text-lg text-zinc-600">
          Plug into the tools you already use.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {INTEGRATIONS.map((name) => (
            <span
              key={name}
              className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm"
            >
              {name}
            </span>
          ))}
        </div>
        <div className="mx-auto mt-12 max-w-3xl rounded-2xl border border-[#E1E9F4] bg-[#F5F8FC] p-6 text-sm leading-relaxed text-zinc-700">
          <Plug className="mx-auto h-6 w-6 text-[#1c2d4a]" />
          <p className="mt-3">
            Or drive <span className="font-semibold text-zinc-900">mustr</span>{" "}
            from Claude Desktop, Cursor, or any AI assistant &mdash; our MCP
            server makes the whole platform programmable.
          </p>
        </div>
      </div>
    </section>
  );
}

const TRUST = [
  {
    word: "Isolated",
    body: "Row-level tenant isolation on every table.",
  },
  {
    word: "Yours",
    body: "Per-tenant Twilio + Stripe Connect — your data, your funds, never commingled.",
  },
  {
    word: "Auditable",
    body: "Every AI decision logged, traceable, and replayable.",
  },
  {
    word: "Guarded",
    body: "Quiet hours, rate limits, crisis detection, A2P 10DLC, SOC 2 path.",
  },
];

function TrustSection() {
  return (
    <section className="bg-zinc-50 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <Shield className="mx-auto h-10 w-10 text-[#1c2d4a]" />
          <h2 className="mt-4 text-4xl font-bold tracking-tight">
            Trust, by design
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            Nonprofit boards demand it. We built for it.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {TRUST.map((t) => (
            <div
              key={t.word}
              className="rounded-2xl border border-zinc-200 bg-white p-6"
            >
              <p className="text-xl font-bold">{t.word}.</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">
                {t.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const TIERS = [
  {
    name: "Starter",
    price: "$99",
    cadence: "/mo",
    description: "Get your first event filled.",
    features: [
      "Up to 250 volunteers",
      "1,500 SMS / mo",
      "1 user seat",
      "Core agents (Recruiter, Scheduler, Engagement)",
    ],
    cta: "Start free trial",
    accent: false,
  },
  {
    name: "Growth",
    price: "$299",
    cadence: "/mo",
    description: "Most nonprofits start here.",
    features: [
      "Up to 2,000 volunteers",
      "10,000 SMS / mo",
      "5 seats",
      "Donation campaigns",
      "MCP server",
    ],
    cta: "Start free trial",
    accent: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "",
    description: "Built for chapters & networks.",
    features: [
      "Unlimited volunteers + SMS",
      "SSO",
      "Dedicated success",
      "Custom integrations",
      "SLA",
    ],
    cta: "Talk to us",
    accent: false,
  },
];

function PricingSection() {
  return (
    <section id="pricing" className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">
            Simple pricing, no per-volunteer fees
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            One price. Every agent. Every integration.
          </p>
        </div>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={cn(
                "flex flex-col rounded-2xl border p-8",
                t.accent
                  ? "border-[#0F172A] bg-[#0F172A] text-white shadow-xl"
                  : "border-zinc-200 bg-white"
              )}
            >
              <p
                className={cn(
                  "text-sm font-semibold uppercase tracking-wider",
                  t.accent ? "text-[#7BA9F0]" : "text-[#1c2d4a]"
                )}
              >
                {t.name}
              </p>
              <div className="mt-3 flex items-baseline gap-1">
                <span
                  className={cn(
                    "text-4xl font-bold",
                    t.accent ? "text-white" : "text-zinc-900"
                  )}
                >
                  {t.price}
                </span>
                {t.cadence && (
                  <span
                    className={cn(
                      "text-sm",
                      t.accent ? "text-zinc-300" : "text-zinc-500"
                    )}
                  >
                    {t.cadence}
                  </span>
                )}
              </div>
              <p
                className={cn(
                  "mt-2 text-sm",
                  t.accent ? "text-zinc-300" : "text-zinc-500"
                )}
              >
                {t.description}
              </p>
              <ul className="mt-6 flex-1 space-y-2 text-sm">
                {t.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <CheckCircle2
                      className={cn(
                        "mt-0.5 h-4 w-4 flex-shrink-0",
                        t.accent ? "text-[#7BA9F0]" : "text-[#1c2d4a]"
                      )}
                    />
                    <span className={t.accent ? "text-zinc-200" : "text-zinc-700"}>
                      {f}
                    </span>
                  </li>
                ))}
              </ul>
              <a
                href="#cta"
                className={cn(
                  "mt-8 rounded-full px-5 py-2.5 text-center text-sm font-semibold",
                  t.accent
                    ? "bg-white text-[#0F172A] hover:bg-zinc-100"
                    : "bg-[#0F172A] text-white hover:bg-zinc-800"
                )}
              >
                {t.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const FAQS = [
  {
    q: "Do volunteers need an app?",
    a: "No. Everything happens over SMS — they reply like they would to a friend.",
  },
  {
    q: "How do you stay compliant with A2P 10DLC?",
    a: "mustr provisions a per-tenant Twilio subaccount, registers your campaign, and handles consent and opt-outs out of the box.",
  },
  {
    q: "Can we keep our CRM?",
    a: "Yes. Salesforce, HubSpot, BambooHR, Airtable, and others can stay your source of truth — mustr syncs and stays in lane.",
  },
  {
    q: "What if the AI gets it wrong?",
    a: "Every reply has a thumbs-down. Hallucinations get flagged and routed for review. Admins can take over any thread, any time.",
  },
  {
    q: "How fast can we launch?",
    a: "Most orgs run their first event through mustr in under a week.",
  },
  {
    q: "What happens if we cancel?",
    a: "Export everything — conversations, contacts, bookings — in standard formats. We don't hold your data hostage.",
  },
];

function FAQSection() {
  return (
    <section id="faq" className="bg-zinc-50 px-6 py-24">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-4xl font-bold tracking-tight">Frequently asked</h2>
        <div className="mt-10 space-y-4">
          {FAQS.map((f) => (
            <div
              key={f.q}
              className="rounded-2xl border border-zinc-200 bg-white p-6"
            >
              <p className="font-semibold text-zinc-900">{f.q}</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">{f.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BottomCTA() {
  return (
    <section id="cta" className="px-6 py-24">
      <div className="mx-auto max-w-3xl rounded-3xl bg-gradient-to-br from-[#0F172A] to-[#1f2c50] p-12 text-center text-white shadow-2xl">
        <h2 className="text-4xl font-bold tracking-tight">
          See it run a real event.
        </h2>
        <p className="mt-3 text-lg text-zinc-300">
          15-minute demo. We&apos;ll walk through your next campaign live.
        </p>
        <a
          href="mailto:hello@mustr.app?subject=mustr%20demo"
          className="mt-8 inline-block rounded-full bg-white px-8 py-3 text-sm font-semibold text-[#0F172A] hover:bg-zinc-100"
        >
          Book your demo
        </a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white px-6 py-12">
      <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-4">
        <div>
          <Wordmark className="h-14 w-auto" />
          <p className="mt-4 max-w-xs text-sm text-zinc-500">
            Made for the people who run nonprofits.
          </p>
        </div>
        <FooterCol
          title="Product"
          links={["Features", "Pricing", "MCP server", "Changelog"]}
        />
        <FooterCol
          title="Company"
          links={["About", "Customers", "Blog", "Contact"]}
        />
        <FooterCol
          title="Legal"
          links={["Privacy", "Terms", "DPA", "Security"]}
        />
      </div>
      <p className="mx-auto mt-12 max-w-6xl text-center text-xs text-zinc-400">
        © 2026 mustr
      </p>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <p className="text-sm font-semibold text-zinc-900">{title}</p>
      <ul className="mt-3 space-y-2 text-sm text-zinc-500">
        {links.map((l) => (
          <li key={l}>
            <a href="#" className="hover:text-zinc-900">
              {l}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
